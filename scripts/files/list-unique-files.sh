#!/bin/bash

# Author: Alan Deutscher
# A silly little script to print out files in two provided directories
#   that are not found in the other directory.
# I created this script to help me to get my desktop backgrounds folder back in sync across multiple machines.
# Note: This script does not currently track duplicate files within the same directory.

# Define colours
if [ -t 1 ]; then
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  NC='\033[0m' # No Color
fi

error(){
  printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __errors=$((${__errors:-0}+1))
}

get-listings(){
  while read __item; do
    md5sum "$__item"
  done <<< "$(find "$1" -type f)"
}

if [ -z "$2" ]; then
  error "Please specify two directories."
  exit 1
fi

if ! [ -d "$1" ]; then
  error "$(printf "First argument not a directory: ${GREEN}%s${NC}" "$1")"
fi

if ! [ -d "$2" ]; then
  error "$(printf "Second argument not a directory: ${GREEN}%s${NC}" "$2")"
fi

if [ "$1" -ef "$2" ]; then
  error "$(printf "Arguments point to same directory: ${GREEN}%s${NC} & ${GREEN}%s${NC}" "$1" "$2")"
fi

if (( ${__errors:-0} )); then
  exit 1
fi


listings_a=$(mktemp)
get-listings "$1" > "$listings_a"
listings_b=$(mktemp)
get-listings "$2" > "$listings_b"

# Page through duplicate candidates.
for c in $(cut -d' ' -f1 < "$listings_a"); do
  if grep -qw "^$c" "$listings_b"; then
    # Only remove from list A if there's a matching counterpart in list B.
    sed -i '/^'$c'/d' "$listings_a"
  fi
  sed -i '/^'$c'/d' "$listings_b"
done

cat "$listings_a" "$listings_b" | cut -d' ' -f3-
rm "$listings_a" "$listings_b"
