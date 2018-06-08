#!/bin/bash

# Kill incoming SSH sessions for a user.
# Kills sessions for current user by default.
# To kill sessions for a different user, specify the username as your first argument.

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

user="${1:-${USER}}"

if [ -z "${user}" ]; then
  error "$(printf "Invalid user: ${BOLD}%s${NC}" "${user}")"
fi

(( "${__error_count}" )) && exit 1

[[ "${user}" == "${USER}" ]] && wording=" current"
notice "$(printf "Killing incoming SSH sessions for%s user: ${BOLD}%s${NC}" "${wording}" "${user}")"

if ! id "${user}" 2> /dev/null >&2; then
  error "$(printf "Invalid user: ${BOLD}%s${NC}" "${user}")"
fi

if (( "${EUID}" )) && [[ "${user}" != "${USER}" ]]; then
  # User is not root, and seeks to kill another user's SSH session.
  # Not bothering to check for special permission bit, which would be a very wacky edge case.
  error "$(printf "Without being ${RED}%s${NC}, we will not be able to kill sessions for ${BOLD}%s${NC} with current user ${BOLD}%s${NC}" "root" "${user}" "${USER}")"
fi

(( "${__error_count}" )) && exit 1

PIDS="$(ps axo user:20,pid,cmd | grep -w sshd | grep -w "^${USER}" | grep -P "\s${USER}@pts" | awk '{print $2}' | grep -P '^\d+$')"

COUNT=0
for pid in ${PIDS}; do
  notice "$(printf "Killing SSH PID: ${BOLD}%s${NC}" "${pid}")"
  kill "${pid}" && COUNT="$((${COUNT}+1))"
done

if (( "${COUNT}" )); then
  notice "$(printf "SSH sessions killed: ${BOLD}%s${NC}" "${COUNT}")"
else
  notice "No SSH sessions to kill."
fi
