#!/bin/bash

# Lazy script to wait for specified processes to be done.
# This is different from the BASH built-in 'wait',
#   as the built-in will only support children of the current shell.

# The trade-off is that this function will not support the tracking of exit codes.
# Only the parent of a process (or something with tracing privileges) can collect its exit code.

# Common message functions
###

# Define colours
if [ -t 1 ] && [ -z "${NO_COLOR}" ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  PURPLE='\033[1;95m'
  YELLOW='\033[1;93m'
  RED='\033[1;31m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi

error(){
  printf "${RED}Error${NC} %s\n" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "${BLUE}Notice${NC} %s\n" "${@}"
}

print_complete(){
  printf "${GREEN}Complete${NC} %s\n" "${@}"
}

print_duration(){
  printf "  ${YELLOW}Duration${NC} %s\n" "${@}"
}

print_wait(){
  printf "${PURPLE}Waiting${NC} %s\n" "${@}"
}

warning(){
  printf "${YELLOW}Warning${NC} %s\n" "${@}"
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

  # Units with a value of zero are left out (e.g. "1 hour and 5 seconds").
  # A duration of zero is displayed as "0 seconds" ("0s" in mode 2).
  # A year is treated as 365 days.

  local __num="${1}"
  local __mode="${2:-0}"
  local __units __unit __name __rest __size __singular __count __i
  local __parts=()

  # Only accept non-negative integers.
  [[ "${__num}" =~ ^[0-9]+$ ]] || return 1
  __num=$((10#${__num}))

  if [ "${__mode}" = 2 ]; then
    # Each unit should be its abbreviation and its length in seconds, from largest to smallest.
    __units=(c:3153600000 y:31536000 w:604800 d:86400 h:3600 m:60 s:1)
  else
    # Each unit should be a pairing of a name (in plural form),
    #  its length in seconds (from largest to smallest),
    #  and (optionally) the phrasing of a single unit (in case lopping an 's' off of the end won't cut it)
    __units=(centuries:3153600000:century years:31536000 weeks:604800 days:86400 hours:3600 minutes:60 seconds:1)
  fi

  for __unit in "${__units[@]}"; do
    __name="${__unit%%:*}"
    __rest="${__unit#*:}"
    __size="${__rest%%:*}"

    __count=$((__num / __size))
    __num=$((__num % __size))

    # Skip units with nothing in them, unless the whole duration is zero.
    if (( ! __count )) && { (( __size > 1 )) || (( ${#__parts[@]} )); }; then
      continue
    fi

    if [ "${__mode}" = 2 ]; then
      # Short, compressed, and space-efficient version.
      __parts+=("${__count}${__name}")
    elif [ "${__count}" -eq 1 ]; then
      # Attempt special singular unit, otherwise lop the 's' off of unit plural for singular.
      __singular=""
      [[ "${__rest}" == *:* ]] && __singular="${__rest#*:}"
      __parts+=("${__count} ${__singular:-${__name%s}}")
    else
      # Standard plural.
      __parts+=("${__count} ${__name}")
    fi
  done

  for (( __i = 0; __i < ${#__parts[@]}; __i++ )); do
    if (( __i )); then
      # Prepare for the next unit.
      if [ "${__mode}" = 2 ]; then
        printf " "
      elif [ "${__mode}" = 0 ] && (( __i == ${#__parts[@]} - 1 )); then
        # If you aren't a fan of the Oxford comma, then take out this line.
        (( ${#__parts[@]} > 2 )) && printf ","
        printf " and "
      else
        printf ", "
      fi
    fi
    printf "%s" "${__parts[__i]}"
  done
}

get_uptime(){
  # Whole seconds since boot. Process start times are measured against this clock.
  local __uptime
  read -r __uptime _ < /proc/uptime
  UPTIME="${__uptime%%.*}"
}

# Script Functions

if type lsof 2> /dev/null >&2; then
  HAVE_LSOF=1
fi

# Process start times in /proc are given in clock ticks.
CLOCK_TICKS="$(getconf CLK_TCK 2> /dev/null)"
if ! [[ "${CLOCK_TICKS}" =~ ^[1-9][0-9]*$ ]]; then
  CLOCK_TICKS=100
fi

read_proc_stat(){
  # Read the state and start time of a process into PROC_STATE and PROC_START.
  # Returns 1 if the process does not exist or has already exited (zombie or dead).
  local stat fields
  { read -r stat < "/proc/${1}/stat"; } 2> /dev/null || return 1

  # The command name (field 2) is in parentheses and may contain spaces,
  #   so split the remaining fields after the last ')'.
  read -r -a fields <<< "${stat##*) }"
  PROC_STATE="${fields[0]}"
  PROC_START="${fields[19]}" # Field 22, start time in clock ticks since boot.
  [[ "${PROC_STATE}" != [ZX] ]]
}

add_pid(){
  # Track a running process, recording its start time and command.
  # Returns 1 if the process is not running.
  local pid="${1}"
  local existing cmd
  local args=()

  for existing in "${PIDS[@]}"; do
    [ "${existing}" = "${pid}" ] && return 0
  done

  read_proc_stat "${pid}" || return 1

  mapfile -d '' -t args 2> /dev/null < "/proc/${pid}/cmdline"
  if (( ${#args[@]} )); then
    cmd="${args[*]}"
  else
    # Kernel threads have no command line. Show the command name in the same style as ps.
    { read -r cmd < "/proc/${pid}/comm"; } 2> /dev/null
    cmd="[${cmd}]"
  fi

  PIDS+=("${pid}")
  STARTS+=("${PROC_START}")
  COMMANDS+=("${cmd}")
}

pid_finished(){
  # A tracked process is finished once it is gone, is a zombie,
  #   or its PID now belongs to a process with a different start time.
  ! read_proc_stat "${PIDS[${1}]}" || [ "${PROC_START}" != "${STARTS[${1}]}" ]
}

wait_for_pids(){

  if (( ANY )); then
    notice "Any-mode specified, stopping as soon as any of the matched processes are completed."
  fi

  complete=0
  get_uptime
  time_start="${UPTIME}"
  while (( 1 )); do
    current=0
    while [ "${current}" -lt "${#PIDS[*]}" ]; do
      if ! (( "${COMPLETED[${current}]:-0}" )) && pid_finished "${current}"; then
        print_complete "$(printf "PID Complete: ${BOLD}%s${NC} %s" "${PIDS[${current}]}" "${COMMANDS[${current}]}")"
        get_uptime
        print_duration "$(printf "Process time: ${BOLD}%s${NC}" "$(__translate_seconds "$((UPTIME - STARTS[current] / CLOCK_TICKS))")")"
        print_duration "$(printf "Watch time: ${BOLD}%s${NC}" "$(__translate_seconds "$((UPTIME - time_start))")")"
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

usage(){
  printf "${BOLD}Usage${NC}: %s [-a] [-l] [-s interval] [--strict] [-h] [--] pid|pattern|file ...\n\n" "${0##*/}"
  printf "Wait for processes to finish, including processes that are not children of the current shell.\n\n"
  printf "Operands:\n"
  printf "  pid          A numeric process ID.\n"
  printf "  pattern      A ${BLUE}pgrep${NC} pattern, matched against process names (first 15 characters).\n"
  printf "  file         A file path. Waits for the processes that have the file open (requires ${BLUE}lsof${NC}).\n"
  printf "               If no process has the file open, the file name is tried as a ${BLUE}pgrep${NC} pattern.\n\n"
  printf "Options:\n"
  printf "  -a           Stop as soon as any one of the processes is finished.\n"
  printf "  -h           Show this help.\n"
  printf "  -l           Lazy mode. Exit successfully instead of failing when no processes matched at all.\n"
  printf "  -s interval  Seconds between checks (default: 0.5, minimum: 0.25).\n"
  printf "  --strict     Fail if any pattern matches no processes, even if other operands matched.\n"
  printf "  --           Treat all remaining arguments as operands.\n"
}

valid_interval(){
  # Accept a decimal number of seconds that is at least 0.25.
  local whole fraction
  [[ "${1}" =~ ^([0-9]*)(\.([0-9]*))?$ ]] || return 1
  whole="${BASH_REMATCH[1]}"
  fraction="${BASH_REMATCH[3]}"
  [ -n "${whole}${fraction}" ] || return 1

  # Compare in hundredths of a second.
  fraction="${fraction}00"
  (( 10#${whole:-0} * 100 + 10#${fraction:0:2} >= 25 ))
}

# Confirm that valid PIDs were given and that they existed at the start of the script's running.

PGREP_THRESHOLD=16
ANY=0
LAZY=0
STRICT=0
END_OF_OPTIONS=0
UNMATCHED_PATTERNS=()
UNMATCHED_COLOURS=()

while (( $# )); do
  # Each pass of getopts gets a fresh argument list, so start over at its first entry.
  OPTIND=1
  while getopts ":ahls:-:" OPT "$@"; do
    # Handle switches up until we encounter a non-switch option.
    case "$OPT" in
      h)
         usage
         exit 0
         ;;
      a)
         ANY=1
         ;;
      l)
         LAZY=1
         ;;
      s)
        if valid_interval "${OPTARG}"; then
          CUSTOM_INTERVAL=1
          INTERVAL="${OPTARG}"
        else
          error "$(printf "Invalid check interval: ${BOLD}%s${NC} (must be at least ${BOLD}%s${NC} seconds)" "${OPTARG}" "0.25")"
        fi
        ;;
      -)
        # getopts has no long options, so '--name' arrives as '-' with 'name' as its argument.
        case "${OPTARG}" in
          strict)
            STRICT=1
            ;;
          *)
            error "$(printf "Invalid switch: ${BOLD}--%s${NC}" "${OPTARG}")"
            ;;
        esac
        ;;
      :)
        error "$(printf "Switch requires an argument: ${BOLD}-%s${NC}" "${OPTARG}")"
        ;;
      *)
        error "$(printf "Invalid switch: ${BOLD}-%s${NC}" "${OPTARG}")"
        ;;
    esac
  done # getopts loop

  # getopts stops after consuming '--'. Everything after it is an operand.
  if (( OPTIND > 1 )) && [ "${*:OPTIND-1:1}" = "--" ]; then
    END_OF_OPTIONS=1
  fi

  # Set ${1} to first operand, ${2} to second operands, etc.
  shift $((OPTIND - 1))
  while (( $# )); do
    # Break if the option began with a '-', going back to getopts phase.
    if ! (( END_OF_OPTIONS )) && [[ "${1}" == -?* ]]; then
      break
    fi

    # Mark that there was an attempt to give a PID.
    # If the attempt failed, then there will be a more specific error message down the chain.
    ATTEMPT=1
    LSOF_PROCESS=0
    IS_FILE=0
    PATTERN_COLOUR="${BOLD}"

    if [ -z "${1}" ] || { ! (( END_OF_OPTIONS )) && [ "${1}" = "-" ]; }; then
      error "$(printf "Invalid operand: ${BOLD}'%s'${NC}" "${1}")"
      shift
      continue
    fi

    if [ -f "${1}" ]; then
      # Argument is a file path. Attempt to use lsof to get a path.

      IS_FILE=1
      PATTERN_COLOUR="${GREEN}"

      if (( "${HAVE_LSOF:-0}" )); then
        lsof_processes="$(lsof -t "${1}")"

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

      if ! [[ "${1}" =~ ^[0-9]+$ ]]; then
        # If the argument is not a number, then assume that we want to pgrep for matcing process entries.

        file_pattern="${1}"
        original_file_pattern=""

        if [ "$(wc -c <<< "${1}")" -ge "16" ]; then

          # Pattern as given is too long. Print a warning and then attempt a clipped-down version.

          if (( "${IS_FILE}" )); then
            file_pattern="$(basename "${file_pattern}")"
          fi
          original_file_pattern="${file_pattern}"
          file_pattern="${file_pattern:0:$((PGREP_THRESHOLD-1))}"

          notice "$(printf "Checking for PIDs matching pattern: ${BOLD}%s${NC}" "${original_file_pattern}")"
          warning "$(printf "Pattern length is ${BOLD}%d${NC} characters or greater. ${BLUE}%s${NC} cannot match this many characters." "${PGREP_THRESHOLD}" "pgrep")"
          warning "$(printf "Attempting to clip down to ${BOLD}%d${NC} characters for ${BLUE}%s${NC}: ${PATTERN_COLOUR}%s${NC} -> ${PATTERN_COLOUR}%s${NC}" "$((PGREP_THRESHOLD-1))" "pgrep" "${original_file_pattern}" "${file_pattern}")"

        else
          notice "$(printf "Checking for PIDs matching pattern: ${BOLD}%s${NC}" "${file_pattern}")"
        fi

        # The '--' keeps patterns beginning in '-' from being read as pgrep options.
        # pgrep never matches itself, and the subshell running it is gone
        #   before add_pid checks it, so only this script needs to be skipped.
        # Skipping this script avoids infinite waiting when waiting for other invocations of this script.
        results="$(pgrep -- "${file_pattern}")"

        matched=0
        for result in ${results}; do
          [ "${result}" = "$$" ] && continue
          add_pid "${result}" && matched=1
        done

        if ! (( matched )); then
          # Reported after all arguments are read, since -l may come after the pattern.
          UNMATCHED_PATTERNS+=("${file_pattern}")
          UNMATCHED_COLOURS+=("${PATTERN_COLOUR}")
        fi
      elif ! add_pid "${1}"; then
        # PID must exist and be running at start.
        error "$(printf "PID does not exist or has already exited: ${BOLD}%s${NC}" "${1}")"
      fi

    fi

    shift
  done # Operand ${1} loop.
done # Outer ${1} loop.

if (( LAZY )) && (( STRICT )); then
  error "$(printf "Switches cannot be combined: ${BOLD}%s${NC} and ${BOLD}%s${NC}" "-l" "--strict")"
fi

for i in "${!UNMATCHED_PATTERNS[@]}"; do
  # The colour goes in the format string so that printf interprets its escape sequence.
  # Unmatched patterns are only fatal in strict mode.
  # Without any matches at all, the "No matched PIDs" check below still fails unless in lazy mode.
  if ! (( STRICT )); then
    warning "$(printf "No processes matched pattern: ${UNMATCHED_COLOURS[i]}%s${NC}" "${UNMATCHED_PATTERNS[i]}")"
  else
    error "$(printf "No processes matched pattern: ${UNMATCHED_COLOURS[i]}%s${NC}" "${UNMATCHED_PATTERNS[i]}")"
  fi
done

if ! (( "${ATTEMPT:-0}" )); then
  error "No PIDs provided."
elif ! (( "${#PIDS[*]}" )) && ! { (( LAZY )) && (( ${#UNMATCHED_PATTERNS[@]} )) && ! (( __error_count )); }; then
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

if ! (( "${#PIDS[*]}" )); then
  # Lazy mode, and none of the patterns matched anything.
  notice "No matched PIDs, nothing to wait for."
  exit 0
fi

current=0
while [ "${current}" -lt "${#PIDS[*]}" ]; do
  print_wait "$(printf "for: ${BOLD}%s${NC} %s" "${PIDS[${current}]}" "${COMMANDS[${current}]}")"
  current="$((current+1))"
done

# Announce Options
(( "${CUSTOM_INTERVAL}" )) && notice "$(printf "Check interval: ${BOLD}%s${NC}" "${INTERVAL}")"

# Wait for PIDs
wait_for_pids
