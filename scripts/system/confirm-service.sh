#!/bin/bash

CMD=systemctl
SERVICE="${1}"

if (( "${EUID}" )); then
  if [ -t 1 ]; then
    echo "Must run as root."
  fi
  exit 1
elif [ -z "${SERVICE}" ]; then
  if [ -t 1 ]; then
    echo "No service specified."
  fi
  exit 1
fi

$CMD start "${SERVICE}"
