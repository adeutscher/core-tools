#!/bin/bash

cd "$(dirname "${0}")"

limit=5

if ! timeout $limit coverage erase; then
  echo "Failed to clear coverage data."
  exit 1
fi
if ! timeout $limit coverage run --omit="/usr*" ./run.py; then
  echo "Failed to run unit tests.."
  exit 1
fi
if ! timeout $limit coverage html --omit="/usr*"; then
  echo "Failed to print coverage report."
  exit 1
fi
if ! timeout $limit coverage report; then
  echo "Failed to print coverage report."
  exit 1
fi

dirPath="htmlcov/index.html"

printf "Coverage report generated at %s/%s\n" "$(pwd)" "${dirPath}"
