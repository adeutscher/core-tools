#!/bin/bash

# Make a QR code for scanning in with a barcode reader app on an Android/iOS/etc device.
# TODO: Make ImageMagick put the SSID below the QR code.

# Functions
############

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

notice(){
  printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

success(){
  printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

# Script-specific functions

check-commands(){
  # Check for required commands
  if ! type qrencode 2> /dev/null >&2; then
    error "$(printf "$BLUE%s$NC was not found!" "qrencode")"
    exit 1
  fi
}

check-password(){
  if [ -n "$1" ]; then

    len="$(expr length "$1")"
    if [ "$len" -lt 8 ]; then
      error "WPA passwords must be 8 characters or longer (max: 63)."
      return 1
    fi

    if [ "$len" -gt 63 ]; then
      error "WPA passwords must be 63 characters or shorter (min: 8)."
      return 1
    fi
    return 0
  fi
  return 1
}

check-ssid(){
  if [ -n "$1" ]; then

    len="$(expr length "$1")"

    if [ "$len" -gt 63 ]; then
      error "WiFi SSIDs cannot be longer than 32 characters."
      return 1
    fi
    return 0
  fi
}

handle-arguments(){
  while getopts "hp:s:" OPT $@; do
    case "$OPT" in
    "h")
      help
      ;;
    "p")
      if check-password "$OPTARG"; then
        password="$OPTARG"
      fi
      ;;
    "s")
      if check-ssid "$OPTARG"; then
        ssid="$OPTARG"
      fi
      ;;
    esac
  done
}

help(){
cat << EOF
Usage: ./${0##*/} [-h] [-p PASSWORD] [-s SSID]
  -h: Print this help screen and exit.
  -p: Get the password as a command line argument (not recommended).
  -s: Set SSID via command line.
Note: If the SSID/password are not given as arguments, then you will be prompted to enter them."
EOF
exit 0
}


sanitize(){
  if [ -n "$1" ]; then
    sed -r "s/([\\;])/\\\1/g" <<< "$1"
  fi
}

# Script Content
#################

printf "This script makes a QR code for connecting to a WPA(2) network.\n"

check-commands
handle-arguments $@

while [ -z "$ssid" ]; do
  read -p "Input SSID: " ssid

  if ! check-ssid "$ssid"; then
    password=""
  fi

done

while [ -z "$password" ]; do
  read -p "Input Password: " -s password
  # Don't future notices on the same line as the password prompt.
  printf "\n"

  if ! check-password "$password"; then
    password=""
  fi

done


filepath="$(date +"$HOME/temp/wifi-%s.png")"

notice "$(printf "Saving QR helper for the \"$BOLD%s$NC\" network to $GREEN%s$NC" "$ssid" "$filepath")"

qrencode "$(printf "WIFI:T:WPA;S:%s;P:%s;;" "$(sanitize "$ssid")" "$(sanitize "$password")")" -o "$filepath"
