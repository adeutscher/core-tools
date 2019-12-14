#!/bin/bash

# Common message functions.

set_colours(){
  # Define colours
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  NC='\033[0m' # No Color
}
[ -t 1 ] && set_colours

error(){
  printf "${RED}"'Error'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "${BLUE}"'Notice'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

# Script Function

home_escape(){
 sed "s|^${HOME}|\\~|g"
}

if [ -z "$1" ]; then
  error "No directories provided.";
  exit 1
fi

while [ -n "$1" ]; do
  if [ -d "$1" ]; then
    d="$(readlink -f "${1}")" # Convenient shorthand
    notice "$(printf "Checking in ${GREEN}%s/${NC} for dead symbolic links..."  "$(home_escape <<< "${d}")")"
    DIRS[${c}]="${d}"
    c="$((${c:-0}+1))"
  elif [ -f "${1}" ]; then
    error "$(printf "${GREEN}%s${NC} is a file, not a directory..." "$(home_escape <<< "${1}")")"
  else
    error "$(printf "${GREEN}%s${NC} does not seem to be a directory..." "$1")"
  fi
  shift
done

while [ "${i:-0}" -lt "${c:-0}" ]; do
  find "${DIRS[${i}]}" -xtype l
  i="$((${i:-0}+1))"
done | home_escape | sort | xargs -I{} printf "    {}\n"
