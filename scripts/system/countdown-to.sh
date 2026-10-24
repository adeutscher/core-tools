#!/bin/bash

# Count down to a time given in any format understood by GNU date's -d option.

# Define colours, separately for standard output and standard error.
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi
if [ -t 2 ]; then
  ERR_BLUE='\033[1;34m'
  ERR_GREEN='\033[1;32m'
  ERR_RED='\033[1;31m'
  ERR_BOLD='\033[1m'
  ERR_NC='\033[0m' # No Color
fi

# Message Functions
error(){
  printf "${ERR_RED}"'Error'"${ERR_NC}"'['"${ERR_GREEN}"'%s'"${ERR_NC}"']: %s\n' "${0##*/}" "${@}" >&2
  __error_count=$((${__error_count:-0}+1))
}

hint(){
  printf "${ERR_BLUE}"'Hint'"${ERR_NC}"'['"${ERR_GREEN}"'%s'"${ERR_NC}"']: %s\n' "${0##*/}" "${@}" >&2
}

notice(){
  printf "${BLUE}"'Notice'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "${0##*/}" "${@}"
}

usage(){
  local _n="${0##*/}"
  cat << USAGE
Usage: ${_n} [-h|--help] time

Count down to the given time, displaying the time remaining.

The time is parsed by GNU date's -d option, so any format that it accepts will work.
Examples:
  ${_n} 17:30
  ${_n} "tomorrow 9am"
  ${_n} "+45 minutes"
  ${_n} "2026-12-31 23:59:59"
USAGE
}

# Script functions

countdown_to(){
  local _t="${*}"
  if [ -z "${_t}" ]; then
    error "No time specified."
    usage >&2
    return 1
  fi

  local _ts _now _th
  if ! _ts="$(date -d "${_t}" +%s 2> /dev/null)"; then
    error "$(printf "Unable to parse time: ${ERR_BOLD}%s${ERR_NC}" "${_t}")"
    return 1
  fi
  printf -v _now '%(%s)T' -1
  printf -v _th '%(%a %b %e %H:%M:%S %Z %Y)T' "${_ts}"

  if [ "${_now}" -gt "${_ts}" ]; then
    error "$(printf "Requested time is ${ERR_BOLD}%s${ERR_NC} in the past: ${ERR_BOLD}%s${ERR_NC}" "$(__translate_seconds "$((_now - _ts))")" "${_th}")"
    if (( _now - _ts < 86400 )); then
      # A time without a day is taken as today, which may have already passed.
      hint "$(printf "A time without a day is taken as today. For a later day, include it (e.g. ${ERR_BOLD}\"tomorrow %s\"${ERR_NC})." "${_t}")"
    fi
    return 1
  elif [ "${_now}" -eq "${_ts}" ]; then
    notice "$(printf "Requested time has been reached: ${BOLD}%s${NC}" "${_th}")"
    return 0
  fi

  notice "$(printf "Counting down to time: ${BOLD}%s${NC}" "${_th}")"
  countdown_until "$((_ts * 1000000))"
}

now_microseconds(){
  # Store the current Unix time in microseconds in the variable named by the first argument.
  if [ -n "${EPOCHREALTIME}" ]; then
    # Strip the decimal point, which may be a comma depending on locale.
    printf -v "${1}" '%s' "${EPOCHREALTIME//[!0-9]/}"
  else
    # Bash older than 5.0 only has a whole-second clock.
    printf -v "${1}" '%(%s)T000000' -1
  fi
}

countdown_interrupted(){
  # Handle an interrupted countdown, reporting how much time was left.
  local _now _remaining
  now_microseconds _now
  _remaining=$((COUNTDOWN_TARGET - _now))
  (( _remaining < 0 )) && _remaining=0

  [ -t 1 ] && printf "\33[2K\r"
  notice "$(printf "Countdown interrupted with ${BOLD}%s${NC} remaining." "$(__translate_seconds "$(( (_remaining + 999999) / 1000000 ))")")"
  exit "${1}"
}

countdown_until(){
  # Count down to the given Unix time, in microseconds.

  COUNTDOWN_TARGET="${1}"
  local _start _now _remaining _seconds _old_seconds="" _nap

  now_microseconds _start

  trap 'countdown_interrupted 130' INT
  trap 'countdown_interrupted 143' TERM

  while (( 1 )); do
    now_microseconds _now
    _remaining=$((COUNTDOWN_TARGET - _now))
    (( _remaining < 0 )) && _remaining=0
    # Round up, so that the display only reaches zero when the target does.
    _seconds=$(( (_remaining + 999999) / 1000000 ))

    if [ -t 1 ] && [ "${_seconds}" != "${_old_seconds}" ]; then
      # Print new output if remaining time has changed.
      # Skipped if output is not going to a terminal.
      printf "\33[2K\r%s remaining" "$(__translate_seconds "${_seconds}" 1)"
    fi
    _old_seconds="${_seconds}"

    (( _remaining )) || break

    if [ -n "${EPOCHREALTIME}" ]; then
      # Sleep until the remaining whole seconds next changes (or the target is reached).
      _nap=$((_remaining % 1000000))
      (( _nap )) || _nap=1000000
    else
      # Without a sub-second clock, check back frequently instead.
      # Making this a smaller number improves the accuracy of display and timing, but uses more CPU resources.
      _nap=200000
    fi
    printf -v _nap '%d.%06d' $((_nap / 1000000)) $((_nap % 1000000))
    # Sleep in the background so that a trapped signal is handled right away instead of after the sleep.
    sleep "${_nap}" &
    wait "$!"
  done

  trap - INT TERM

  [ -t 1 ] && printf "\33[2K\r"
  printf "%s elapsed\n" "$(__translate_seconds "$(( (COUNTDOWN_TARGET - _start + 500000) / 1000000 ))" 1)"
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

case "${1}" in
  -h|--help)
    usage
    exit 0
    ;;
esac

countdown_to "${@}"
