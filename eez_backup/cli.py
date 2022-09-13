import argparse
import asyncio
import logging
import os
import sys
from argparse import Namespace
from collections import defaultdict
from contextlib import ExitStack, contextmanager
from functools import reduce
from pathlib import Path
from typing import Iterable, ContextManager, Callable

from rich.logging import RichHandler
from yaml import load

from eez_backup.command import CommandSequence, Status
from eez_backup.common import Env
from eez_backup.config import Config
from eez_backup.monitor import ProgressMonitor, Monitor, LoggerMonitor
from eez_backup.profile import Profile

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


@contextmanager
def monitor_factory() -> ContextManager[Callable[[str], Monitor]]:
    if logging.getLogger().level > logging.INFO:
        with ProgressMonitor.default_progress() as progress:
            yield lambda name: ProgressMonitor(name, progress, 0.8)
    else:
        yield lambda name: LoggerMonitor(name)


async def map_repositories(profiles: Iterable[Profile], args, *_, **__) -> Status:
    try:
        index = args.index("repo-map") + 1
        args = args[index:]
    except ValueError:
        ValueError(f"Malformed command {args}")

    with monitor_factory() as new_monitor:
        tasks = []
        repositories = {p.repository for p in profiles}
        for repository in repositories:
            sequence = CommandSequence()
            sequence.add_command(repository.base_command(*args))
            tasks.append(sequence.exec(monitor=new_monitor(repository.tag), capture_output=True))

        return reduce(Status.__add__, await asyncio.gather(*tasks), Status())


async def map_profiles(profiles: Iterable[Profile], args, *_, **__) -> Status:
    try:
        index = args.index("profile-map") + 1
        args = args[index:]
    except ValueError:
        ValueError(f"Malformed command {args}")

    profile_groups = defaultdict(list)
    for profile in profiles:
        profile_groups[profile.repository].append(profile)

    with monitor_factory() as new_monitor:
        tasks = []
        for repository, profiles_ in profile_groups.items():
            sequence = CommandSequence()

            for profile in profiles_:
                sequence.add_command(profile.base_command(*args))

            tasks.append(sequence.exec(monitor=new_monitor(repository.tag), capture_output=True))

        return reduce(Status.__add__, await asyncio.gather(*tasks), Status())


async def backup(profiles: Iterable[Profile], *_, **__) -> Status:
    profile_groups = defaultdict(list)
    for profile in profiles:
        profile_groups[profile.repository].append(profile)

    with ExitStack() as stack, monitor_factory() as new_monitor:
        tasks = []
        for repository, profiles_ in profile_groups.items():
            sequence = CommandSequence()

            sequence.add_command(repository.online_cmd(), ignore_error=True)
            for profile in profiles_:
                sequence.add_command(stack.enter_context(profile.backup_cmd_context()))
                sequence.add_command(profile.clean_cmd())

            tasks.append(sequence.exec(monitor=new_monitor(repository.tag), capture_output=True))

        return reduce(Status.__add__, await asyncio.gather(*tasks), Status())


def parse_args(argv=None) -> Namespace:
    parser = argparse.ArgumentParser(description="Another convenience wrapper for restic")
    parser.add_argument(
        "-v", "--verbose", action="count", help="log level (disables progress bars if set)"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("~/.backup.yml").expanduser(),
        metavar="",
        help="config file to use, default is ~/.backup.yml",
    )
    parser.add_argument(
        "-r",
        "--repository",
        action="append",
        type=str,
        metavar="",
        help="repository to use, use all repositories by default, can be used multiple times",
    )
    parser.add_argument(
        "-p",
        "--profile",
        action="append",
        type=str,
        metavar="",
        help="profile to use, use all profiles by default, can be used multiple times",
    )

    subparsers = parser.add_subparsers(required=True, help="commands")

    run_parser = subparsers.add_parser("run", help="run backup and forget for all profiles")
    run_parser.set_defaults(func=backup)

    map_repositories_parser = subparsers.add_parser(
        "repo-map", help="run any restic command for all given repositories"
    )
    map_repositories_parser.add_argument("args", nargs=argparse.REMAINDER)
    map_repositories_parser.set_defaults(func=map_repositories)

    map_profiles_parser = subparsers.add_parser(
        "profile-map", help="run any restic command for all given profiles"
    )
    map_profiles_parser.add_argument("args", nargs=argparse.REMAINDER)
    map_profiles_parser.set_defaults(func=map_profiles)

    return parser.parse_args(argv)


def verbosity_to_loglevel(verbosity: int | None = None) -> str:
    level = max(logging.DEBUG, logging.WARNING - max(verbosity or 0, 0) * 10)
    return logging.getLevelName(level)


def cli(argv=None) -> int:
    argv = argv or sys.argv[1:]
    args = parse_args(argv)

    logging.basicConfig(format="%(message)s", datefmt="[%X]", handlers=[RichHandler()])
    logging.getLogger().setLevel(verbosity_to_loglevel(args.verbose))
    logging.debug(f"{args=}")

    # load config
    with args.config.expanduser().open(mode="rt") as f:
        config = Config.parse_obj(load(f, Loader=Loader))

    logging.debug(config.json())

    # compile and filter profiles
    profiles = list(
        config.compile_profiles(
            repository_defaults=dict(env=Env(os.environ)),
            profile_defaults=dict(base=args.config.parent.absolute()),
        )
    )
    logging.debug(profiles)

    if selection := args.repository:
        logging.info(f"filter repositories: {set(selection)}")
        profiles = [p for p in profiles if p.repository.tag in selection]

    if selection := args.profile:
        logging.info(f"filter profiles: {set(selection)}")
        profiles = [p for p in profiles if p.tag in selection]

    if not profiles:
        logging.warning(f"no profiles specified")
        return 1

    async def cmd():
        status = await args.func(profiles, argv)
        if status.is_err():
            for i, message in enumerate(status.messages, start=1):
                logging.error(f"{i}: {message!r}")
        return status.code

    return asyncio.run(cmd())
