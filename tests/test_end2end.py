import shutil
from contextlib import closing
from pathlib import Path

import pytest
import secretstorage

from eez_backup.cli import cli


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
def repositories():
    root = Path("/tmp")
    repository_1 = root.joinpath("demo_repository_1")
    repository_2 = root.joinpath("demo_repository_2")

    shutil.rmtree(repository_1, ignore_errors=True)
    shutil.rmtree(repository_2, ignore_errors=True)

    assert cli("-v -c demo/config.toml repo-map init".split()) == 0

    yield None

    shutil.rmtree(repository_1)
    shutil.rmtree(repository_2)


def test_end2end(keyring, repositories):
    cli("-v -c demo/config.toml run".split())
    cli("-v -c demo/config.toml profile-map forget".split())
