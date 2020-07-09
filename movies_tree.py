#!/usr/bin/env python3
import argparse
import copy
import csv
import os
import shutil
import sys
from pathlib import Path

from lib.cmdline import OpenInputFileAction, StoreColumnsListAction, EnsureDirectoryAction, \
    EnsureExistingDirectoryAction, StoreColumnsSetAction

FILENAME_COLUMN_ID = 0
PATH_CWD = Path('.')
OUTPUT_COLUMNS = {  # names of the group subdirectories
    'title': "Podle abecedy",
    'year': "Podle roku",
    'genre': "Podle žánru",
    'country': "Podle země",
    'director': "Podle režie",
    'actor': "Podle obsazení",
}
OUTPUT_COLUMNS_UNGRUPPED = ('title',)  # these custom-sort directories doesn't group into subdirectories by value
DEFAULT_INPUT_COLUMNS = (
    'filename', 'title', 'year', 'genre', 'genre', 'country', 'country', 'director', 'actor', 'actor',
)
DEFAULT_RENAME_COLUMNS = ('title', 'genre', 'country', 'director', 'actor')


class Program:
    def __init__(self):
        parser = argparse.ArgumentParser(description="Creates groupped movie directories.")

        parser.add_argument('-i',  # INPUT CSV DATA
                            action=OpenInputFileAction, dest='input', metavar='FILENAME', default=sys.stdin,
                            help="The input csv file name. Reads standard input if not set.")

        parser.add_argument('-c',  # INPUT COLUMNS
                            action=StoreColumnsListAction, dest='input_columns', metavar='COLUMNS',
                            default=DEFAULT_INPUT_COLUMNS, help=f"comma-separated list of the input file's columns. "
                                                                f"The first column is always column containing "
                                                                f"a file name. OPTIONS: "
                                                                f"{', '.join(sorted(OUTPUT_COLUMNS.keys()))}. "
                                                                f"First column is always \"filename\". "
                                                                f"DEFAULT: \"{','.join(DEFAULT_INPUT_COLUMNS)}\".")

        parser.add_argument('-r',  # RENAME BY COLUMNS
                            action=StoreColumnsSetAction, dest='output_columns', metavar='COLUMNS',
                            default=DEFAULT_RENAME_COLUMNS, help=f"comma-separated columns list for movies grouping. "
                                                                 f"OPTIONS: {', '.join(sorted(OUTPUT_COLUMNS.keys()))}."
                                                                 f" DEFAULT: \"{','.join(DEFAULT_RENAME_COLUMNS)}\".")

        parser.add_argument('-d',  # INPUT DIRECTORY
                            action=EnsureExistingDirectoryAction, dest='input_dir', metavar='DIRECTORY',
                            default=PATH_CWD, help="Directory containing input files")

        parser.add_argument('-o',  # OUTPUT DIRECTORY
                            action=EnsureDirectoryAction, dest='output_dir', metavar='DIRECTORY',
                            default=Path('.'), help="Directory for output hardlinks. Will be created if not exist.")

        parser.add_argument('-x',  # CLEAR OUTPUT DIRECTORY
                            action='store_true', dest='output_clear',
                            help="Clear all files in the output directory before creating new hardlinks. By default "
                                 "clearing of the current working directory is prohibited.")

        self.args = parser.parse_args()

    def main(self):
        output_is_cwd = self.args.output_dir.samefile('.')
        if self.args.output_clear and not output_is_cwd:
            shutil.rmtree(self.args.output_dir)
            print(f'Removed all contents of the target directory: {self.args.output_dir.absolute()}/')

        reader = csv.reader(self.args.input, delimiter=",", quotechar='"')
        next(reader)  # skip header row. TODO: separate command-line argument?
        for line in reader:
            original_filename = line[FILENAME_COLUMN_ID]
            _, fn_extension = os.path.splitext(original_filename)
            source_path = Path(self.args.input_dir, original_filename)

            if not source_path.is_file():
                print(f'Source movie file not found: {source_path.absolute()}.')
                continue

            movie = self.parse_csv_movie(line)

            for col in self.args.output_columns:
                if col in movie:
                    for i in range(len(movie[col])):
                        if col in OUTPUT_COLUMNS_UNGRUPPED:
                            new_filename = self.movie_file_name(movie)

                        else:
                            movie_ = copy.deepcopy(movie)
                            del movie_[col][i]  # remove subdirectory name from the file name
                            new_filename = self.movie_file_name(movie_)

                        bits = [self.args.output_dir,
                                OUTPUT_COLUMNS[col],  # custom-sort subdirectory name
                                None if col in OUTPUT_COLUMNS_UNGRUPPED else movie[col][i],  # group by value
                                f'{new_filename}{fn_extension}'
                                ]

                        target_path = Path(*filter(None, bits))

                        target_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)

                        if target_path.is_dir():
                            print(f'Target path is a directory, I will not touch that: {target_path.absolute()}')
                            continue

                        if target_path.is_file():
                            if target_path.samefile(source_path):
                                continue  # be quiet when nothing is needed to be done

                        try:
                            source_path.link_to(target_path)
                            print(f"Created new hardlink: '{source_path}' -> '{target_path}'")

                        except FileExistsError:
                            print(f"I would like to overwrite, I will not touch that: {target_path.absolute()}.")
                            # continue

    def parse_csv_movie(self, line):
        movie = dict()
        for i, col in enumerate(self.args.input_columns):
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
        return f'{title} ({details})' if details else title


if __name__ == "__main__":
    program = Program()

    try:
        program.main()

    except KeyboardInterrupt:
        print()  # quiet Ctrl+C interruption, just finish last line.
