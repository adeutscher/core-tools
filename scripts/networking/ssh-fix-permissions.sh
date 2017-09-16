#!/bin/bash

# Common message functions.

# Define colours
if [ -t 1 ]; then
  GREEN='\033[1;32m'
  BLUE='\033[1;34m'
  BOLD='\033[1m'
  RED='\033[1;31m'
  NC='\033[0m' # No Color
fi

error(){
  printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __error_count=$((${__error_count:-0}+1))
}

# Script commands

get_fix_functions(){
  # Gather commands.
  for path in $(echo $PATH | sed 's/\:/\ /g'); do
    # Note: Using redirection of ls is much faster than BASH wildcards was.
    for command in $(ls $path 2> /dev/null); do
      echo $command
    done
  done | grep "ssh-fix-permissions-" | sort
}

# Script flow

tools="$(get_fix_functions)"

if [ -z "$tools" ]; then
  # No fixer functions detected.
  exit 1
fi

__total=0
__failed=0
for permissionFunction in $tools; do
  __total=$(($__total+1))
  if ! "$permissionFunction"; then
    error "$(printf "SSH permission fix command failed: ${BLUE}%s${NC}" "$permissionFunction")"
    __failed=$(($__failed+1))
  fi
done

if (( $__failed )); then
  error "$(printf "Errors with ${BOLD}%d${NC}/${BOLD}%d${NC} SSH functions." "$__failed" "$__total")"
fi
