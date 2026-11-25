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

# The kernel cuts process names (as seen by pgrep) down to this many characters.
COMM_LENGTH=15

# pgrep-only mode (-p, or WAIT_FOR_PID_PGREP_ONLY set to anything other than empty or 0).
# By default, patterns are also matched against full script and program names (see build_name_table).
# That check reads the command line of every process in /proc from bash, once per pattern check
#   (the initial check and each -r re-check, never on each wait interval).
# Trade-offs of the full name check:
#   * It is slower than pgrep alone. About 0.1s per check with ~700 processes, more on busier systems.
#   * It can match more processes than pgrep alone, such as every 'python foo.py' for pattern 'foo'.
#   * Without it, scripts run by an interpreter and names over the kernel's limit are invisible.
# The check is on by default. It happens once (or once per re-check) in a script that is
#   presumably watching at least one long-running task, so its cost is not worth trading for missed matches.
#   To confirm phrasing, that's once per check sweep, not once per pattern in a sweep.
# I don't particularly like the idea of iterating through /proc on a fundamental level,
#   but unfortunately it seems to be the best worst option.
case "${WAIT_FOR_PID_PGREP_ONLY:-0}" in
  0) PGREP_ONLY=0 ;;
  *) PGREP_ONLY=1 ;;
esac

# Interpreters that run a script given as an argument.
# A script run through its shebang line also shows up this way (e.g. '/bin/bash ./foo.sh').
SHELL_INTERPRETERS='^(ba|da|z|k|mk|a|y|c|tc)?sh$|^fish$'
SCRIPT_INTERPRETERS='^(python|pypy|perl|ruby|php|lua|luajit|node|nodejs|tclsh|wish|Rscript)[0-9.]*$'

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
  local i cmd
  local args=()

  read_proc_stat "${pid}" || return 1

  # A PID with a different start time is a new process re-using the number of a finished one.
  for i in "${!PIDS[@]}"; do
    [ "${PIDS[i]}" = "${pid}" ] && [ "${STARTS[i]}" = "${PROC_START}" ] && return 0
  done

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

get_script_name(){
  # Set SCRIPT_NAME to the base name of the script that an interpreter command line is running.
  # Arguments: the command line, one argument per command line entry.
  # Returns 1 if the command is not a known interpreter, or if it is not running a script file
  #   (e.g. 'bash -c ...', 'python -c ...', or reading from standard input).
  # Arguments after the script are the script's own, and are never looked at.
  local cmd="${1##*/}"
  local family arg c rest i
  local value_opts="" noscript_opts="" script_opts="" long_value_opts="" long_noscript_opts=""
  SCRIPT_NAME=""
  shift

  if [[ "${cmd}" =~ ${SHELL_INTERPRETERS} ]]; then
    family=shell
  elif [[ "${cmd}" =~ ${SCRIPT_INTERPRETERS} ]]; then
    family="${BASH_REMATCH[1]}"
  else
    return 1
  fi

  # Short options that take a value, that mean there is no script file,
  #   or that take the script (or module) to run as their value.
  case "${family}" in
    shell)
      value_opts="oO"; noscript_opts="cs"
      long_value_opts="--rcfile --init-file"
      ;;
    python|pypy)
      value_opts="WXQ"; noscript_opts="c"; script_opts="m"
      ;;
    perl)
      noscript_opts="eE"
      ;;
    ruby)
      value_opts="CEFIr"; noscript_opts="e"
      ;;
    php)
      value_opts="cdz"; noscript_opts="raR"; script_opts="fF"
      ;;
    lua|luajit)
      # 'lua -e stat script.lua' still runs the script after the statement.
      value_opts="el"
      ;;
    node|nodejs)
      value_opts="r"; noscript_opts="ep"
      long_value_opts="--require --loader --experimental-loader --import"
      long_noscript_opts="--eval --print"
      ;;
    tclsh|wish)
      long_value_opts="-encoding"
      ;;
    Rscript)
      noscript_opts="e"
      ;;
  esac

  while (( $# )); do
    arg="${1}"
    shift

    [ -n "${arg}" ] && case " ${long_value_opts} " in
      *" ${arg} "*)
        shift
        continue
        ;;
    esac

    case "${arg}" in
      --)
        SCRIPT_NAME="${1}"
        break
        ;;
      -|"")
        # Reading the script from standard input.
        return 1
        ;;
      --*)
        case " ${long_noscript_opts} " in
          *" ${arg%%=*} "*)
            return 1
            ;;
        esac
        continue
        ;;
      -?*|+?*)
        if [[ "${arg}" == +* ]] && [ "${family}" != shell ]; then
          SCRIPT_NAME="${arg}"
          break
        fi

        # Walk through a group of short options, such as '-ex' or '-Wignore'.
        for (( i = 1; i < ${#arg}; i++ )); do
          c="${arg:i:1}"
          rest="${arg:i+1}"
          if [[ "${noscript_opts}" == *"${c}"* ]]; then
            return 1
          elif [[ "${script_opts}" == *"${c}"* ]]; then
            SCRIPT_NAME="${rest:-${1}}"
            break 2
          elif [[ "${value_opts}" == *"${c}"* ]]; then
            # The value is either the rest of this argument or the next argument.
            [ -z "${rest}" ] && shift
            break
          fi
        done
        ;;
      *)
        SCRIPT_NAME="${arg}"
        break
        ;;
    esac
  done

  SCRIPT_NAME="${SCRIPT_NAME##*/}"
  [ -n "${SCRIPT_NAME}" ]
}

build_name_table(){
  # Record the full names of running processes in cases that pgrep cannot see:
  #   * Scripts run by an interpreter, where the process name is the interpreter (e.g. 'python foo.py').
  #   * Programs and scripts whose names are longer than the kernel's process name limit.
  local dir pid comm name
  local args=()

  NAME_PIDS=()
  NAME_VALUES=()

  for dir in /proc/[0-9]*; do
    pid="${dir#/proc/}"
    # This script is never matched, the same as the pgrep check.
    [ "${pid}" = "$$" ] && continue

    mapfile -d '' -t args 2> /dev/null < "${dir}/cmdline" || continue
    (( ${#args[@]} )) || continue

    if get_script_name "${args[@]}"; then
      name="${SCRIPT_NAME}"
    else
      # Not a script. Only use the program name if the process name was cut short.
      { read -r comm < "${dir}/comm"; } 2> /dev/null || continue
      name="${args[0]##*/}"
      (( ${#comm} == COMM_LENGTH )) && [[ "${name}" == "${comm}"?* ]] || continue
    fi

    NAME_PIDS+=("${pid}")
    NAME_VALUES+=("${name}")
  done

  NAME_TABLE_BUILT=1
}

match_file(){
  # Track the processes that have a file open.
  # Arguments: file path, quiet mode (1 during re-checks).
  # Returns 1 if no process has the file open, or if lsof is not available.
  local path="${1}"
  local quiet="${2:-0}"
  local lsof_processes p

  if ! (( "${HAVE_LSOF:-0}" )); then
    # Was given a file path, but could not follow up because lsof was not available.
    # Make this mark to print a specific error message down the chain.
    TRIED_LSOF=1
    return 1
  fi

  if (( quiet )); then
    lsof_processes="$(lsof -t "${path}" 2> /dev/null)"
  else
    lsof_processes="$(lsof -t "${path}")"
  fi

  if [ -z "${lsof_processes}" ]; then
    # Print a notice that an attempt was made to use lsof on a path.
    # Explicitly choosing not to count this as an error.
    (( quiet )) || notice "$(printf "File ${GREEN}%s${NC} is not being used by any processes. Attempting the file name through ${BLUE}%s${NC}" "${path}" "pgrep")"
    return 1
  fi

  for p in ${lsof_processes}; do
    (( quiet )) || notice "$(printf "File ${GREEN}%s${NC} is open in process: ${BOLD}%s${NC}" "${path}" "${p}")"
    add_pid "${p}"
  done
}

match_pattern(){
  # Track the processes matching a pattern, by process name (pgrep) and by full script or program name.
  # Arguments: pattern, colour for messages, quiet mode (1 during re-checks).
  # Returns 1 if nothing matched.
  local pattern="${1}"
  local colour="${2:-${BOLD}}"
  local quiet="${3:-0}"
  local pgrep_pattern="${pattern}"
  local matched=0
  local results result i

  if [ "${#pattern}" -gt "${COMM_LENGTH}" ]; then

    # Pattern as given is too long for pgrep. Print a warning and then attempt a clipped-down version.
    # The full pattern is still checked against full script and program names below,
    #   unless in pgrep-only mode.
    pgrep_pattern="${pattern:0:${COMM_LENGTH}}"

    if ! (( quiet )); then
      notice "$(printf "Checking for PIDs matching pattern: ${BOLD}%s${NC}" "${pattern}")"
      warning "$(printf "Pattern length is ${BOLD}%d${NC} characters or greater. ${BLUE}%s${NC} cannot match this many characters." "$((COMM_LENGTH+1))" "pgrep")"
      warning "$(printf "Attempting to clip down to ${BOLD}%d${NC} characters for ${BLUE}%s${NC}: ${colour}%s${NC} -> ${colour}%s${NC}" "${COMM_LENGTH}" "pgrep" "${pattern}" "${pgrep_pattern}")"
    fi

  elif ! (( quiet )); then
    notice "$(printf "Checking for PIDs matching pattern: ${BOLD}%s${NC}" "${pattern}")"
  fi

  # The '--' keeps patterns beginning in '-' from being read as pgrep options.
  # pgrep never matches itself, and the subshell running it is gone
  #   before add_pid checks it, so only this script needs to be skipped.
  # Skipping this script avoids infinite waiting when waiting for other invocations of this script.
  if (( quiet )); then
    results="$(pgrep -- "${pgrep_pattern}" 2> /dev/null)"
  else
    results="$(pgrep -- "${pgrep_pattern}")"
  fi

  for result in ${results}; do
    [ "${result}" = "$$" ] && continue
    add_pid "${result}" && matched=1
  done

  # Check full names using the same extended regular expression syntax that pgrep uses.
  # Skipped in pgrep-only mode (see PGREP_ONLY).
  if ! (( PGREP_ONLY )); then
    (( "${NAME_TABLE_BUILT:-0}" )) || build_name_table
    for i in "${!NAME_PIDS[@]}"; do
      [[ "${NAME_VALUES[i]}" =~ ${pattern} ]] || continue
      add_pid "${NAME_PIDS[i]}" && matched=1
    done
  fi

  (( matched ))
}

match_operand(){
  # Track the processes for a file or pattern operand.
  # Arguments: operand, whether the operand was a file (1/0), quiet mode (1 during re-checks).
  # Returns 1 if nothing matched.
  local operand="${1}"
  local is_file="${2:-0}"
  local quiet="${3:-0}"

  if (( is_file )); then
    match_file "${operand}" "${quiet}" && return 0
    # Fall back to the file's name, which pgrep and the script name check can match.
    match_pattern "${operand##*/}" "${GREEN}" "${quiet}"
  else
    match_pattern "${operand}" "${BOLD}" "${quiet}"
  fi
}

print_waiting(){
  # Announce the tracked processes, starting at the given index.
  local current="${1:-0}"
  while [ "${current}" -lt "${#PIDS[*]}" ]; do
    print_wait "$(printf "for: ${BOLD}%s${NC} %s" "${PIDS[${current}]}" "${COMMANDS[${current}]}")"
    current="$((current+1))"
  done
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

  # Processes completed in an earlier round (before a re-check) stay complete.
  complete=0
  for current in "${!COMPLETED[@]}"; do
    (( COMPLETED[current] )) && complete=$((complete+1))
  done

  # Watch time covers all rounds of waiting.
  if [ -z "${time_start}" ]; then
    get_uptime
    time_start="${UPTIME}"
  fi

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

recheck(){
  # Look for new processes matching the pattern and file operands.
  # PID operands are not re-checked.
  # Returns 1 if no new processes were found.
  local before="${#PIDS[*]}"
  local i

  notice "Re-checking for new processes matching the requested patterns and files."

  # Process names may have changed since the last check.
  NAME_TABLE_BUILT=0
  for i in "${!RECHECK_OPERANDS[@]}"; do
    match_operand "${RECHECK_OPERANDS[i]}" "${RECHECK_FILES[i]}" 1
  done

  if [ "${#PIDS[*]}" -eq "${before}" ]; then
    notice "No new matching processes found."
    return 1
  fi

  print_waiting "${before}"
}

usage(){
  printf "${BOLD}Usage${NC}: %s [-a] [-l] [-p] [-r] [-s interval] [--strict] [-h] [--] pid|pattern|file ...\n\n" "${0##*/}"
  printf "Wait for processes to finish, including processes that are not children of the current shell.\n\n"
  printf "Operands:\n"
  printf "  pid          A numeric process ID.\n"
  printf "  pattern      A ${BLUE}pgrep${NC} pattern, matched against process names (first 15 characters).\n"
  printf "               Also matched against the full name of a script run by an interpreter\n"
  printf "               (e.g. 'python foo.py' or 'bash /path/to/foo.sh'), and the full name of\n"
  printf "               a program whose name is too long for ${BLUE}pgrep${NC}. Arguments to a script are not matched.\n"
  printf "  file         A file path. Waits for the processes that have the file open (requires ${BLUE}lsof${NC}).\n"
  printf "               If no process has the file open, the file name is tried as a pattern.\n\n"
  printf "Options:\n"
  printf "  -a           Stop as soon as any one of the processes is finished.\n"
  printf "  -h           Show this help.\n"
  printf "  -l           Lazy mode. Exit successfully instead of failing when no processes matched at all.\n"
  printf "  -p           pgrep-only mode. Skip matching full script and program names, which reads every\n"
  printf "               process in /proc. Faster, but misses scripts run by an interpreter and long names.\n"
  printf "               Also enabled by setting ${BOLD}WAIT_FOR_PID_PGREP_ONLY${NC} to anything other than empty or 0.\n"
  printf "  -r           Re-check mode. Once all processes are finished, check the patterns and files again,\n"
  printf "               and wait for any new matches. Repeats until a check finds nothing new.\n"
  printf "               PID operands are not re-checked.\n"
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

ANY=0
LAZY=0
RECHECK=0
STRICT=0
END_OF_OPTIONS=0
UNMATCHED_PATTERNS=()
UNMATCHED_COLOURS=()
RECHECK_OPERANDS=()
RECHECK_FILES=()

while (( $# )); do
  # Each pass of getopts gets a fresh argument list, so start over at its first entry.
  OPTIND=1
  while getopts ":ahlprs:-:" OPT "$@"; do
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
      p)
         PGREP_ONLY=1
         ;;
      r)
         RECHECK=1
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

    if [ -z "${1}" ] || { ! (( END_OF_OPTIONS )) && [ "${1}" = "-" ]; }; then
      error "$(printf "Invalid operand: ${BOLD}'%s'${NC}" "${1}")"
      shift
      continue
    fi

    if [ -f "${1}" ]; then
      # Argument is a file path. Attempt to use lsof to find the processes using it.
      if match_file "${1}"; then
        RECHECK_OPERANDS+=("${1}")
        RECHECK_FILES+=(1)
        shift
        continue
      fi
      IS_FILE=1
    else
      IS_FILE=0
    fi

    # If lsof did not match any processes, then attempt to use pgrep or a direct PID.
    if [[ "${1}" =~ ^[0-9]+$ ]]; then
      if ! add_pid "${1}"; then
        # PID must exist and be running at start.
        error "$(printf "PID does not exist or has already exited: ${BOLD}%s${NC}" "${1}")"
      fi
    else
      # If the argument is not a number, then assume that we want to pgrep for matching process entries.
      RECHECK_OPERANDS+=("${1}")
      RECHECK_FILES+=("${IS_FILE}")

      if (( IS_FILE )); then
        pattern="${1##*/}"
        colour="${GREEN}"
      else
        pattern="${1}"
        colour="${BOLD}"
      fi

      if ! match_pattern "${pattern}" "${colour}"; then
        # Reported after all arguments are read, since -l may come after the pattern.
        UNMATCHED_PATTERNS+=("${pattern}")
        UNMATCHED_COLOURS+=("${colour}")
      fi
    fi

    shift
  done # Operand ${1} loop.
done # Outer ${1} loop.

if (( LAZY )) && (( STRICT )); then
  error "$(printf "Switches cannot be combined: ${BOLD}%s${NC} and ${BOLD}%s${NC}" "-l" "--strict")"
fi

if (( ANY )) && (( RECHECK )); then
  error "$(printf "Switches cannot be combined: ${BOLD}%s${NC} and ${BOLD}%s${NC}" "-a" "-r")"
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

print_waiting 0

# Announce Options
(( "${CUSTOM_INTERVAL}" )) && notice "$(printf "Check interval: ${BOLD}%s${NC}" "${INTERVAL}")"

if (( RECHECK )) && ! (( ${#RECHECK_OPERANDS[@]} )); then
  notice "Re-check mode has no patterns or files to re-check. Only PIDs were given."
  RECHECK=0
fi

# Wait for PIDs
wait_for_pids

# Re-check for new matches until a check comes up empty.
# Finding nothing new is the normal way for re-check mode to finish.
while (( RECHECK )) && recheck; do
  wait_for_pids
done

exit 0
