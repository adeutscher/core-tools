#!/bin/bash

#set -x

# This script shall:
#  - Report on successful authentications as a deduplicated list of usernames,
#      IP addresses, and method (password vs. publickey).
#  - Report on unsuccessful authentications (failed passwords) as a
#      deduplicated list of IP addresses, usernames, and total attempt numbers

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

process_failed_logins(){
  # Get a list of attempts that were unsuccessful.
  printf "Failed logins:\n"
  __get_all_file_contents $@ | grep -oP "Failed password for( invalid)? user [^ ]+ from [^ ]+" | awk -F' ' '{if($4=="invalid"){print $6" "$8}else{print $5" "$7}}' | sort | uniq -c | sort -rn
}

process_successful_logins(){
  # Get a list of users that were successful.
  printf "Successful logins:\n"
  __get_all_file_contents $@ | grep -oP "Accepted (password|publickey) for [^ ]+ from [^ ]+" | awk -F' ' '{ print $4" "$6" "$2}' | sort | uniq -c | sort -rn
}

# Secure log files are provided as arguments.
# Check for these arguments.
if ! (( $# )); then
  printf "Please provide path to secure files.\n"
  exit 1
fi

process_successful_logins $@
process_failed_logins $@
