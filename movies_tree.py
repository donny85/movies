#!/usr/bin/env python3
import argparse
import copy
import csv
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from lib.cmdline import OpenInputFileAction, StoreColumnsListAction, EnsureDirectoryAction, \
    EnsureExistingDirectoryAction, StoreColumnsSetAction

FILENAME_COLUMN_ID = 0
PATH_CWD = Path('.')
COLUMNS = {  # names of the group subdirectories
    'title': "Podle abecedy",
    'year': "Podle roku",
    'genre': "Podle žánru",
    'country': "Podle země",
    'director': "Podle režie",
    'actor': "Podle obsazení",
}
FLAT_GROUPBY_COLUMNS = ('title',)  # these custom-sort directories doesn't group into subdirectories by value
DEFAULT_COLUMNS = (
    'filename', 'title', 'year', 'genre', 'genre', 'country', 'country', 'director', 'actor', 'actor',
)
DEFAULT_GROUPBY_COLUMNS = ('title', 'genre', 'country', 'director', 'actor')


class Program:
    def __init__(self):
        """
        -i input csv file (or std input)
        -c comma-separated list of csv columns
        -g comma-separated list of group-by columns
        -d directory containing source media files
        -o new tree directory (on same filesystem as the source dir)
        -u update directory tree (allow removing hard links)
        -r clear new tree directory before creating new tree (not clearing CWD)
        """
        parser = argparse.ArgumentParser(description="Creates groupped movie directories.")

        parser.add_argument('-i',  # INPUT CSV DATA
                            action=OpenInputFileAction, dest='input', metavar='FILENAME', default=sys.stdin,
                            help="The input csv file name. Reads standard input if not set.")

        parser.add_argument('-c',  # INPUT COLUMNS
                            action=StoreColumnsListAction, dest='columns', metavar='COLUMNS',
                            default=DEFAULT_COLUMNS, help="comma-separated list of the input file's columns. "
                                                          "The first column is always column containing "
                                                          "a file name. OPTIONS: " +
                                                          ', '.join(sorted(COLUMNS.keys())) +
                                                          '. First column is always "file name". '
                                                          'DEFAULT: "{0}".'.format(','.join(DEFAULT_COLUMNS)))

        parser.add_argument('-g',  # GROUP-BY COLUMNS
                            action=StoreColumnsSetAction, dest='groupby_columns', metavar='COLUMNS',
                            default=DEFAULT_GROUPBY_COLUMNS, help="comma-separated columns list for movies grouping. "
                                                                  "OPTIONS: " +
                                                                  str(', '.join(sorted(COLUMNS.keys()))) +
                                                                  '. DEFAULT: ' +
                                                                  str(','.join(DEFAULT_GROUPBY_COLUMNS)) +
                                                                  '.'
                            )

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

        parser.add_argument('-v',  # VERBOSE
                            action='store_true', dest='verbose',
                            help='Print what is done.')
        self.args = parser.parse_args()

        self.stats = defaultdict(int)

    def main(self):
        output_is_cwd = self.args.output_dir.samefile('.')
        if self.args.output_clear and not output_is_cwd:
            shutil.rmtree(self.args.output_dir)
            self.stats['clear_output_dir'] += 1
            print('Removed all contents of the target directory: {0}/'.format(self.args.output_dir.absolute()))

        reader = csv.reader(self.args.input, delimiter=",", quotechar='"')
        next(reader)  # skip header row.
        for line in reader:
            original_filename = line[FILENAME_COLUMN_ID]
            _, fn_extension = os.path.splitext(original_filename)
            source_path = Path(self.args.input_dir, original_filename)

            if not source_path.is_file():
                print('Source movie file not found: ' + str(source_path.absolute()))
                self.stats['file_not_found'] += 1
                continue

            movie = self.parse_csv_movie(line)

            for col in self.args.groupby_columns:
                if col in movie:
                    for i in range(len(movie[col])):
                        if col in FLAT_GROUPBY_COLUMNS:
                            new_filename = self.movie_file_name(movie)

                        else:
                            movie_ = copy.deepcopy(movie)
                            del movie_[col][i]  # remove subdirectory name from the file name
                            new_filename = self.movie_file_name(movie_)

                        bits = [self.args.output_dir,
                                COLUMNS[col],  # custom-sort subdirectory name
                                None if col in FLAT_GROUPBY_COLUMNS else movie[col][i],  # group by value
                                '{name}{ext}'.format(name=new_filename, ext=fn_extension)
                                ]

                        target_path = Path(*filter(None, bits))

                        target_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)

                        if target_path.is_dir():
                            self.stats['hardlinks_are_dirs'] += 1
                            if self.args.verbose:
                                print(
                                    'Target path is a directory, I will not touch that: ' + str(target_path.absolute()))
                            continue

                        if target_path.is_file():
                            if target_path.samefile(source_path):
                                self.stats['hardlinks_found'] += 1
                                continue  # be quiet when nothing is needed to be done

                            if self.args.output_update:
                                target_path.unlink()
                                self.stats['hardlinks_removed'] += 1
                                if self.args.verbose:
                                    print("Removed hardlink: " + target_path.absolute())

                        try:
                            if hasattr(source_path, 'link_to'):
                                source_path.link_to(target_path)
                            else:  # python<3.8
                                os.link(str(source_path.absolute()), str(target_path.absolute()))

                            self.stats['hardlinks_new'] += 1
                            if self.args.verbose:
                                print("Created new hardlink: '{0}' -> '{1}'".format(source_path, target_path))

                        except FileExistsError:
                            self.stats['hardlinks_occupied'] += 1
                            if self.args.verbose:
                                print("I would like to overwrite, I will not touch that: {0}."
                                      .format(target_path.absolute()))
                            # continue

    def parse_csv_movie(self, line):
        movie = dict()
        for i, col in enumerate(self.args.columns):
            if col not in movie:
                movie[col] = []
            if line[i]:
                movie[col] += [line[i]]
        """
        {
            "title": ["Supersmradi - Malí Géniové 2"],
            "actor": ["Jon Voight", "Scott Baio"],
            "director": ["Bob Clark"],
            "genre": [],
            ...
        }
        """
        return movie

    @staticmethod
    def movie_file_name(movie):
        title = ', '.join(movie.get('title', ()))
        director = ', '.join(movie.get('director', ()))
        year = ', '.join(movie.get('year', ()))
        genres = ', '.join(movie.get('genre', ()))
        actors = ', '.join(movie.get('actor', ()))
        desc = '; '.join(filter(None, [director, genres, actors]))
        details = ', '.join(filter(None, [year, desc]))
        """
        Supersmradi - Malí Géniové 2 (1997, Bob Clark; Rodinný, Komedie; Jon Voight, Scott Baio)
        """
        fn = '{0} ({1})'.format(title, details) if details else title
        return fn.replace(r'/', '_')

    def print_stats(self):
        row_format = "|{:>15}" * 2 + '|'
        print(row_format.format("event", "triggered"))
        print(('|' + '-' * 15) * 2 + '|')
        for item in self.stats.items():
            print(row_format.format(*item))


if __name__ == "__main__":
    program = Program()

    try:
        program.main()

    except KeyboardInterrupt:
        print()  # quiet Ctrl+C interruption, just finish last line.

    program.print_stats()
