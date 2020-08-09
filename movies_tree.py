#!/usr/bin/env python3
import argparse
import copy
import csv
import os
import shutil
import sys

from collections import defaultdict
from pathlib import Path

from lib.action import OpenInputFileAction, StoreColumnsListAction, EnsureDirectoryAction, \
    EnsureExistingDirectoryAction, StoreColumnsSetAction
from lib.movies import movie_file_name, parse_csv_movie
from lib.settings import COLUMNS, FLAT_GROUPBY_COLUMNS, DEFAULT_COLUMNS, DEFAULT_GROUPBY_COLUMNS
from lib.utils import print_dict_as_table

FILENAME_COLUMN_ID = 0
PATH_CWD = Path('.')


class Program:
    """
    -i input csv file (or std input)
    -c comma-separated list of csv columns
    -g comma-separated list of group-by columns
    -d directory containing source media files
    -o new tree directory (on same filesystem as the source dir)
    -u update directory tree (allow removing hard links)
    -r clear new tree directory before creating new tree (not clearing CWD)
    --verbose increase verbosity
    --dry-run avoid any changes to file system
    """

    def __init__(self):
        parser = self.get_parser()
        self.args = parser.parse_args()
        self.stats = defaultdict(int)

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser(description="Creates groupped movie directories.")

        parser.add_argument('-i',  # INPUT CSV DATA
                            action=OpenInputFileAction, dest='input', metavar='FILENAME', default=sys.stdin,
                            help="The input csv file name. Reads standard input if not set.")

        parser.add_argument('-c',  # INPUT COLUMNS
                            action=StoreColumnsListAction, dest='columns', metavar='COLUMNS',
                            default=DEFAULT_COLUMNS, help="comma-separated list of the input file's columns. "
                                                          "The first column is always column containing "
                                                          "a file name. OPTIONS: " + ', '.join(sorted(COLUMNS.keys())) +
                                                          '. First column is always "filename". DEFAULT: "' +
                                                          ','.join(DEFAULT_COLUMNS) + '".')

        parser.add_argument('-g',  # GROUP-BY COLUMNS
                            action=StoreColumnsSetAction, dest='groupby_columns', metavar='COLUMNS',
                            default=DEFAULT_GROUPBY_COLUMNS, help="comma-separated columns list for movies grouping. "
                                                                  "OPTIONS: " + str(', '.join(sorted(COLUMNS.keys()))) +
                                                                  '. DEFAULT: "' +
                                                                  ','.join(DEFAULT_GROUPBY_COLUMNS) + '".')

        parser.add_argument('-d',  # INPUT DIRECTORY
                            action=EnsureExistingDirectoryAction, dest='input_dir', metavar='DIRECTORY',
                            default=PATH_CWD, help="Directory containing input files")

        parser.add_argument('-o',  # OUTPUT DIRECTORY
                            action=EnsureDirectoryAction, dest='output_dir', metavar='DIRECTORY',
                            default=Path('.'), help="Directory for output hardlinks. Will be created if not exist.")

        parser.add_argument('-u',  # UPDATE OUTPUT_DIRECTORY
                            action='store_true', dest='output_update',
                            help="Allow removing hardlinks in the output tree."
                            )

        parser.add_argument('-r',  # CLEAR OUTPUT DIRECTORY
                            action='store_true', dest='output_clear',
                            help="Clear all files in the output directory before creating new hardlinks. By default "
                                 "clearing of the current working directory is prohibited.")

        parser.add_argument('--verbose',  # VERBOSE
                            action='store_true', dest='verbose',
                            help="Print what is done.")

        parser.add_argument('--dry-run',  # DRY RUN
                            action='store_true', dest='dry_run',
                            help="Don't do any filesystem modification.")

        return parser

    def finish(self):
        print_dict_as_table(self.stats)

    def main(self):
        output_is_cwd = self.args.output_dir.samefile('.')
        if self.args.output_clear and not output_is_cwd:
            shutil.rmtree(self.args.output_dir)
            self.stats['clear_output_dir'] += 1
            print('Removed all contents of the target directory: {0}/'.format(self.args.output_dir.absolute()))

        reader = csv.reader(self.args.input, delimiter=",", quotechar='"')

        # skip header row
        next(reader)

        for line in reader:
            original_filename = line[FILENAME_COLUMN_ID]
            _, fn_extension = os.path.splitext(original_filename)
            source_path = Path(self.args.input_dir, original_filename)

            if not source_path.is_file():
                print('Source movie file not found: ' + str(source_path.absolute()))
                self.stats['file_not_found'] += 1
                continue

            movie = parse_csv_movie(self.args.columns, line)

            for groupby_column in self.args.groupby_columns:
                if groupby_column in movie:
                    for idx_movie_prop in range(len(movie[groupby_column])):
                        if groupby_column in FLAT_GROUPBY_COLUMNS:
                            new_filename = movie_file_name(movie)

                        else:
                            movie_ = copy.deepcopy(movie)
                            # remove subdirectory name from the file name
                            del movie_[groupby_column][idx_movie_prop]
                            new_filename = movie_file_name(movie_)

                        bits = [self.args.output_dir,
                                COLUMNS[groupby_column],  # custom-sort subdirectory name
                                None if groupby_column in FLAT_GROUPBY_COLUMNS
                                else movie[groupby_column][idx_movie_prop],  # group by value
                                '{name}{ext}'.format(name=new_filename, ext=fn_extension)
                                ]

                        target_path = Path(*filter(None, bits))

                        if not self.args.dry_run:
                            target_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)

                        if target_path.is_dir():
                            self.stats['hardlinks_are_dirs'] += 1
                            if self.args.verbose:
                                print('Cannot create hard link: ' + str(target_path.absolute()))
                            continue  # this has to be resolved manually

                        if target_path.is_file():
                            if target_path.samefile(source_path):
                                self.stats['hardlinks_found'] += 1
                                if self.args.verbose:
                                    print("Hard link found: " + str(target_path.absolute()))
                                continue  # be quiet when nothing is needed to be done

                            if self.args.output_update:
                                if not self.args.dry_run:
                                    target_path.unlink()
                                self.stats['hardlinks_removed'] += 1
                                if self.args.verbose:
                                    print("Removed file in the place of hard link: " + str(target_path.absolute()))

                        try:
                            if not self.args.dry_run:
                                if hasattr(source_path, 'link_to'):
                                    source_path.link_to(target_path)
                                else:  # python<3.8
                                    os.link(str(source_path.absolute()), str(target_path.absolute()))

                            self.stats['hardlinks_new'] += 1
                            if self.args.verbose:
                                print("Created hard link: '{0}' -> '{1}'".format(source_path, target_path))

                        except FileExistsError:
                            self.stats['hardlinks_occupied'] += 1
                            if self.args.verbose:
                                print("Another file already exists on the path: " + str(target_path.absolute()))
                            # continue


if __name__ == "__main__":
    program = Program()

    try:
        program.main()

    except KeyboardInterrupt:
        print()  # quiet Ctrl+C interruption, just finish last line.

    program.finish()
