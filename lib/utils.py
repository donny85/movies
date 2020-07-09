import os
import re
import shutil
import sys

from unidecode import unidecode


def progress_bar(iteration: int, total: int, prefix='', suffix='', decimals=0, fixed_size=None, fill='█'):
    if iteration > total:
        iteration = total
    pct_pad = 3 + decimals + (1 if decimals > 0 else 0)
    percent = ("{}".format("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total))).rjust(pct_pad))
    styling = '%s [%s] %s%% %s' % (prefix, fill, percent, suffix)
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


def string_tokens(source: str, stop_words=None):
    source = unidecode(source).lower()
    if re.match(r'.+\.\w{2-4}$', source):
        file_name = os.path.basename(source)
        source = os.path.splitext(file_name)[0]

    dividers = re.compile(r'[^\w]+', re.MULTILINE | re.UNICODE)

    list_of_words = dividers.sub(' ', source).split()
    return list(filter(lambda x: x not in stop_words, list_of_words) if stop_words is not None else list_of_words)
