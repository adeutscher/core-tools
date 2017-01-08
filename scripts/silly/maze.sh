#!/bin/bash

########################################################################
# File Name: maze.sh: Print out a silly maze with slashes/backslashes. #
#   Create a silly randomly-generated maze.                                  #
#   May or may not be possible to "solve".                             #
#   Originally suggested as a function on reddit, StackOverflow,       #
#   or similar, but I am unable to find the original thread.           #
########################################################################

# Define colours
if [ -t 1 ]; then
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi

error(){
  printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

handle-arguments(){
  while getopts "hr" OPT $@; do
    case "$OPT" in
    "h")
      help
      ;;
    "r")
      RAINBOW=1
      ;;
    esac
  done
}

help(){
cat << EOF
Usage: ./${0##*/} [-h] [-r]
  -h: Print this help screen and exit.
  -r: Rainbow mode
EOF
exit 0
}

handle-arguments $@

if (( $RAINBOW )); then
  while true; do (( RANDOM % 2 )) && echo -ne "\e[3$(( $RANDOM % 8 ))m╱" || echo -n ╲; sleep .05; done
else
  while true; do (( $RANDOM % 2 )) && echo -n / || echo -n \\; sleep 0.05; done
fi
