#!/usr/bin/env python3
import os
import sys
import enum
import glob
import json
import pprint
import argparse
import subprocess
from yaml import load
from pathlib import Path
from itertools import chain
from collections import OrderedDict
from contextlib import contextmanager
from tempfile import NamedTemporaryFile

try:
    from yaml import CLoader as Loader

except ImportError:
    from yaml import Loader


class Colors(enum.Enum):
    NONE = '\033[0m'

    # TODO formatting
    FB = '\033[1m'
    FU = '\033[4m'

    # normal colors
    K = '\033[0;30m'	# dark black
    R = '\033[0;31m'	# dark red
    G = '\033[0;32m'	# dark green
    Y = '\033[0;33m'	# dark yellow (brown)
    B = '\033[0;34m'	# dark blue
    M = '\033[0;35m'	# dark magenta
    C = '\033[0;36m'	# dark cyan
    W = '\033[0;37m'	# dark white (L.gray)

    # bright (emphasized) colors
    EK = '\033[1;30m'		# bright black (D.gray)
    ER = '\033[1;31m'		# bright red
    EG = '\033[1;32m'		# bright green
    EY = '\033[1;33m'		# bright yellow
    EB = '\033[1;34m'		# bright blue
    EM = '\033[1;35m'		# bright magenta
    EC = '\033[1;36m'		# bright cyan
    EW = '\033[1;37m'		# bright white

    # background colors
    BK = '\033[40m'	# black
    BR = '\033[41m'	# red
    BG = '\033[42m'	# green
    BY = '\033[43m'	# yellow (brown)
    BB = '\033[44m'	# blue
    BM = '\033[45m'	# magenta
    BC = '\033[46m'	# cyan
    BW = '\033[47m'	# white (L.gray)

    def escape(self, s):
        none = type(self).NONE.value
        return f'{self.value}{s}{none}' if not s.endswith(none) else f'{self.value}{s}'


def fmt(s, *args):

    for arg in args:
        for flag in str(arg).split(','):
            s = Colors[flag.strip()].escape(s)

    return s


@contextmanager
def cd(path):
    cwd = os.getcwd()
    os.chdir(os.path.expanduser(path))

    try:
        yield cwd

    finally:
        os.chdir(cwd)


# TODO this is a bit overkill and should be replaced by good old dictionaries
class NameSpaceDict(dict):
    """A dictionary class whose members can be accessed as attributes."""
    @staticmethod
    def _mapping(*args, **kwargs):
        state = {}

        for arg in args:
            state.update(arg)

        state.update(kwargs)

        for key, value in state.items():
            yield key, NameSpaceDict(value) if isinstance(value, dict) else value

    def __init__(self, *args, **kwargs):
        super().__init__(self._mapping(*args, **kwargs))

    def __setitem__(self, key, value):
        super().__setitem__(key, NameSpaceDict(value) if isinstance(value, dict) else value)

    def __getattr__(self, item):
        try:
            return self.__getitem__(item)

        except KeyError as error:
            raise AttributeError(error)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)


class Unit:
    def __init__(self, tag, base, environment, repository, include, exclude=(), clean_policy=None, **kwargs):
        self._tag = tag
        self._base = base
        self._environment = NameSpaceDict(os.environ)
        self._repository = repository
        self._include = list(include)
        self._exclude = list(exclude)
        self._clean_policy = clean_policy

        self._environment.update(environment)

    def __str__(self):
        return f'{type(self).__name__}({self._repository}#{self._tag})'

    @classmethod
    def factory(cls, config):
        for tag, params in config.units.items():
            params = {**config.globals, **params}

            for repository in params.pop('repositories'):
                if repository in config.repositories:
                    yield cls(
                        tag=tag,
                        base=os.path.expanduser('~/'),
                        environment=config.repositories[repository],
                        repository = repository,
                        **params
                    )

    @property
    def repository(self):
        return self._repository

    def execute(self, *args):
        with cd(self._base):
            return subprocess.run(['restic', *args], capture_output=True, env=self._environment).returncode

    def online(self):
        return self.execute('snapshots', '--json')

    def backup(self, expand=False):
        with NamedTemporaryFile(mode='rt+') as incl, NamedTemporaryFile(mode='rt+') as excl:
            incl.write('\n'.join(self._include))
            excl.write('\n'.join(self._exclude))

            incl.flush()
            excl.flush()

            return self.execute('backup', '-q', '--tag', self._tag, '--files-from', incl.name, '--exclude-file', excl.name)

    def clean(self, silent=True):
        if not self._clean_policy:
            return 1
        return self.execute('forget', '--tag', self._tag, *map(str, chain(*self._clean_policy.items())))


def restic(config, args):
    status = 0

    for i, (name, environment) in enumerate(config.repositories.items(), start=1):
        print(f'[{i}/{len(config.repositories)}] {fmt(name, "FB")}')
        status = max(status, subprocess.run(['restic', *args.args], env={**os.environ, **environment}).returncode)

    return status


def backup(config, args):
    status = 0
    online = set()
    units = list(Unit.factory(config))
    methods = OrderedDict(
        backup=Unit.backup,
        clean=Unit.clean
    )

    print('check repositories')
    for i, (name, environment) in enumerate(config.repositories.items(), start=1):
        print(f'[{i}/{len(config.repositories)}] check: {name} ({environment.RESTIC_REPOSITORY})', end=' ', flush=True)

        cmd = ('restic', 'snapshots', '-q')
        if subprocess.run(cmd, capture_output=True, env={**os.environ, **environment}).returncode == 0:
            print(fmt('online', 'G'))
            online.add(name)

        else:
            print(fmt('offline', 'Y'))
    
    if online:
        for mname, method in methods.items():
            print()
            for i, unit in enumerate(units, start=1):
                print(f'[{i}/{len(units)}] {mname}:', unit, end=' ', flush=True)

                if unit.repository not in online:
                    print(fmt('skip', 'Y'))
                    continue

                rc = method(unit)
                status = max(status, rc)

                print(fmt('ok', 'G') if rc == 0 else fmt('failed', 'R'))

    print(f'\nexit {status}')
    return status


if __name__ == '__main__':
    # cli
    parser = argparse.ArgumentParser(description='convenience wrapper for restic')
    parser.add_argument(
        '-c', '--config', type=str, default='~/.backup.yml', metavar='',
        help='configuration file to use, default is ~/.backup.yml'
    )
    parser.add_argument(
        '-r', '--repository', action='append', type=str, metavar='',
        help='repositories to use, default is to use all repositories'
    )

    subparsers = parser.add_subparsers(required=True, help='commands')

    run_parser = subparsers.add_parser('run', help='run the backup')
    run_parser.set_defaults(func=backup)

    map_parser = subparsers.add_parser('map', help='execute a restic command for all repositories')
    map_parser.add_argument('args', nargs=argparse.REMAINDER)
    map_parser.set_defaults(func=restic)

    args = parser.parse_args()
    
    # load config
    with Path(args.config).expanduser().open(mode='rt') as f:
        config = NameSpaceDict(load(f, Loader=Loader))

    # manipulate config with respect to cli arguments
    if args.repository:
        try:
            config.repositories = {r: config.repositories[r] for r in args.repository}

        except KeyError as err:
            raise ValueError(f'unknown repository {err}, choose one of: {list(config.repositories)}')

    # execute
    sys.exit(args.func(config, args))
