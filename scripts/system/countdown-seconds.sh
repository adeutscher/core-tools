#!/bin/bash

# Count down to the specified number of seconds.
# Note: Still has a bit of wobble to it. Actual runtime will be within one second of target time.

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

  local __modules_count="$(wc -w <<< "${__modules[*]}")"
  while [ "$__i" -lt "$__modules_count" ]; do
    # Cycling through to get values for each unit.
    local __value="$(cut -d':' -f2 <<< "${__modules[$__i]}")"

    local __mod_value="$(($__num % $__value))"
    local __num="$((__num / $__value))"

    local __times[$__i]="$__mod_value"
    local __c=$(($__c+1))
    local __i=$(($__i+1))
    if (( ! $__num )); then
      break
    fi
  done
  unset __module

  local __i=$(($__c-1))
  while [ "$__i" -ge "0" ]; do
    # Splitting logic for compressed version (mode 2) and
    #   other phrasings requires much less tangled code.
    if [ "${2:-0}" -eq 2 ]; then
      # Short, compressed, and space-efficient version.

      printf "${__times[$__i]}$(cut -d':' -f1 <<< "${__modules[$__i]}")"

      if (( $__i )); then
        printf " "
      fi
    else
      # Long version

      # Cycling through used units in reverse.
      if [ "${2:-0}" -eq 0 ] && (( ! $__i )) && [ "$__c" -gt 1 ]; then
        printf "and "
      fi

      # Handle plural
      if [ "${__times[$__i]}" -eq 1 ]; then
        # Attempt special singluar unit.
        local __s="$(cut -d':' -f3 <<< "${__modules[$__i]}")"
        if [ -n "$__s" ]; then
          # Singular unit had content.
          printf "${__times[$__i]} $__s"
        else
          # Lop the 's' off of unit plural for singular.
          printf "${__times[$__i]} $(cut -d':' -f1 <<< "${__modules[$__i]}" | sed 's/s$//')"
        fi
      else
        # Standard plural.
        printf "${__times[$__i]} $(cut -d':' -f1 <<< "${__modules[$__i]}")"
      fi

      if (( $__i )); then
        # Prepare for the next unit.
        # If you aren't a fan of the Oxford comma, then take out this line
        [ "$__c" -ge 2 ] && printf ","
        # Print space. Leave this in.
        printf " "
      fi
    fi

    local __i=$(($__i-1))
  done
}

countdown_seconds(){

  # If not a positive integer integer, return
  egrep -q "^[0-9]{1,}$" <<< "${1}" || return 1
  (( "${1:-0}" )) || return 1

  duration="${1}"
  target="$(date -d "${duration} seconds" +%s)"

  while (( 1 )); do
    current="$(date +%s)"
    remaining="$((${target}-${current}))"

    if [ "${remaining}" -ge 0 ] && [ "${remaining}" -ne "${old_remaining:-0}" ]; then
      # Print new output if remaining time has changed.
      printf "\33[2K\r%s remaining" " " "$(__translate_seconds "${remaining}" 1)"
    fi
    old_remaining="${remaining}"

    # Sleep briefly.
    # Making this a smaller number improves the accuracy of display and timing, but uses more CPU resources.
    # Then again, if CPU optimization was the main concern, then a plain sleep should have been used instead of this script...
    sleep 0.2

    [ "${remaining}" -lt 1 ] && break
  done
  printf "\33[2K\r%s\n" "$(__translate_seconds "${duration}" 1) elapsed"
}

arg_duration="${1}"

countdown_seconds "${arg_duration}"
