
# Time-related Functions
####

__translate_seconds(){
  # Translate a time given in seconds (e.g. the difference between two Unix timestamps) to more human-friendly units.

  # So far, I've mostly used this in hook functions to give me a display of how long the parent process has lasted.
  # Example:
  #  local __ctime=$(date +%s)
  #  local __stime=$(stat -c%X /proc/$PPID)
  #  local __time_output="$(__translate_seconds "$(($__ctime - $__stime))")"

  local __num=$1
  local __c=0
  local __i=0

  # Each "module" should be a pairing of a name (in plural form),
  #  the number of that unit until the next phrasing,
  #  and (optionally) the phrasing of a single unit (in case lopping an 's' off of the end won't cut it)
  local __modules=(seconds:60 minutes:60 hours:24 days:7 weeks:52 years:100 centuries:100:century)

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
    # Cycling through used units in reverse.
    if (( ! $__i )) && [ "$__c" -gt 1 ]; then
      printf "and "
    fi

    if [ "${__times[$__i]}" -eq 1 ]; then
      local __s="$(cut -d':' -f3 <<< "${__modules[$__i]}")"
      if [ -n "$__s" ]; then
        printf "${__times[$__i]} $__s"
      else
        printf "${__times[$__i]} $(cut -d':' -f1 <<< "${__modules[$__i]}" | sed 's/s$//')"
      fi
    else
      printf "${__times[$__i]} $(cut -d':' -f1 <<< "${__modules[$__i]}")"
    fi

    if (( $__i )); then
      if [ "$__c" -gt 2 ]; then
        # Prepare for the next unit.
        # If you aren't a fan of the Oxford comma, then you have some adjusting to do.
        printf ", "
      else
        printf " "
      fi
    fi

    local __i=$(($__i-1))
  done
}
