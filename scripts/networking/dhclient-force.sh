#!/bin/bash

#####################
# Message Functions #
#####################

# Define colours
BLUE='\033[1;34m'
GREEN='\033[1;32m'
RED='\033[1;31m'
YELLOW='\e[1;93m'
BOLD='\033[1m'
NC='\033[0m' # No Color

error(){
    printf "$RED"'Error'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

notice(){
    printf "$BLUE"'Notice'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

warning(){
    printf "$YELLOW"'Warning'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

####################
# Script Functions #
####################

root_or_rerun(){
    if [ "$EUID" -gt 0 ]; then
        sudo "$0" $@
        exit $?
    fi
}

check_environment(){

  # Arguments both as non-root in order to handle any input errors before we run root.
  handle_arguments $@

  if [ -z "$interface" ]; then
    error "$(printf "No interface provided. Usage: $GREEN%s$NC interface" "$(basename $0)")"
    exit 1
  fi

  if ! ip a s "$interface" 2> /dev/null >&2; then
    error "$(printf "The $BOLD%s$NC interface was not found. Quitting...\n" "$interface")"
    exit 2
  fi
  if nmcli device status 2> /dev/null | grep -v unmanaged | tail -n +2 | cut -d' ' -f1 | grep -q '^'$interface'$'; then
    error "$(printf "The $BOLD%s$NC interface is still being managed by NetworkManager. Quitting...\n" "$interface")"
    exit 3
  fi

}

clean_pid_file(){
    if [ -f "$pid_file" ]; then
        notice "$(printf "Removing old PID file: $GREEN%s$NC" "$pid_file")"
        rm "$pid_file"
        return $?
    fi
    return 0
}

fix_directory(){
  if [ -h "$0" ]; then
    cd "$(dirname "$(readlink -f "$0")")"
  else
    cd "$(dirname "$0")"
  fi
}

handle_arguments(){
  for opt in $(getopt ":a" $@); do 
    case "$opt" in
    "-a")
      address_only=1
      ;;
    *)
      interface=$opt
      ;;
    esac
  done
  unset opt

  pid_file="/var/run/dhclient-$interface.pid"

}

run_dhclient(){
  umask 077
    
  local dhclient_script=./dhclient-script.sh
  local short_options="subnet-mask, broadcast-address, host-name, interface-mtu"
  if [ -z "$address_only" ]; then
    notice "$(printf "Running ${BLUE}%s${NC} on ${BOLD}%s${NC}..." "dhclient" "$interface")"
    if [ -f "$dhclient_script" ]; then
      dhclient -sf "$dhclient_script" -pf "$pid_file" "$interface"
    else
      dhclient -pf "$pid_file" "$interface"
    fi
  else
    notice "$(printf "Running ${BLUE}%s${NC} on ${BOLD}%s${NC}... (address-only)" "dhclient" "$interface")"
    if [ -f "$dhclient_script" ]; then
      dhclient -sf "$dhclient_script" -pf "$pid_file" "$interface" --request-options "$short_options"
    else
      dhclient -pf "$pid_file" "$interface" --request-options "$short_options"
    fi

  fi
  return $?
}

kill_old_instance(){
  if [ -f "$pid_file" ] && pgrep "dhclient" | grep -q "^$(cat "$pid_file")$"; then
    # PID file exists, and a dhclient process is running at that PID from a previous run of this script..
    notice "Sending a kill signal to previous dhclient process."
    dhclient -x -pf "$pid_file"
  fi

  # Make sure that the PID file is gone, if it exists.
  clean_pid_file
}

check_environment $@
root_or_rerun $@
fix_directory
kill_old_instance
run_dhclient

