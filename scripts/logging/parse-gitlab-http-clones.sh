#!/bin/bash

#set -x

# This script shall:
#   Report on IPs that are implied to have performed a successful git checkout from GitLab over HTTP(s).

__get_all_file_contents(){
  for __file in $@; do
    if ! [ -f "$__file" ]; then
      printf "File not found: %s\n" "$__file"
      continue
    fi
    unset __sudo
    if [[ "$__file" =~ \.gz ]]; then
      local __command=zcat
    else
      local __command=cat
    fi
    if (( $EUID )) && ! [ -r "$__file" ]; then
      __sudo="sudo"
    fi
    $__sudo $__command "$__file"
  done

}

process_checkouts(){
  # Get a list of attempts that were unsuccessful.
  printf "Overview of HTTP(s) checkouts implied in provided log files:\n"
  while read __entry; do
    ip=$(cut -d' ' -f 1 <<< "$__entry")
    repo="$(grep -oP "POST.*git-upload-pack" <<< "$__entry" | sed -r -e 's/POST(\ |\t)+//g' -e 's/\.git\/git-upload-pack/.git/g')"
    printf "%s %s\n" "$ip" "$repo"
  done <<< "$(__get_all_file_contents $@ | grep POST | grep git-upload-pack)" | sort | uniq -c | awk -F' ' '{printf "%-15s %02d %s\n", $2, $1, $3}' | sort -n -t . -k 1,1 -k 2,2 -k 3,3 -k 4,4
}

# Secure log files are provided as arguments.
# Check for these arguments.
if ! (( $# )); then
  printf "Please provide path to GitLab access log files.\n"
  exit 1
fi

process_checkouts $@
