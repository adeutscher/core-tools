#!/bin/bash

# Set favoured MATE keybinds across all active MATE sessions.
# Reminder: To add additional keybinds, the easiest method is
#   to watch for writes using the following command:
# dconf watch /

KEYBINDS="$(cat << EOF
/org/mate/settings-daemon/plugins/media-keys/www            <Primary><Alt>f
/org/mate/marco/global-keybindings/run-command-terminal     <Primary><Alt>t
/org/mate/settings-daemon/plugins/media-keys/home           <Mod4>e
/org/mate/pluma/insert-spaces                               true
/org/gnome/desktop/wm/preferences/mouse-button-modifier
EOF
)"

# Common message functions.

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  PURPLE='\033[1;95m'
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

question(){
  unset __response
  while [ -z "${__response}" ]; do
    printf "$PURPLE"'Question'"$NC"'['"$GREEN"'%s'"$NC"']: %s: ' "$(basename $0)" "${1}"
    [ -n "${2}" ] && local __o="-s"
    read ${__o} -p "" __response
    [ -n "${2}" ] && printf "\n"
    if [ -z "${__response}" ]; then
      error "Empty input."
      # Negate error increment, not a true error
      __error_count=$((${__error_count:-0}-1))
    fi
  done
}

success(){
  printf "${GREEN}"'Success'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __warning_count=$((${__warning_count:-0}+1))
}

# Script functions

backup_env(){
  # Preserve old value of DBUS_SESSION_BUS_ADDRESS to re-export after the script is complete.
  if [ -n "$DBUS_SESSION_BUS_ADDRESS" ]; then
    __old_dbus="$DBUS_SESSION_BUS_ADDRESS"
  fi
}

restore_env(){
  if [ -n "$__old_dbus" ]; then
    export DBUS_SESSION_BUS_ADDRESS="$__old_dbus"
  else
    unset DBUS_SESSION_BUS_ADDRESS
  fi
}

set_env(){

  # Replace old environment variables.

  # If a PID was not provided, get one from the first session that pgrep finds.
  pid=${1:-$(pgrep -U "$(whoami)" '(gnome|mate)-session' | head -n1)}

  # mate-session and gnome-session are reliable processes to search for to get our D-Bus session from.
  if [ -n "$pid" ] && [ -r "$/proc/${pid}/environ" ]; then
    environmentType=$(ps -p $pid -o cmd= | sed 's/-session$//g')
    export $(</proc/$pid/environ tr \\0 \\n | grep -E '^DBUS_SESSION_BUS_ADDRESS=')
  fi
}

set_key(){
  if [ -z "${1}" ] || [ -z "${2}" ]; then
    return 1
  fi

  local old_val="$(dconf read "${1}")"

  if grep -Pq "^(\d+|true|false)$" <<< "${2}"; then
    local val="${2}"    
  else
    local val="'${2}'"
  fi

  [[ "${old_val}" != "${val}" ]] || return 0

  notice "$(printf "${BOLD}%s${NC}: ${BOLD}%s${NC} to ${BOLD}%s${NC}" "${pid}" "${1}" "${2}")"
  dconf write "${1}" "'${2}'"
}

set_keybinds(){

  __pid_list="$(pgrep -U "$(whoami)" "mate-session")"
  if [ -z "${__pid_list}" ]; then
    error "No MATE sessions detected..."
    return 1
  fi

  for __pid in ${__pid_list}; do

    set_env "${__pid}"
    notice "$(printf "Setting keybinds for PID: ${BOLD}%d${NC}" "${__pid}")"
    while read __pair; do
      [ -z "$__pair" ] && continue

      set_key "$(awk -F' ' '{ print $1 }' <<< "${__pair}")" "$(awk -F' ' '{ $1=""; print $0 }' <<< "${__pair}" | sed -r 's/^\s+//g')"
    done <<< "${KEYBINDS}"
  done
}

notice "Setting up preferred MATE keybinds on active MATE sessions."
set_keybinds
