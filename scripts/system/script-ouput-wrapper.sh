#!/bin/bash

# Some other scripts are sensitive to being temporarily truncated (e.g. my conky tasks display).
# Alternately, scripts like my conky tasks display could be interrupted if the script were to fail to run (no internet, in conky's case).
# This script will only replace the target file (argument 1) with the output of the script command
#     (arguments 2 and onwards) if the target command has any output to replace.

tempFile="$(mktemp)"
targetFile=$1
shift
if [ -n "$($@ | tee "$tempFile")" ]; then
  # Only replace file if there was content to replace it with.
  mv -f "$tempFile" "$targetFile"
else
  # Remove temp file, was not moved.
  rm -f "$tempFile"
fi
