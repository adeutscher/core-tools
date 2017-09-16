#!/bin/bash

# Generic script for updating file permissions.

if [ -z "$1" ] || [ ! -d "$1" ]; then
  exit 1
fi

# $1 is assumed to be to a directory of SSH resources.
# * All files should be set to 600 (RW for owner only)
# * All directories should be set to 700 (Access for owner only)
# Don't nuke any sub-folders, process them separately
find "$1" -type d 2> /dev/null | xargs -I{} chmod 700 "{}" 2> /dev/null
find "$1" -type f 2> /dev/null | xargs -I{} chmod 600 "{}" 2> /dev/null

# Make sure that file ownership is right on Windows.
# Added after problems with ownership and TortoiseSVN on Windows via MobaXterm.
if [ -n "$WINDIR" ]; then
  chown $USERNAME -R ${1}/* 2> /dev/null
fi

