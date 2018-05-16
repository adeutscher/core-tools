#!/bin/bash

# Lazy script to add a trusted CA Certificate.

# Only use sudo if we are not already root.
if (( ${EUID} )); then
  _s="sudo"
fi

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

# Script Functions

add_prompt(){
  local _f="${1}"
  local _r=""

  while (( 1 )); do
    question "$(printf "Add ${GREEN}%s${NC} as a trusted certificate? (y/n)" "${_f}")"

    if grep -iPq "y(es)?" <<< "${__response}"; then
      local _r=0
    elif grep -iPq "n(o(pe)?)?" <<< "${__response}"; then
      local _r=1
    else
      error "Invalid input. Please respond with a yes/no."
      # Negate error increment, not a permanent error
      __error_count=$((${__error_count:-0}-1))
    fi

    if [ ! -z "${_r}" ]; then
      unset __response
      return "${_r}"
    fi
  done
}

add_cert(){
  # General addition function
  # Validate and confirm user input.

  local __error_count_initial="${__error_count:-0}"

  local newCert="${1}"

  local newCertPath="$(readlink -f "${1}")"
  local newCertDisplay="$(sed "s|^${HOME}|\\~|g" <<< "${newCertPath}")"

  # Initial error checks
  if [ -z "${newCert}" ]; then
    error "No certificate provided."
  elif [ ! -f "${newCert}" ]; then
    error "$(printf "File not found: ${GREEN}%s${NC}" "${newCert}")"
  elif ! grep -q "\.crt" <<< "${newCertPath}"; then
    error "$(printf "Certificate must end in ${GREEN}%s${NC}: ${GREEN}%s${NC}" ".crt" "${newCertDisplay}")"
  fi

  [ "${__error_count_initial}" -lt "${__error_count:0}" ] && return 1

  if ! add_prompt "${newCertDisplay}"; then
    notice "$(printf "Aborting addition of certificate: ${GREEN}%s${NC}" "${newCertDisplay}")"
    return 0
  fi

  add_cert_${method} "${newCertPath}"
}

add_cert_redhat(){
  # Procedure for RedHat-based systems.

  local newCertPath="${1}"
  local certDest="/etc/pki/ca-trust/source/anchors/"
  if ! "${_s}" cp "${newCertPath}" "${certDest}"; then
    error "$(printf "Failed to copy certificate to CA collection (${GREEN}%s${NC}): ${GREEN}%s${NC}" "${certDest}" "${newCertPath}")"
  elif ! "${_s}" update-ca-trust force-enable; then
    error "$(printf "Failed to update trusted CA collection for certificate: ${GREEN}%s${NC}" "${newCertPath}")"
  fi
}

[ -z "${1}" ] && error "No file paths provided."

if [ -f "/etc/redhat-release" ]; then
  method="redhat"
else
  error "No distributions other than RedHat distributions are supported at this time."
fi

if [ -z "${method}" ]; then
  error "No method assigned to this distribution."
  # This error should not ever be triggered, but this covers our bases...
fi

# Abort if errors exist.
if (( "${__error_count:-0}" )); then
  exit 2
fi

for _f in $@; do
  add_cert "${_f}"
done

# Return with non-zero if errors happened during any certificate addition.
if (( "${__error_count:-0}" )); then
  exit 3
fi

exit 0
