#!/usr/bin/env python3
import argparse
import csv
import os.path
import shutil
import sys

from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from requests.exceptions import ConnectionError as RequestsConnectionError

from lib.cmdline import OpenInputFileAction, StoreColumnsListAction, LoadFileLinesAction, ProtectFileOverwriteAction
from lib.csfd import search_movies, AVAILABLE_COLUMNS
from lib.settings import DEFAULT_COLUMNS, DEFAULT_SKIPPING_COLUMNS
from lib.utils import log, string_tokens

FIRST_MOVIE_YEAR = 1878

MIN_YEAR = FIRST_MOVIE_YEAR
MAX_YEAR = date.today().year


class Program:
    def __init__(self):
        """
        -i input csv file (or std input)
        -c input columns
        -s file with stopwords to be removed from base file name
        -f overwrite output
        -x filled columns
        output csv file
        """

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
        self.args = parser.parse_args()

        self.stats = dict(read=0, write=0, parse=0, match=0, skip=0, drop=0)
        self.temp_output = NamedTemporaryFile(mode="w", delete=False)
        self.stopwords = set(self.args.stopwords or [])
        with open('assets/stopwords.txt', 'r') as f:
            self.stopwords.update(set([x.strip() for x in f.read().strip().splitlines() if x]))

    def backup(self, original_file_name, count=0):
        def fname(i):
            return "{fn}.bak{suff}".format(fn=original_file_name, suff='.{0}'.format(i) if i else '')

        backup = Path(fname(count))
        if backup.is_file():
            self.backup(original_file_name, count + 1)

        target = Path(fname(count - 1)) if count > 0 else Path(original_file_name)
        target.rename(backup)

    def finish(self):
        if hasattr(self, 'temp_output'):
            self.temp_output.close()

            if hasattr(self, 'args'):
                if self.args.input != sys.stdin:
                    self.args.input.close()

                if hasattr(self, 'stats'):
                    if self.stats['write'] > 0:
                        if os.path.isfile(self.args.output):
                            if self.args.overwrite == 1:
                                self.backup(self.args.output)
                            elif self.args.overwrite == 2:
                                os.remove(self.args.output)

                        shutil.move(self.temp_output.name, self.args.output)

                    w, pm, s, d = self.stats['write'], self.stats['match'], self.stats['skip'], self.stats['drop']
                    log("\nWrote: {w}; perfect matches: {pm}, skipped: {s}, dropped: {d}\n".format(
                        w=w, pm=pm, s=s, d=d))

    def main(self):
        total = None
        if self.args.input != sys.stdin:
            total = len([line for line in self.args.input])
            self.args.input.seek(0)
            log("Total number of requested records: {0}".format(total))  # init console output

        reader = csv.reader(self.args.input, delimiter=",", quotechar='"')
        writer = csv.writer(self.temp_output, quoting=csv.QUOTE_MINIMAL, delimiter=",", quotechar='"')

        writer.writerow(self.args.columns)  # header row

        for line in reader:
            self.stats['read'] += 1

            record = dict((k, v) for k, v in zip(self.args.columns, line) if v)

            cols = self.args.skipping_columns
            vals = filter(None, map(record.get, cols))
            skipped = cols and len(cols) == len(list(vals))

            if not skipped:
                kwlog = dict(total=total, counter=self.stats['read'])

                # make query
                if 'query' in record:
                    query = record['query']

                elif 'title' in record and 'year' in record:
                    raw_query = ' '.join(filter(None, map(record.get, ['title', 'year', 'director'])))
                    query = ' '.join(string_tokens(raw_query))

                elif 'raw_query' in record:
                    record['tokenized_raw_query'] = string_tokens(record['raw_query'], self.stopwords)
                    query = ' '.join(record['tokenized_raw_query'])

                else:
                    self.stats['drop'] += 1
                    continue

                log("- processing '{0}'".format(query), **kwlog)

                try:
                    movies = search_movies(query)

                    rows = []
                    for movie in movies:
                        # prepare for comparison
                        query_tokens = set(string_tokens(query))
                        result_tokens = set(string_tokens(' '.join(movie.values())))

                        # discard unwanted values
                        result_tokens.discard(record.get('match'))
                        for x in map(str, range(10)):
                            query_tokens.discard(x), result_tokens.discard(x)

                        # compare query and result and try to find perfect match
                        matching_vals = result_tokens.intersection(query_tokens)
                        matching_years = (y for y in matching_vals if (y.isdigit() and MIN_YEAR <= int(y) < MAX_YEAR))
                        movie_year = movie.get('year')

                        def match(key, value):
                            return value and value == record.get(key)

                        # perfect match:
                        matches_ok = movie_year in matching_years and query_tokens.issubset(result_tokens)
                        if matches_ok or (match('title', movie.get('title')) and match('year', movie_year)):
                            rows = [{**record, **movie, 'match': "100"}]
                            break

                        rows += [{**record, **movie}]

                except RequestsConnectionError:
                    rows = [{**record}]
                    log("Connection error ({0})".format(query), **kwlog)

            else:
                self.stats['skip'] += 1
                rows = [{**record, 'match': "100"}]

            self.stats['match' if len(rows) == 1 and rows[0]['match'] == "100" else 'parse'] += 1

            for r in rows:
                writer.writerow([r.get(col, '') for col in self.args.columns])
                self.stats['write'] += 1


if __name__ == "__main__":
    program = Program()

    try:
        program.main()

    except KeyboardInterrupt:
        print()  # end the line if the input was interrupted by Ctrl+C

    program.finish()
