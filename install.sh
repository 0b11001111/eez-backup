#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# make backup.py executable
chmod +x "$DIR/backup.py"

# create link: /local/bin/backup -> ./backup.py
ln --symbolic --force "$DIR/backup.py" ~/.local/bin/backup

# deploy example config if none exists so far
if [ ! -f ~/.backup.yml ]; then
    echo "create example configuration at ~/.backup.yml"
    cp "$DIR/example_config.yml" ~/.backup.yml
fi