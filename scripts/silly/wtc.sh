#!/bin/bash

##########################################################################
# File Name: wtc.sh: Scrape wacky commit messages from whatthecommit.com #
##########################################################################

# Stream timing
DEFAULT_TIMING=5
# Set a ground floor to timing in order to be kind to WTC servers.
MINIMUM_TIMING=2

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi

check-commands(){
  # Check for required commands
  if ! type curl 2> /dev/null >&2; then
    error "$(printf "$BLUE%s$NC was not found!" "curl")"
    exit 1
  fi
}

check-int(){
  if [ -z "$1" ] || ! grep -P "^\d*$" <<< "$1"; then
    return 1
  fi
}

error(){
  printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

handle-arguments(){
  while getopts "hst:" OPT $@; do
    case "$OPT" in
    "h")
      help
      ;;
    "s")
      STREAM=1
      ;;
    "t")
      if check-int "$OPTARG"; then
        if [ "$OPTARG" -ge $MINIMUM_TIMING ]; then
          TIMING="$OPTARG"
        else
          error "$(printf "Stream timing cannot be less than $BOLD%s$NC." "$MINIMUM_TIMING")"
          help
        fi
      else
        error "Stream timings must be expressed as an integer."
        help
      fi
      ;;
    esac
  done
}

help(){
cat << EOF
Usage: ./${0##*/} [-h] [-s [-t TIMING]]
  -h: Print this help screen and exit.
  -s: Stream mode, continually print messages
  -t time: Time interval when in stream mode (Default: 5)
EOF
exit 0
}

# What-The-Commit is a site that has random silly commit quotes.
wtc(){
  local src="http://whatthecommit.com/"
  # Adding in a catch-all grep for "." to give us a non-zero error code for empty content.
  if ! curl -s "${src}" | grep '<div id="content">' -A 1 | tail -n 1 | sed 's/<p>//' | grep --colour=none "."; then
    # Being unable to get content probably means a networking problem on our end.
    # Less likely, the site has changed its layout and needs to be revisited.
    # Even less likely, the site is gone altogether.
    error "$(printf "Unable to get commit content. Is ${GREEN}%s${NC} reachable?" "${src}")"
    exit 1
  fi
}

# Constantly print out wtc quotes.
wtc-stream(){
  while wtc; do sleep 5; done
}

check-commands
handle-arguments $@

if (( STREAM )); then
  while wtc; do
    sleep ${TIMING:-$DEFAULT_TIMING}
  done
else
  # One and done
  wtc
fi
