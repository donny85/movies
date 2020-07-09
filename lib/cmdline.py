import argparse
import os
import sys
from pathlib import Path

from lib.settings import DEFAULT_COLUMNS
from lib.csfd import AVAILABLE_COLUMNS




class SimpleAction(argparse.Action):
    def action(self, parser, namespace, value, option_string=None):
        return value

    def __call__(self, parser, namespace, value, option_string=None):
        if type(value) == list:
            if len(value) > 1:
                raise NotImplementedError("SimpleAction: multiple values not supported.")
            value = value[0]

        value = self.action(parser, namespace, value, option_string)
        setattr(namespace, self.dest, value)


class EnsureExistingDirectoryAction(SimpleAction):
    def action(self, parser, namespace, value, option_string=None):
        path = Path(value)
        if not path.is_dir():
            raise argparse.ArgumentError(self, f"Not a directory: {path.absolute()}")
        return super().action(parser, namespace, path, option_string)


class EnsureDirectoryAction(SimpleAction):
    def action(self, parser, namespace, value, option_string=None):
        path = Path(value)
        if path.exists() and not path.is_dir():
            raise argparse.ArgumentError(self, f"Not a directory: {path.absolute()}")
        path.mkdir(mode=0o755, parents=True, exist_ok=True)
        return super().action(parser, namespace, path, option_string)


class OpenInputFileAction(SimpleAction):
    def action(self, parser, namespace, value, option_string=None):
        value = open(value, 'r')
        return super().action(parser, namespace, value, option_string)


class LoadFileLinesAction(SimpleAction):
    def action(self, parser, namespace, value, option_string=None):
        with open(value, 'r') as f:
            try:
                new_value = set([x for x in f.read().strip().splitlines() if x])
            except IOError as e:
                raise argparse.ArgumentError(self, f'error reading {value}: {e}')

            return super().action(parser, namespace, new_value, option_string)


class ProtectFileOverwriteAction(SimpleAction):
    def action(self, parser, namespace, value, option_string=None):
        overwrite = getattr(namespace, 'overwrite')
        if os.path.isfile(value) and not overwrite:
            raise argparse.ArgumentError(self, 'Output file already exists. Use "-f" to overwrite.')
        return super().action(parser, namespace, value, option_string)


class StoreColumnsSetAction(SimpleAction):
    def action(self, parser, namespace, value, option_string=None):
        value = set([s.strip() for s in value.lower().strip().split(',') if s])
        return super().action(parser, namespace, value, option_string)


class StoreColumnsListAction(SimpleAction):
    def action(self, parser, namespace, value, option_string=None):
        value = list([s.strip() for s in value.lower().strip().split(',') if s])
        return super().action(parser, namespace, value, option_string)


"""
-i input csv file (or std input)
-i:c input columns
-i:d input divider
-i:q input quot. marks

-s file with stopwords to be removed from base file name 

-n normalize file names

-f overwrite output

-o:x filled columns
-o:c output columns
-o:d output divider
-o:q output quot. marks
output csv file
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Scans movie files in a directory and returns matches from ČSFD.")

    # INPUT CSV FILE
    parser.add_argument("-i",
                        action=OpenInputFileAction, dest="input", metavar="FILENAME", default=sys.stdin,
                        help="The input csv file name. Reads standard input if not set.")

    # INPUT COLUMNS
    parser.add_argument("-i:c",
                        action=StoreColumnsListAction, dest="input_columns", metavar="COLUMNS", default=DEFAULT_COLUMNS,
                        help=f"comma-separated list of input columns. "
                             f"OPTIONS: {', '.join(sorted(AVAILABLE_COLUMNS))}. "
                             f"First column is always \"file name\". "
                             f"DEFAULT: \"{','.join(DEFAULT_COLUMNS)}\"")

    # INPUT DIVIDER
    parser.add_argument("-i:d",
                        action="store", dest="input_delimiter", default=",",
                        help="Input CSV columns delimiter, default=\",\"")

    # INPUT QUOT. MARKS
    parser.add_argument("-i:q",
                        action="store", dest="input_quot", default="'",
                        help="Input CSV quotation marks, default=\"'\" (single quote).")

    # FILES - STOPWORDS IN FILENAMES
    parser.add_argument("-s",
                        action=LoadFileLinesAction, nargs=1, dest="stopwords", metavar="FILE",
                        help="Name of file containing ignored words (one stop word per line).")

    # OVERWRITE OUTPUT
    # PROHIBIT BACKUP (2nd usage)
    parser.add_argument("-f",
                        action="count", dest="overwrite", default=0,
                        help="Overwrites existing output file, if used twice, overwrites without a backup.")

    # OUTPUT FILLED COLUMNS
    parser.add_argument("-o:x",
                        action=StoreColumnsListAction, dest="skipping_columns", metavar="COLUMNS", default=('director',),
                        help=f"When all of the comma-separated list of columns are filled, no new information is " +
                             f"searched."
                             f"OPTIONS: {', '.join(sorted(AVAILABLE_COLUMNS))}.")

    # OUTPUT COLUMNS
    parser.add_argument("-o:c",
                        action=StoreColumnsListAction, dest="output_columns", metavar="COLUMNS",
                        default=DEFAULT_COLUMNS, help=f"comma-separated list of outputted columns. "
                                                      f"OPTIONS: {', '.join(sorted(AVAILABLE_COLUMNS))}. "
                                                      f"First column is always \"file name\". "
                                                      f"DEFAULT: \"{','.join(DEFAULT_COLUMNS)}\".")

    # OUTPUT DIVIDER
    parser.add_argument("-o:d",
                        action="store", dest="output_delimiter", default=",",
                        help="Output CSV columns delimiter, default=\",\".")

    # OUTPUT QUOT. MARKS
    parser.add_argument("-o:q",
                        action="store", dest="output_quot", default='"',
                        help="Output CSV quotation marks, default='\"' (double quote).")

    # OUTPUT FILE
    parser.add_argument('output',
                        action=ProtectFileOverwriteAction, metavar='OUTPUT_FILE',
                        help="Name of the output CSV file.")

    return parser.parse_args()
