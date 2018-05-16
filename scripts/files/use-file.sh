#!/bin/bash

# A silly wrapper to open a file in a desktop environment as a file manager like Nautilus or Caja would.

[ -z "${1}" ] && exit 1

# Use gio to open.
command="gio open"
# An older system (CentOS) might not have gio available.
type gio 2> /dev/null >&2 || command="gvfs-open"

while [ -n "${1}" ]; do
  printf "Opening file: %s\n" "${1}"
  ${command} "${1}"
  shift
done
