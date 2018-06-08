#!/bin/bash

# Super-lazy and over-engineered wrapper to burn an ISO image to a CD.

# Common message functions.

set_colours(){
  # Define colours
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  PURPLE='\033[1;95m'
  BOLD='\033[1m'
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

# Script Operations

ISO="$(readlink -f "${1}")"
DEVICE="$(readlink -f "${2:-/dev/cdrom}")"

unset COMMAND
for _command in wodim cdrecord; do
  if type "${_command}" 2> /dev/null >&2; then
    COMMAND="${_command}"
    break
  fi
done

if [ -z "${COMMAND}" ]; then
  error "$(printf "Neither ${BLUE}%s${NC} nor ${BLUE}%s${NC} are available on this system." "wodim" "cdrecord")"
fi

if [ -z "${ISO}" ]; then
  error "No ISO specified."
elif ! [ -f "${ISO}" ]; then
  error "$(printf "ISO does not exist: ${GREEN}%s${NC}" "${ISO}")"
fi

if ! [ -b "${DEVICE}" ]; then
  error "$(printf "No such target device: ${GREEN}%s${NC}" "${DEVICE}")"
elif ! [ -w "${DEVICE}" ]; then
  if (( ${EUID:-0} )); then
    notice "$(printf "Target device ${GREEN}%s${NC} not writable as ${BOLD}%s${NC}. Escalating to ${RED}%s${NC}" "${DEVICE}" "${USER}" "root")"
    sudo bash "$(readlink "${0}")"
    exit $?
  fi
  error "$(printf "Target device ${GREEN}%s${NC} not writable to ${RED}%s${NC}..." "${DEVICE}" )"
fi

(( "${__error_count:-0}" )) && exit 1

notice "$(printf "Burning ${GREEN}%s${NC} to ${GREEN}%s${NC}." "${ISO##*/}" "${DEVICE}")"

time "${COMMAND}" -v dev="${DEVICE}" speed=8 -eject "${ISO}"
ret="${?}"

if (( "${ret}" )); then
  error "$(printf "Failed to burn ${GREEN}%s${NC} to ${GREEN}%s${NC}." "${ISO##*/}" "${DEVICE}")"
else
  notice "$(printf "Burned ${GREEN}%s${NC} to ${GREEN}%s${NC}." "${ISO##*/}" "${DEVICE}")"
fi

exit "${ret}"
else

fi
