# eez-backup

Another convenience wrapper for [_restic_](https://restic.net/).

## Install

You can simply install `eez-backup` from PyPI via

```bash
python -m pip install eez-backup
```

## Setup

`eez-backup` assumes `backup.toml` to be present in your home directory, thus create it.
You can use [`tests/demo/config.toml`](./tests/demo/config.toml) as a template.

Now, you can initialize the _restic_ repositories by running

```bash
backup repo-map init
```

... and then back up your data by running

```bash
backup run
```

That's it!

## CLI interface

```text
usage: backup [-h] [-v] [-c] [-r] [-p] {run,repo-map,profile-map} ...

Another convenience wrapper for restic

positional arguments:
  {run,repo-map,profile-map}
                        commands
    run                 run backup and forget for all profiles
    repo-map            run any restic command for all given repositories
    profile-map         run any restic command for all given profiles

options:
  -h, --help            show this help message and exit
  -v, --verbose         log level (disables progress bars if set)
  -c , --config         config file to use, default is ~/.backup.toml
  -r , --repository     repository to use, use all repositories by default, can be used multiple times
  -p , --profile        profile to use, use all profiles by default, can be used multiple times
```

(`backup --help`)

### Glossary

- **Repositories:** refer to a target locations for your backups and map 1:1 to [_restic_ repositories](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html).
- **Profiles:** define a set of directories/files to be in-/excluded from a backup among other options. Per profile and
  backup a [snapshot](https://restic.readthedocs.io/en/stable/040_backup.html) is created.

