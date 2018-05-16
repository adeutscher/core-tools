#!/bin/bash

# Common message functions.

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi

error(){
  printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __warning_count=$((${__warning_count:-0}+1))
}

# Script functions

beep(){
  # Attempt to make a beep using the motherboard printer.
  # Useful for trying to announce that a task is done on a machine without other speakers.
  # This function will fail quietly if we have no motherboard speaker for whatever reason.
  if [ -w "/dev/tty1" ]; then
    # Default number
    local count=1
    local count_limit=25
    if grep -Pq "^\d{1,}$" <<< "$1" ; then
      if [ "$1" -le 0 ]; then
        local count=1
      elif [ "$1" -gt "$count_limit" ]; then
        # Cap out at a certain number of beeps to prevent accidental typos.
        # If you really want to beep over 15 times, call beep multiple times
        warning "$(printf "Capping beep count at ${BOLD}%s${NC}" "$count_limit")"
        local count=$count_limit
      else
        local count=$1
      fi
    fi
    local i=0
    while [ "$i" -lt "$count" ]; do
      echo -e "\07" > /dev/tty1
      local i=$(($i + 1))
      # Add a small beep to be able to tell individual beeps apart.
      sleep .1
    done
  else
    error "$(printf "${GREEN}%s${NC} is not writable. Cannot attempt a beep." "/dev/tty1")"
    return 1
  fi
}

beep $@
