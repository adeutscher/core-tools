#!/bin/bash

# Lazy script to wait for specified processes to be done.
# This is different from the BASH built-in 'wait',
#   as the built-in will only support children of the current shell.

# The trade-off is that this function will not support the tracking of exit codes.

# Common message functions
###

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  PURPLE='\033[1;95m'
  YELLOW='\033[1;93m'
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

print_complete(){
  printf "${GREEN}"'Complete'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

print_duration(){
  printf "${YELLOW}"'Duration'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

print_wait(){
  printf "${PURPLE}"'Waiting'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

warning(){
  printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

# Time-related Functions
####

__translate_seconds(){
  # Translate a time given in seconds (e.g. the difference between two Unix timestamps) to more human-friendly units.

  # So far, I've mostly used this in hook functions to give me a display of how long the parent process has lasted.
  # Example:
  #  local __ctime=$(date +%s)
  #  local __stime=$(stat -c%X /proc/$PPID)
  #  local __time_output="$(__translate_seconds "$(($__ctime - $__stime))")"

  # The optional second argument to this function specifies the format mode.
  # Mode and format examples:
  # 0: 3 hours, 2 minutes, and 1 second (DEFAULT)
  # 1: 3 hours, 2 minutes, 1 second
  # 2: 3h 2m 1s

  local __num=$1
  local __c=0
  local __i=0

  if [ "${2:-0}" -eq 2 ]; then
    # Each "module" should be the unit and the number of that unit until the next phrasing.
    local __modules=(s:60 m:60 h:24 d:7 w:52 y:100 c:100)
  else
    # Each "module" should be a pairing of a name (in plural form),
    #  the number of that unit until the next phrasing,
    #  and (optionally) the phrasing of a single unit (in case lopping an 's' off of the end won't cut it)
    local __modules=(seconds:60 minutes:60 hours:24 days:7 weeks:52 years:100 centuries:100:century)
  fi

  local __modules_count
  __modules_count="$(wc -w <<< "${__modules[*]}")"
  while [ "$__i" -lt "$__modules_count" ]; do
    # Cycling through to get values for each unit.
    local __value
    __value="$(cut -d':' -f2 <<< "${__modules[$__i]}")"

    local __mod_value
    __mod_value=$((__num % __value))
    local __num
    __num=$((__num / __value))

    local __times[$__i]="$__mod_value"
    local __c
    __c=$((__c+1))
    local __i
    __i=$((__i+1))
    if (( ! __num )); then
      break
    fi
  done
  unset __module

  local __i=$((__c-1))
  while [ "$__i" -ge "0" ]; do
    # Splitting logic for compressed version (mode 2) and
    #   other phrasings requires much less tangled code.
    if [ "${2:-0}" -eq 2 ]; then
      # Short, compressed, and space-efficient version.

      printf "%s%s" "${__times[$__i]}" "$(cut -d':' -f1 <<< "${__modules[$__i]}")"

      if (( __i )); then
        printf " "
      fi
    else
      # Long version

      # Cycling through used units in reverse.
      if [ "${2:-0}" -eq 0 ] && (( ! __i )) && [ "$__c" -gt 1 ]; then
        printf "and "
      fi

      # Handle plural
      if [ "${__times[$__i]}" -eq 1 ]; then
        # Attempt special singluar unit.
        local __s
        __s="$(cut -d':' -f3 <<< "${__modules[$__i]}")"
        if [ -n "$__s" ]; then
          # Singular unit had content.
          printf "%s %s" "${__times[$__i]}" "$__s"
        else
          # Lop the 's' off of unit plural for singular.
          printf "%s %s" "${__times[$__i]}" "$(cut -d':' -f1 <<< "${__modules[$__i]}" | sed 's/s$//')"
        fi
      else
        # Standard plural.
        printf "%s %s" "${__times[$__i]}" "$(cut -d':' -f1 <<< "${__modules[$__i]}")"
      fi

      if (( __i )); then
        # Prepare for the next unit.
        # If you aren't a fan of the Oxford comma, then take out this line
        [ "$__c" -ge 2 ] && printf ","
        # Print space. Leave this in.
        printf " "
      fi
    fi

    local __i=$((__i-1))
  done
}

# Script Functions

if type lsof 2> /dev/null >&2; then
  HAVE_LSOF=1
fi

add_pid(){
  if [ -z "${1}" ] || grep -qw "${1}" <<< "${PIDS[*]}"; then
    return 0
  fi
  PIDS[${#PIDS[*]}]="${1}"
}

pid_exists(){
  [ -d "/proc/${1}" ] && return 0
  return 1
}

wait_for_pids(){

  if (( ANY )); then
    notice "Any-mode specified, stopping as soon as any of the matched processes are completed."
  fi

  complete=0
  time_start="$(date +%s)"
  while (( 1 )); do
    current=0
    while [ "${current}" -lt "${#PIDS[*]}" ]; do
      if ! (( "${COMPLETED[${current}]:-0}" )) && ! pid_exists "${PIDS[${current}]}"; then
        print_complete "$(printf "PID Complete: ${BOLD}%s${NC}: %s" "${PIDS[${current}]}" "${COMMANDS[${current}]}")"
        time_diff="$(($(date +%s)-time_start))"
        print_duration "$(printf "Process time: ${BOLD}%s${NC}" "$(__translate_seconds "$((time_diff+${DURATIONS[${current}]}))")")"
        print_duration "$(printf "Watch time: ${BOLD}%s${NC}" "$(__translate_seconds "${time_diff}")")"
        complete=$((complete+1))
        COMPLETED[${current}]=1
      fi
      current=$((current+1))

    done

    if (( ANY )) && (( complete )); then
      break
    fi

    # Check for wheher or not we are done before we sleep.
    # This is done outside of the while statement in order to avoid the sleep
    [ "${complete}" -eq "${#PIDS[*]}" ] && break

    sleep "${INTERVAL:-0.5}"
  done
}

# Confirm that valid PIDs were given and that they existed at the start of the script's running.

PGREP_THRESHOLD=16
ANY=0

while [ -n "${1}" ]; do
  while getopts "ahs:" OPT "$@"; do
    # Handle switches up until we encounter a non-switch option.
    case "$OPT" in
      h)
         notice "Usage: ./wait-for-pid.sh [-a] [-s interval] [-h] pattern|pid ..."
         exit 0
         ;;
      a)
         ANY=1
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
    LSOF_PROCESS=0
    IS_FILE=0
    PATTERN_COLOUR="${BOLD}"

    if [ -f "${1}" ]; then
      # Argument is a file path. Attempt to use lsof to get a path.

      IS_FILE=1
      PATTERN_COLOUR="${GREEN}"

      if (( "${HAVE_LSOF:-0}" )); then
        lsof_processes="$(lsof -t "${1}" | sort | uniq)"

        if [ -n "${lsof_processes}" ]; then
          LSOF_PROCESS=1
          for p in ${lsof_processes}; do
            notice "$(printf "File ${GREEN}%s${NC} is open in process: ${BOLD}%s${NC}" "${1}" "${p}")"
            add_pid "${p}"
          done
        else
          # Print a notice that an attempt was made to use lsof on a path.
          # Explicitly choosing not to count this as an error.
          notice "$(printf "File ${GREEN}%s${NC} is not being used by any processes. Attempting the file name through ${BLUE}%s${NC}" "${1}" "pgrep")"
        fi
      else
        # Was given a file path, but could not follow up because lsof was not available.
        # Make this mark to print a specific error message down the chain.
        TRIED_LSOF=1
      fi
    fi

    if ! (( "${LSOF_PROCESS:-0}" )); then

      # If lsof did not match any processes, then attempt to use pgrep or a direct PID.

      if ! grep -Pq "^\d+$" <<< "${1}"; then
        # If the argument is not a number, then assume that we want to pgrep for matcing process entries.

        file_pattern="${1}"
        original_file_pattern=""

        if [ "$(wc -c <<< "${1}")" -ge "16" ]; then

          # Pattern as given is too long. Print a warning and then attempt a clipped-down version.

          if (( "${IS_FILE}" )); then
            file_pattern="$(basename "${file_pattern}")"
            original_file_pattern="${file_pattern}"
          fi
          file_pattern="${file_pattern:0:$((PGREP_THRESHOLD-1))}"

          notice "$(printf "Checking for PIDs matching pattern: ${BOLD}%s${NC}" "${original_file_pattern}")"
          warning "$(printf "Pattern length is ${BOLD}%d${NC} characters or greater. ${BLUE}%s${NC} cannot match this many characters." "${PGREP_THRESHOLD}" "pgrep")"
          warning "$(printf "Attempting to clip down to ${BOLD}%d${NC} characters for ${BLUE}%s${NC}: ${PATTERN_COLOUR}%s${NC} -> ${PATTERN_COLOUR}%s${NC}" "$((PGREP_THRESHOLD-1))" "pgrep" "${original_file_pattern}" "${file_pattern}")"

        else
          notice "$(printf "Checking for PIDs matching pattern: ${BOLD}%s${NC}" "${file_pattern}")"
        fi

        # Get results, sanitizing options beginning in '-'.
        # Strip out PID of script and the subshell that collects input to respectively
        # avoid infinite waiting when waiting for other invocations of this script and
        #  to cut down on output on account of insta-done processes.

        # The BASHPID SHOULD be stuck to the PID of the current BASH process.
        # However, it seems that piped output is itself its own PID. TIL.
        # Our options in this case are:
        #  A: Store BASHPID in a separate variable before piping. I went with this option.
        #  B: Use mktemp to avoid subshells altogether. Seems like a bit of a waste.

        results="$(bpid="${BASHPID}"; pgrep "${file_pattern//-/\\-}" | sed -e "/^${$}$/d" -e "/^${bpid}$/d")"

        if [ -z "${results}" ]; then
          error "$(printf "No processes matched pattern: ${PATTERN_COLOUR}%s${NC}" "${file_pattern}")"
        else
          for result in ${results}; do
            add_pid "${result}"
          done
        fi
      elif ! pid_exists "${1}"; then
        # PID must exist at start.
        error "$(printf "PID does not exist: ${BOLD}%s${NC}" "${1}")"
      else
        # Argument is a number
        add_pid "${1}"
      fi

    fi

    shift
  done # Operand ${1} loop.
done # Outer ${1} loop.

if ! (( "${ATTEMPT:-0}" )); then
  error "No PIDs provided."
elif ! (( "${#PIDS[*]}" )); then
  # Drive the point home that no matches happened.
  error "No matched PIDs."
fi

if (( __error_count )); then

  if (( TRIED_LSOF )); then
    # Only bring up the lsof attempt if we're in an error state.
    notice "$(printf "Tried to run ${BLUE}%s${NC}, but the command was not available" "lsof")"
  fi

  exit 1
fi

current=0
while [ "${current}" -lt "${#PIDS[*]}" ]; do
  COMMANDS[${current}]="$(ps -eo cmd -q "${PIDS[${current}]}" | tail -n1)"
  DURATIONS[${current}]="$(ps axwo etimes -q "${PIDS[${current}]}" | tail -n1)"
  print_wait "$(printf "Waiting for PID: ${BOLD}%s${NC}: %s" "${PIDS[${current}]}" "${COMMANDS[${current}]}")"
  current="$((current+1))"
done

# Announce Options
(( "${CUSTOM_INTERVAL}" )) && notice "$(printf "Check interval: ${BOLD}%s${NC}" "${INTERVAL}")"

# Wait for PIDs
wait_for_pids
