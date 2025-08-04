import os
import shutil
from contextlib import closing
from pathlib import Path
from typing import Generator

import pytest
import secretstorage

from eez_backup.cli import cli


@pytest.fixture
def enter_test_directory() -> Generator[Path, None, None]:
    current_working_directory = os.getcwd()
    test_directory = Path(__file__).parent.resolve()
    os.chdir(test_directory)

    try:
        yield test_directory

    finally:
        os.chdir(current_working_directory)


@pytest.fixture
def keyring():
    attributes = dict(app_id="eu.luoc.eez-backup", app_mode="demo")

    with closing(secretstorage.dbus_init()) as connection:
        collection = secretstorage.get_default_collection(connection)
        collection.unlock()

        collection.create_item("eez-backup demo", attributes, b"DemoPassword1")

        yield None

        for item in collection.search_items(attributes):
            item.delete()


@pytest.fixture
def setup_repositories():
    root = Path("/tmp")
    repository_1 = root / "test_repository_1"
    repository_2 = root / "test_repository_2"

    shutil.rmtree(repository_1, ignore_errors=True)
    shutil.rmtree(repository_2, ignore_errors=True)

    assert cli("-v -c demo/config.toml repo-map init".split()) == 0

    yield None

    shutil.rmtree(repository_1)
    shutil.rmtree(repository_2)


def test_end2end(enter_test_directory, keyring, setup_repositories):
    cli("-v -c demo/config.toml run".split())
    cli("-v -c demo/config.toml profile-map forget".split())
