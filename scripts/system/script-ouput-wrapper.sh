#!/bin/bash

# Some other scripts are sensitive to being temporarily truncated (e.g. my conky tasks display).
# Alternately, scripts like my conky tasks display could be interrupted if the script were to fail to run (no internet, in conky's case).
# This script will only replace the target file (argument 1) with the output of the script command
#     (arguments 2 and onwards) if the target command has any output to replace.

set -x
tempFile=$(mktemp)
targetFile=$1
shift 
if [ -n "$($@ | tee "$tempFile")" ]; then
  mv -f "$tempFile" "$targetFile"
fi
