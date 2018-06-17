#!/bin/bash

# Silly script to purge all .retry files from Ansible directory.
(( "${ANSIBLE:-0}" )) || cd "$(dirname "$(readlink -f "${0}")")"

while read retry; do
  [ -n "${retry}" ] || continue
  printf "Cleaning out file: %s\n" "$(readlink -f "${retry}")"
  rm "${retry}"
done <<< "$(find . -name '*.retry')"
