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
  __error_count=$((${__error_count:-0}+1))
}

# A more strongly phrased error (error also implies more of a misconfiguration).
alert(){
  printf "$RED"'ALERT'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __alert_count=$((${__alert_count:-0}+1))
}

notice(){
  printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

success(){
  printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __warning_count=$((${__warning:-0}+1))
}

# Script functions

check_shellshock(){    
    if env x='() { :;}; echo vulnerable' bash -c "echo Testing" | grep -q "vulnerable"; then
        alert "$(printf "Server is vunerable to ${BOLD}%s${NC} (${BOLD}%s${NC})." "ShellShock" "CVE-2014-6271")"
    else
        success "$(printf "Server is not vunerable to ${BOLD}%s${NC} (${BOLD}%s${NC})." "ShellShock" "CVE-2014-6271")"
    fi
}

check_shellshock
