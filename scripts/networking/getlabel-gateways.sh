#!/bin/bash

# Convenience wrapper around getlabel to fetch for all gateways.

# Common message functions

set_colours(){
  # Define colours
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
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

# Script logic

command="getlabel"
interfaces="$(route -n | grep "^0.0.0.0" | awk -F' ' '{ print $8 }' | sort | uniq | sed '/tun/d')"

if [ -z "${interfaces}" ]; then
  error "No non-tun default gateways defined."
fi

if ! type "${command}" 2> /dev/null >&2; then
  error "$(printf "${BLUE}%s${NC} command not available." "${command}")"
fi

(( "${__error_count}" )) && exit 1

for i in ${interfaces}; do
  tidy_name="${tidy_name} ${i}"
done

c=$(wc -w <<< "${interfaces}")
if [ "${c}" -eq 1 ]; then
  notice "$(printf "Getting labels for default gateway:${BOLD}%s${NC}" "${tidy_name}")"
else
  notice "$(printf "Getting labels for ${BOLD}%d${NC} default gateways: ${BOLD}%s${NC}" "${c}" "${tidy_name}")"
fi


for i in ${interfaces}; do
  if ! "${command}" "${i}" "${@}"; then
    error "$(printf "Error running ${BLUE}%s${NC}" getlabel)"
  fi
done

(( "${__error_count}" )) && exit 1

exit 0
