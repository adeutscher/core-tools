#!/bin/bash

# ping-reliably.sh
# A lazy network check script.
# Keep pinging a target server until we
#   have enough consecutive successful pings.
# This script finishing is a decent enough
#   sign that the host is on with no
#   interfering firewall rules along the way
#   and a steady-ish network link.

# Common message functions.

# Define colours
if [ -t 1 ]; then
  BOLD='\033[1m'
  RED='\033[1;31m'
  GREEN='\033[1;32m'
  NC='\033[0m' # No Color
fi

error(){
  printf "${RED}"'Error'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename ${0})" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "${BLUE}"'Notice'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename ${0})" "${@}"
}

# Script Functions

end(){
  printf "\n"
  exit 130
}

trap end SIGINT

_a="${1}" # Address
_t="${2:-60}" # Target number

if ! grep -Pq "^\d+$" <<< "${_t}"; then
  error "$(printf "Invalid ping count: ${BOLD}%s${NC}" "${_t}")"
fi

if [ -z "${_a}" ]; then
  error "No address provided."
else
  ping -w1 -c1 "${_a}" 2> /dev/null >&2
  if [ "${?}" -eq 2 ]; then
    error "$(printf "Invalid address: ${GREEN}%s${NC}" "${_a}")"
  fi
fi

(( "${__error_count:-0}" )) && exit 1

notice "$(printf "Waiting until ${GREEN}%s${NC} ${GREEN}%s${NC} be pinged ${BOLD}%d${NC} times in a row." "${_a}" "can" "${_t}")"

while [ "${_c:-0}" -lt "${_t}" ]; do
  _c=$((${_c:-0}+1))
  _l=$((${_l:-0}+1))

  if ! ping -w1 -c1 "${_a}" 2> /dev/null >&2; then
    _c=0
  fi

  # Print status
  printf "\33[2K\rSteady ${GREEN}%s${NC} pings: ${BOLD}%d${NC}/${BOLD}%d${NC}" "${_a}" "${_c}" "${_t}"

  # Sleep for a bit on non-timeout
  [ "${_c}" -eq 0 ] || sleep 1
done

printf "\n"
