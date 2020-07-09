#!/usr/bin/env python3
import csv
import os.path
import shutil
import sys

from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from requests.exceptions import ConnectionError as RequestsConnectionError

from lib.cmdline import parse_args
from lib.csfd import search_movies
from lib.utils import log, string_tokens

FIRST_MOVIE_YEAR = 1878

MIN_YEAR = FIRST_MOVIE_YEAR
MAX_YEAR = date.today().year


class Program:
    def __init__(self):
        self.args = parse_args()
        self.stats = dict(read=0, write=0, parse=0, match=0, skip=0, drop=0)
        self.temp_output = NamedTemporaryFile(mode="w", delete=False)
        self.stopwords = set(self.args.stopwords or [])
        with open('assets/stopwords.txt', 'r') as f:
            self.stopwords.update(set([x.strip() for x in f.read().strip().splitlines() if x]))

    def backup(self, original_file_name, count=0):
        def fname(i):
            return f"{original_file_name}.bak{f'.{i}' if i else ''}"

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

                        print('self.temp_output.name', self.temp_output.name)
                        print('self.args.output', self.args.output)

                        shutil.move(self.temp_output.name, self.args.output)

                    w, pm, s, d = self.stats['write'], self.stats['match'], self.stats['skip'], self.stats['drop']
                    log(f"\nWrote: {w}; perfect matches: {pm}, skipped: {s}, dropped: {d}\n")

    def main(self):
        total = None
        if self.args.input != sys.stdin:
            total = len([line for line in self.args.input])
            self.args.input.seek(0)
            log(f"Total number of requested records: {total}", total)  # init console output

        reader = csv.reader(self.args.input,
                            delimiter=self.args.input_delimiter, quotechar=self.args.input_quot)
        writer = csv.writer(self.temp_output, quoting=csv.QUOTE_MINIMAL,
                            delimiter=self.args.output_delimiter, quotechar=self.args.output_quot)

        writer.writerow(self.args.input_columns)  # header row

        for line in reader:
            self.stats['read'] += 1

            record = dict((k, v) for k, v in zip(self.args.input_columns, line) if v)

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

                log(f"- processing '{query}'", **kwlog)

                try:
                    movies = search_movies(query, self.args.output_columns)

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

                        matches_ok = movie_year in matching_years and query_tokens.issubset(result_tokens)

                        def match(key, value):
                            return value == record.get(key) if value else False

                        perfect_match = matches_ok or (match('title', movie.get('title')) and match('year', movie_year))

                        if perfect_match:
                            rows = [{**record, **movie, 'match': "100"}]
                            break

                        rows += [{**record, **movie}]

                except RequestsConnectionError:
                    rows = [{**record}]
                    log(f"Connection error ({query})", **kwlog)

            else:
                self.stats['skip'] += 1
                rows = [{**record, 'match': "100"}]

            self.stats['match' if len(rows) == 1 and rows[0]['match'] == "100" else 'parse'] += 1

            for r in rows:
                writer.writerow([r.get(col, '') for col in self.args.output_columns])
                self.stats['write'] += 1


if __name__ == "__main__":
    program = Program()

    try:
        program.main()

    except KeyboardInterrupt:
        print()  # end the line if the input was interrupted by Ctrl+C

    program.finish()
