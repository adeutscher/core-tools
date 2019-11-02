#!/bin/bash

# A short and silly wrapper over making a quick self-signed certificate.

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

target="$(basename "${1:-${HOSTNAME}}")"

if [ -z "${target}" ]; then
  error "No target specified."
elif ! grep -qP "^[[:alnum:]^.*[[:^digit:]].*$" <<< "${target}"; then
  # Target validation.
  error "$(printf "Invalid target: ${GREEN}%s${NC}" "${target}")"
fi

(( "${__error_count:-0}" )) && exit 1

notice "$(printf "Making a quick self-signed cert for target: ${GREEN}%s${NC}" "${target}")"

file_cert="${target}.crt"
file_key="${target}.key"

if [ -f "${file_cert}" ]; then
  error "$(printf "Cert file already exists: ${GREEN}%s${NC}" "${file_cert}")"
fi
if [ -f "${file_key}" ]; then
  error "$(printf "Key file already exists: ${GREEN}%s${NC}" "${file_key}")"
fi

(( "${__error_count:-0}" )) && exit 1

openssl req -newkey rsa:4096 -nodes -keyout "${file_key}" -x509 -days 365 -subj "/CN=${target}" -out "${file_cert}"
