import argparse
import os
from pathlib import Path


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
            raise argparse.ArgumentError(self, "Not a directory: {0}".format(path.absolute()))
        return super().action(parser, namespace, path, option_string)


class EnsureDirectoryAction(SimpleAction):
    def action(self, parser, namespace, value, option_string=None):
        path = Path(value)
        if path.exists() and not path.is_dir():
            raise argparse.ArgumentError(self, "Not a directory: {0}".format(path.absolute()))
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
                raise argparse.ArgumentError(self, 'error reading {value}: {e}'.format(value=value, e=e))

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
