#!/bin/bash

# Run ansible/ansible-playbook against EC2 inventory.
# Usage: ./ansible-ec2.sh keyfile filter command(s)

INVENTORY_SCRIPT="$(readlink -f "$(dirname "$(readlink -f "${0}")")")/inventory/ec2.py"

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

success(){
  printf "${GREEN}"'Success'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __warning_count=$((${__warning_count:-0}+1))
}

# Script operations
KEYFILE="${1}"
shift
FILTER="${1}"
shift

if [ -z "${FILTER}" ]; then
  error "No filter provided"
fi

if [ -z "${KEYFILE}" ]; then
  error "No keyfile provided."
elif [ ! -f "${KEYFILE}" ]; then
  error "$(printf "Key file not found: ${GREEN}%s${NC}" "${KEYFILE}")"
elif [ ! -r "${KEYFILE}" ]; then
  error "$(printf "Key file could not be read: ${GREEN}%s${NC}" "${KEYFILE}")"
elif ! chmod 400 "${KEYFILE}"; then
  error "$(printf "Could not confirm permissions on key file: ${GREEN}%s${NC}" "${KEYFILE}")"
fi

if [ "${#}" -eq 0 ]; then
  error "No parameters provided."
fi

if [ ! -f "${INVENTORY_SCRIPT}" ]; then
  error "$(printf "Inventory script not found: ${GREEN}%s${NC}" "${EC2_SCRIPT}")"
elif [ ! -x "${INVENTORY_SCRIPT}" ]; then
  error "$(printf "Inventory script not executable: ${GREEN}%s${NC}" "${EC2_SCRIPT}")"
fi

(( "${__error_count:-0}" )) && exit 1

command=ansible
filter_switch=""

if grep -q playbook <<< "${0}$(readlink -f "${0}")"; then
  # Avoiding code duplication with a silly check to the command name.
  # If we are trying to run a playbook, then use a playbook.
  command="ansible-playbook"
  filter_switch="-l"
fi

unset INVENTORY_VALUE
if grep -Pq '^(([0-9]){1,3}\.){3}([0-9]{1,3})$' <<< "${FILTER}"; then
  # If an IP address was provided, then assume that the host is an EC2 file in inventory
  #   and don't bother to spend/waste time on the inventory script.
  notice "$(printf "Checking against single address: ${GREEN}%s${NC}" "${FILTER}")"
  INVENTORY_VALUE="${FILTER},"
else
  notice "$(printf "Running ${BLUE}%s${NC} against filter: ${BOLD}%s${NC}" "${command}" "${FILTER}")"
  INVENTORY_VALUE="${INVENTORY_SCRIPT}"
fi

time "${command}" -i ${INVENTORY_VALUE} --key-file "${KEYFILE}" -u ec2-user ${filter_switch} "${FILTER}" "${@}"
