import os
import re
import shutil
import sys
from pathlib import Path

from unidecode import unidecode


def progress_bar(iteration: int, total: int, prefix='', suffix='', decimals=0, fixed_size=None, fill='█'):
    iteration = min(iteration, total)
    pct_pad = 3 + decimals + (1 if decimals > 0 else 0)
    percent = ("{}".format("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total))).rjust(pct_pad))
    styling = '{prefix} [{fill}] {percent} % {suffix}'.format(prefix=prefix, fill=fill, percent=percent, suffix=suffix)
    length = fixed_size

    if fixed_size is None:
        cols, _ = shutil.get_terminal_size(fallback=(100, 1))
        length = cols - len(styling)

    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write('\r\x1b[J%s' % styling.replace(fill, bar))


def log(message=None, total=None, counter=None):
    if message is not None:
        sys.stdout.write("\033[F\r\033[J")
        sys.stdout.write('{}\n'.format(message))

    if total is not None:
        if counter is None:  # None is used to initialize progress bar
            counter = 0

        progress_bar(iteration=counter, total=total,
                     prefix="Processing {} of {}".format(str(counter).rjust(len(str(total))), total))

    if total is None and message is None:
        sys.stdout.write('\n')


def tokenize_string(source: str, stop_words=None) -> list:
    source = unidecode(source).lower()
    if re.match(r'.+\.\w{2,4}$', source):
        file_name = os.path.basename(source)
        source = os.path.splitext(file_name)[0]

    dividers = re.compile(r'[^\w]+', re.MULTILINE | re.UNICODE)

    list_of_words = dividers.sub(' ', source).split()
    return list(filter(lambda x: x not in stop_words, list_of_words) if stop_words is not None else list_of_words)


def backup_rename(original_file_name, count=0):
    def fname(i):
        return "{fn}.bak{suff}".format(fn=original_file_name, suff='.{0}'.format(i) if i else '')

    backup = Path(fname(count))
    if backup.is_file():
        backup_rename(original_file_name, count + 1)

    target = Path(fname(count - 1)) if count > 0 else Path(original_file_name)
    target.rename(backup)


def str_pct(num):
    return str(round(num * 100))


def print_dict_as_table(data):
    row_format = " | {:<20} | {:>10} | "
    print(' ' + '_' * 37)
    print(row_format.format("key", "value"))
    print((' | ' + '-' * 20 + ' | ' + '-' * 10) + ' | ')
    for item in data.items():
        print(row_format.format(*item))
    print((' | ' + '-' * 20 + ' | ' + '-' * 10) + ' | ')
