#!/bin/bash

# Lazy script to wait for specified processes to be done.
# This is different from the BASH built-in 'wait',
#   as the built-in will only support children of the current shell.

# The trade-off is that this function will not support the tracking of exit codes.

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
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

# Script Functions

add_pid(){
  [ -z "${1}" ] && return 0
  notice "$(printf "Waiting for PID: ${BOLD}%s${NC}" "${1}")"
  PIDS="${PIDS} ${1}"
}

pid_exists(){
  [ -d "/proc/${1}" ] && return 0
  return 1
}

validate_pids(){

  # Confirm that valid PIDs were given and that they existed at the start of the script's running.

  if [ -z "${1}" ]; then
    error "No PIDs provided."
    return 1
  fi

  for pid in ${@}; do
    if ! grep -Pq "^\d+$" <<< "${pid}"; then
      # If the argument is not a number, then assume that we want to pgrep for matcing entries.
      notice "$(printf "Checking for PIDs matching pattern: ${BOLD}%s${NC}" "${pid}")"

      # Get results, sanitizing options beginning in '-'.
      results="$(pgrep "$(sed "s/-/\\\\-/g" <<< "${pid}")")"

      if [ -z "${results}" ]; then
        error "$(printf "No matching processes: ${BOLD}%s${NC}" "${pid}")"
        continue
      fi
      for result in ${results}; do
        add_pid "${result}"
      done
    elif ! pid_exists "${pid}"; then
      # PID must exist at start.
      error "$(printf "PID does not exist: ${BOLD}%s${NC}" "${pid}")"
    else
      add_pid "${pid}"
    fi
  done

  (( "${__error_count:-0}" )) && return 1
  return 0
}

wait_for_pids(){

  count="$(wc -w <<< "${PIDS}")"
  complete=0

  while [ "${complete}" -lt "${count}" ]; do
    for pid in ${PIDS}; do
      if ! pid_exists "${pid}"; then
        notice "$(printf "PID Complete: ${BOLD}%s${NC}" "${pid}")"
        complete="$((${complete}+1))"
        PIDS="$(sed -r "s/\b${pid}\b//g" <<< "${PIDS}")"
      fi
    done
    sleep 1
  done
}

validate_pids $@ || exit 1
wait_for_pids
