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
  COUNT="$((${COUNT:-0}+1))"
  PIDS[${COUNT}]="${1}"
}

pid_exists(){
  [ -d "/proc/${1}" ] && return 0
  return 1
}

wait_for_pids(){
  complete=0
  while (( 1 )); do
    current=0
    while [ "${current}" -lt "${COUNT}" ]; do
      current="$((${current}+1))"
      (( "${COMPLETED[${current}]:-0}" )) && continue
      if ! pid_exists "${PIDS[${current}]}"; then
        notice "$(printf "PID Complete: ${BOLD}%s${NC}" "${PIDS[${current}]}")"
        complete="$((${complete}+1))"
        COMPLETED[${current}]=1
      fi
    done
    [ "${complete}" -eq "${COUNT}" ] && break
    sleep "${INTERVAL:-0.5}"
  done
}

# Confirm that valid PIDs were given and that they existed at the start of the script's running.

while [ -n "${1}" ]; do
  while getopts ":hs:" OPT $@; do
    # Handle switches up until we encounter a non-switch option.
    case "$OPT" in
      h)
         notice "Usage: ./wait-for-pid.sh [-s interval] [-h] pattern|pid ..."
         exit 0
         ;;
      s)
        if grep -Pq "^\d+$" <<< "${OPTARG}"; then
          CUSTOM_INTERVAL=1
          INTERVAL="${OPTARG}"
        else
          error "$(printf "Invalid check interval: ${BOLD}%s${NC}" "${OPTARG}")"
        fi
        ;;
      *)
        error "$(printf "Invalid switch: ${BOLD}-%s${NC}" "${OPTARG}")"
        ;;
    esac
  done # getopts loop

  # Set ${1} to first operand, ${2} to second operands, etc.
  shift $((OPTIND - 1))
  while [ -n "${1}" ]; do
    # Break if the option began with a '-', going back to getopts phase.
    grep -q "^\-" <<< "${1}" && break

    # Mark that there was an attempt to give a PID.
    # If the attempt failed, then there will be a more specific error message down the chain.
    ATTEMPT=1

    if ! grep -Pq "^\d+$" <<< "${1}"; then
      # If the argument is not a number, then assume that we want to pgrep for matcing entries.
      notice "$(printf "Checking for PIDs matching pattern: ${BOLD}%s${NC}" "${1}")"

      # Get results, sanitizing options beginning in '-'.
      # Strip out PID of script and the subshell that collects input to respectively
      # avoid infinite waiting when waiting for other invocations of this script and
      #  to cut down on output on account of insta-done processes.

      # The BASHPID SHOULD be stuck to the PID of the current BASH process.
      # However, it seems that piped output is itself its own PID. TIL.
      # Our options in this case are:
      #  A: Store BASHPID in a separate variable before piping. I went with this option.
      #  B: Use mktemp to avoid subshells altogether. Seems like a bit of a waste.

      results="$(bpid="${BASHPID}"; pgrep "$(sed "s/-/\\\\-/g" <<< "${1}")" | sed -e "/^${$}$/d" -e "/^${bpid}$/d")"

      if [ -z "${results}" ]; then
        error "$(printf "No matching processes: ${BOLD}%s${NC}" "${1}")"
      else
        for result in ${results}; do
          add_pid "${result}"
        done
      fi
    elif ! pid_exists "${1}"; then
      # PID must exist at start.
      error "$(printf "PID does not exist: ${BOLD}%s${NC}" "${1}")"
    else
      add_pid "${1}"
    fi
    shift
  done # Operand ${1} loop.
done # Outer ${1} loop.

if ! (( "${ATTEMPT:-0}" )); then
  error "No PIDs provided."
fi

(( "${__error_count:-0}" )) && exit 1

current=0
while [ "${current}" -lt "${COUNT}" ]; do
  current="$((${current}+1))"
  notice "$(printf "Waiting for PID: ${BOLD}%s${NC}" "${PIDS[${current}]}")"
done

# Announce Options
(( "${CUSTOM_INTERVAL}" )) && notice "$(printf "Check interval: ${BOLD}%s${NC}" "${INTERVAL}")"

# Wait for PIDs
wait_for_pids
