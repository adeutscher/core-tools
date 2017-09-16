#!/bin/bash

# A lazy script to run multiple setup aspects at once.
# Not combining them only for organizational purposes.

cd "$(dirname "$(readlink -f "$0")")"

for s in setup-tools.sh tmux-configuration.sh crontab-setup.sh; do
  echo "Running $s"
  ./$s
done
