
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
