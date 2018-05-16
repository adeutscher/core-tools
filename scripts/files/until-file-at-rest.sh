#!/bin/bash

REST_INTERVAL=2

# Lazy script to wait for specified files to "come to rest" and no longer receive writes.
# A file has come "to rest" if one of the following is true:
# * The file has not increased in size in the number of seconds hard-coded in REST_INTERVAL.
# * The file is outright gone. This is considered to be a valid "at-rest"
#   state because of cases like .part files used by Firefox for downloads.
# However, this script is not able to provide any context for why a file has come to rest.

# For the moment, this script is not named "wait-for-at-rest" for the convenience
#   of tab-completion conflicts with its relative 'wait-for-pid.sh'.

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi

error(){
  printf "${RED}"'Error'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "${BLUE}"'Notice'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

warning(){
  printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __warning_count=$((${__warning_count:-0}+1))
}

get_size(){
  stat -c %s "${1}" 2> /dev/null || echo 0
}

# Validation
##

# Confirm that valid files were given and that they existed at the start of the script's running.
# Breaking our normal habit of using as many functions as possible to preserve integrity of paths with spaces.

if [ -z "${1}" ]; then
  error "No files provided."
  exit 1
fi

__count=0
while [ -n "${1}" ]; do
  # Assign to variable for convenience and so that we can conveniently shift immediately.
  __count="$((${__count}+1))"
  __file="${1}"
  shift

  if [ ! -f "${__file}" ]; then
    error "$(printf "Not a file: ${GREEN}%s${NC}" "${__file}")"
    continue
  fi
  notice "$(printf "Checking for file: ${GREEN}%s${NC}" "${__file}")"
  files[${__count}]="${__file}"
  sizes[${__count}]="$(get_size "${__file}")"
  finished[${__count}]="0"
done

(( "${__error_count:-0}" )) && exit 1

notice "$(printf "Waiting for ${BOLD}%d${NC} files to come to rest (check interval: ${BOLD}%s${NC} seconds)" "${__count}" "${REST_INTERVAL}")"

__complete=0

# Wait for files.
while [ "${__complete}" -lt "${__count}" ]; do
  __i=0;
  sleep "${REST_INTERVAL}"
  while [ "${__i}" -lt "${__count}" ]; do
    __i="$((${__i}+1))"
    # File has already been examined.
    (( "${finished[${__i}]}" )) && continue

    if [ ! -f "${files[${__i}]}" ]; then
      # File does not exist.
      # Making this a separate check mostly for the convenience of
      # someone who does not agree with my idea that a gone file
      # should not be error-worthy.
      finished[${__i}]=1
      __complete="$((${__complete}+1))"
      warning "$(printf "File gone: ${GREEN}%s${NC}" "${files[${__i}]}")"
      continue
    fi

    size="$(get_size "${files[${__i}]}")"
    if [ "${size}" -eq "${sizes[${__i}]}" ]; then
      finished[${__i}]=1
      __complete="$((${__complete}+1))"
      notice "$(printf "File at rest: ${GREEN}%s${NC}" "${files[${__i}]}")"
      continue
    fi
    sizes[${__i}]="${size}"
  done
done

