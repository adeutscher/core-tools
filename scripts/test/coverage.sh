#!/bin/bash

cd "$(dirname "${0}")"

limit=5

if ! timeout $limit coverage erase; then
  echo "Failed to clear coverage data."
  exit 1
fi
if ! timeout $((limit * 5)) coverage run --omit="/usr*" ./run.py; then
  echo "Failed to run unit tests.."
  echo "If run.py passes on its own but coverage fails, then we may need to increase the coverage script's timeout limit."
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
