#!/bin/bash

# Check domain/port pairs in a CSV file for upcoming expiry, and notify contacts.
# Usage: ./ssl-expiry-check -f data-file [-s notification-hook]

# CSV format: domain,port,days-threshold,contacts
# Contacts are optional, and must be handled by a separate script.
# Script arguments: ./script contact domain state expiry-time time-remaining

# Assignments to uncomment and place into script:
# CONTACT="${1}"     # Contact path
# DOMAIN="${2}"      # Domain examined
# STATE="${3}"       # Mode. Possible states: "expiring", "expiring SOON", or "expired"
# EXPIRY_TIME="${4}" # Expiry date
# REMAINING="${5}"   # Remaining time (human-readable)

# Common message functions.

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  PURPLE='\033[1;95m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi

error(){
  [ -t 1 ] && printf "${RED}"'Error'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  [ -t 1 ] && printf "${BLUE}"'Notice'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

success(){
  [ -t 1 ] && printf "${GREEN}"'Success'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  [ -t 1 ] && printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __warning_count=$((${__warning_count:-0}+1))
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
        if [ "$__c" -gt 2 ]; then
          # Prepare for the next unit.
          # If you aren't a fan of the Oxford comma, then you have some adjusting to do.
          printf ", "
        else
          printf " "
        fi
      fi
    fi

    local __i=$(($__i-1))
  done
}

# Script Functions

is_file(){
  [ -f "${1}" ]
}

is_script(){
  [ -f "${1}" ] && [ -x "${1}" ]
}

# Handle Arguments

while getopts "f:s:" OPT $@; do
  case "${OPT}" in
    "f")
      DATA_FILE="${OPTARG}"
      ;;
    "s")
      SCRIPT="${OPTARG}"
      ;;
  esac
done

if [ -n "${SCRIPT}" ] && ! is_script "${SCRIPT}"; then
  error "$(printf "Not an executable script: ${GREEN}%s${NC}" "${SCRIPT}")"
else
  SCRIPT="$(readlink -f "${SCRIPT}")"
fi

if [ -z "${DATA_FILE}" ]; then
  error "No data file provided."
elif [ -n "${DATA_FILE}" ] && ! is_file "${DATA_FILE}"; then
  error "$(printf "Not an valid data file: ${GREEN}%s${NC}" "${DATA_FILE}")"
fi

(( "${__error_count:-0}" )) && exit 1

TIME_NOW="$(date +%s)"
while read data; do
  [ -z "${data}" ] && continue
  DOMAIN="$(cut -d',' -f1 <<< "${data}")"
  PORT="$(cut -d',' -f2 <<< "${data}")"
  DAYS_WARNING="$(cut -d',' -f3 <<< "${data}")"

  # If invalid day count (empty or bad formatting), skip line
  grep -Pq "^\d+$" <<< "${DAYS_WARNING}" || continue

  DAYS_WARNING_SECONDS="$((${DAYS_WARNING} * 24 * 60 * 60))"
  # If the expiry time of a certificate is before (less) than this point, raise a warning.
  WARNING_THRESHOLD="$((${TIME_NOW}+${DAYS_WARNING_SECONDS}))"
  CONTACTS="$(cut -d',' -f4- <<< "${data}" | sed 's/,/ /g')"

  # If output is not a terminal, then there must be a script contacts to reach.
  [ ! -t 1 ] && ( [ -z "${SCRIPT}" ] || [ -z "${CONTACTS}" ] ) && continue

  # Get data from server.
  EXPIRY_DATE="$(openssl s_client -connect "${DOMAIN}:${PORT}" 2>/dev/null <<< "" | openssl x509 -noout -dates | grep notAfter | cut -d'=' -f2)"
  if [ -z "${EXPIRY_DATE}" ]; then
    error "$(printf "Unable to get expiry information for domain: ${BOLD}%s${NC}" "${DOMAIN}")"
    continue
  fi
  EXPIRY_DATE_UNIX="$(date -d "${EXPIRY_DATE}" +%s)"

  TIME_REMAINING="$((${EXPIRY_DATE_UNIX}-${TIME_NOW}))"
  TIME_REMAINING_READABLE="$(__translate_seconds "$(python -c "print abs(${TIME_REMAINING})")")"

  FUNCTION=notice
  FUNCTION_COLOUR="${GREEN}"
  FUNCTION_WORDING="expiring"
  SCRIPT_WORDING="is expiring"
  TIME_REMAINING_WORDING="to go"
  TIME_REMAINING_SCRIPT="in ${TIME_REMAINING_READABLE}"
  if [ "${WARNING_THRESHOLD}" -gt "${EXPIRY_DATE_UNIX}" ]; then
    FUNCTION=warning
    FUNCTION_COLOUR="${RED}"
    SCRIPT_WORDING="is expiring SOON"
  elif [ "${TIME_REMAINING}" -lt "0" ]; then
    FUNCTION=warning
    FUNCTION_COLOUR="${RED}"
    FUNCTION_WORDING="has expired"
    TIME_REMAINING_WORDING="ago"
    SCRIPT_WORDING="expired"
    TIME_REMAINING_SCRIPT="${TIME_REMAINING_READABLE} ago"
  fi

  "${FUNCTION}" "$(printf "Domain ${BOLD}%s${NC} %s at ${FUNCTION_COLOUR}%s${NC}: ${BOLD}%s${NC}" "${DOMAIN}" "${FUNCTION_WORDING}" "${EXPIRY_DATE}" "${TIME_REMAINING_READABLE} ${TIME_REMAINING_WORDING}")"

  # Script arguments: ./script contact domain state expiry-time time-remaining
  if [ -n "${SCRIPT}" ]; then
    for CONTACT in ${CONTACTS}; do
      "${SCRIPT}" "${CONTACT}" "${DOMAIN}" "${SCRIPT_WORDING}" "${EXPIRY_DATE}" "${TIME_REMAINING_SCRIPT}"
    done

  fi

done < "${DATA_FILE}"

