#!/usr/bin/env python3
import argparse
import csv
import os.path
import shutil
import sys

from collections import defaultdict
from tempfile import NamedTemporaryFile
from requests.exceptions import ConnectionError as RequestsConnectionError

from lib.action import OpenInputFileAction, StoreColumnsListAction, LoadFileLinesAction, ProtectFileOverwriteAction
from lib.movies import search_movies, AVAILABLE_COLUMNS, movie_query_match
from lib.settings import DEFAULT_COLUMNS, DEFAULT_SKIPPING_COLUMNS, FLAT_GROUPBY_COLUMNS
from lib.utils import log, tokenize_string, backup_rename, print_dict_as_table


class Program:
    """
    -i input csv file (or std input)
    -c input columns
    -s file with stopwords to be removed from base file name
    -f overwrite output
    -x filled columns
    output csv file
    """

    def __init__(self):
        parser = self.get_parser()
        self.args = parser.parse_args()
        self.stats = defaultdict(int)
        self.temp_output = NamedTemporaryFile(mode="w", delete=False)
        self.stopwords = set(self.args.stopwords or [])
        with open('assets/stopwords.txt', 'r') as f:
            self.stopwords.update(set([x.strip() for x in f.read().strip().splitlines() if x]))

    @staticmethod
    def get_parser():
        parser = argparse.ArgumentParser(description="Scans movie files in a directory and returns matches from ČSFD.")

        # INPUT CSV FILE
        parser.add_argument("-i",
                            action=OpenInputFileAction, dest="input", metavar="FILENAME", default=sys.stdin,
                            help="The input csv file name. Reads standard input if not set.")

        # INPUT COLUMNS
        parser.add_argument("-c",
                            action=StoreColumnsListAction, dest="columns", metavar="COLUMNS",
                            default=DEFAULT_COLUMNS,
                            help="comma-separated list of column names. "
                                 "OPTIONS: {0}. ".format(', '.join(sorted(AVAILABLE_COLUMNS))) +
                                 'First column is always "file name". '
                                 'DEFAULT: "{0}"'.format(','.join(DEFAULT_COLUMNS)))

        # FILES - STOPWORDS IN FILENAMES
        parser.add_argument("-s",
                            action=LoadFileLinesAction, nargs=1, dest="stopwords", metavar="FILE",
                            help="Name of file containing ignored words (one stop word per line).")

        # OVERWRITE OUTPUT
        # PROHIBIT BACKUP (2nd usage)
        parser.add_argument("-f",
                            action="count", dest="overwrite", default=0,
                            help="Overwrites existing output file, if used twice, overwrites without a backup.")

        # OUTPUT FILLED COLUMNS TO SKIP QUERY
        parser.add_argument("-x",
                            action=StoreColumnsListAction, dest="skipping_columns", metavar="COLUMNS",
                            default=DEFAULT_SKIPPING_COLUMNS,
                            help="comma-separated list of columns. When all that columns are filled, "
                                 "no new information is searched. "
                                 "OPTIONS: {0}. ".format(', '.join(sorted(AVAILABLE_COLUMNS))) +
                                 'DEFAULT: "{0}".'.format(','.join(DEFAULT_SKIPPING_COLUMNS)))

        # OUTPUT FILE
        parser.add_argument('output',
                            action=ProtectFileOverwriteAction, metavar='OUTPUT_FILE',
                            help="Name of the output CSV file.")

        return parser

    def finish(self):
        if hasattr(self, 'temp_output'):
            self.temp_output.close()

        if self.args.input and self.args.input != sys.stdin:
            self.args.input.close()

        if self.stats['write']:
            if os.path.isfile(self.args.output):
                if self.args.overwrite == 1:  # single usage -f
                    backup_rename(self.args.output)
                elif self.args.overwrite == 2:  # double usage -ff
                    os.remove(self.args.output)

            shutil.move(self.temp_output.name, self.args.output)
        print('\n\n')
        print_dict_as_table(self.stats)

    def main(self):
        total = None
        if self.args.input == sys.stdin:
            log("Reading the standard input...")

        else:
            total = len([line for line in self.args.input])
            self.args.input.seek(0)
            log("Total number of requested records: {0}".format(total))  # init console output

        reader = csv.reader(self.args.input, delimiter=",", quotechar='"')
        writer = csv.writer(self.temp_output, quoting=csv.QUOTE_MINIMAL, delimiter=",", quotechar='"')

        writer.writerow(self.args.columns)  # header row

        for src_row in reader:
            kwlog = dict(total=total, counter=self.stats['read'])
            log('- processing input: {}'.format(src_row), **kwlog)
            self.stats['read'] += 1

            record = defaultdict(list)
            for i, c in enumerate(self.args.columns):
                if i <= len(src_row) - 1:
                    record[c] += [src_row[i]]

            # skipped == all of the skipping_columns have values.
            cols = self.args.skipping_columns
            vals = filter(None, map(lambda x: len(record[x]) > 0, cols))
            skipped = cols and len(cols) == len(list(vals))

            if not skipped:

                # make query
                if len(record['query']):
                    query = record['query']

                elif len(record['title']):
                    tokens = []
                    tokens += record['title']
                    tokens += record['year']
                    tokens += record['director']
                    raw_query = ' '.join(filter(None, tokens))
                    query = ' '.join(tokenize_string(raw_query))

                elif len(record['filename']):
                    [filename] = record['filename']
                    query = ' '.join(tokenize_string(filename, self.stopwords))

                else:
                    self.stats['drop'] += 1
                    print("  - could not create query: ", record)
                    continue

                log("  - query: '{0}'".format(query), **kwlog)

                try:
                    movies = search_movies(query)

                    current_movie_rows = []
                    log("  - got {} {}".format(len(movies), 'result' if len(movies) == 1 else 'results'), **kwlog)
                    for cnt, movie in enumerate(movies):
                        # prepare for comparison

                        def matches(key):
                            v = movie.get(key)
                            return v and v == record.get(key)

                        # perfect match:
                        if "100" in movie['match'] or (matches('title') and matches('year')):
                            log("  - found perfect match #{}: {}".format(cnt+1, movie), **kwlog)
                            current_movie_rows = [{**record, **movie}]
                            break

                        row = {**record, **movie}
                        current_movie_rows += [row]
                        log("  - added a result #{}: {}".format(cnt+1, row), **kwlog)

                except RequestsConnectionError:
                    current_movie_rows = [{**record}]
                    log("  - connection error ({0})".format(query), **kwlog)

            else:
                self.stats['skip'] += 1
                log("  - skipped", **kwlog)
                current_movie_rows = [{**record, 'match': ["100"]}]

            stats_key = 'match' if len(current_movie_rows) == 1 and "100" in current_movie_rows[0]['match'] else 'parse'
            log(stats_key, **kwlog)
            self.stats[stats_key] += 1

            for row in current_movie_rows:
                dest_row = []
                for col in self.args.columns:
                    value = ''
                    if len(row[col]):
                        if col not in FLAT_GROUPBY_COLUMNS:
                            value = row[col].pop(0)
                        else:
                            value = row[col][0]
                    dest_row += value if type(value) == list else [value]

                writer.writerow(dest_row)
                self.stats['write'] += 1
            kwlog['counter'] += + 1
            log(**kwlog)


if __name__ == "__main__":
    program = Program()

    try:
        program.main()

    except KeyboardInterrupt:
        print()  # end the line if the input was interrupted by Ctrl+C

    program.finish()
