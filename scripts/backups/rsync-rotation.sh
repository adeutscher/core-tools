#!/bin/sh
#########################
# rsync Rotation Script #
# Author: /u/tidal49    #
# Version: 3.1          #
#########################
#set -x

# Rotate a backup of local files with rsync.
# I originally created this script because I was not satisfied
#  with how indicative the names of rsnapshot backups were.

#############
# Functions #
#############

# Common message functions.

set_colours(){
  # Define colours
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  PURPLE='\033[1;95m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
}

unset_colours(){
  unset BLUE GREEN RED YELLOW PURPLE BOLD NC
}

[ -t 1 ] && set_colours

debug(){
  (( "${__verbose:-0}" )) && printf "${PURPLE}"'DEBUG'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

error(){
  printf "${RED}"'Error'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "${BLUE}"'Notice'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

success(){
  printf "${GREEN}"'Success'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __success_count=$((${__success_count:-0}+1))
}

usage(){
  printf "${PURPLE}"'Usage'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

warning(){
  printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __warning_count=$((${__warning_count:-0}+1))
}

hexit(){
  usage "$(printf "Usage: ${GREEN}./%s${NC} input_path output_path [-c retention-count] [-f \"extra-rsync-flags\"] [-v] [-m]" "$(basename "${0}")")"
  usage "$(cat << EOF
rsync Rotation Script switches:
           --help, -h  Print this menu
           -c count    Count of how many backups to keep on file (default 7)
           -d          Replace duplicate files within a backup using fdupes.
                       Your fdupes version must support the -L/--linkhard option.
           -f flags    Extra flags to pass to rsync
           -m          Monochrome mode. Do not print colours. Redundant if stdout is not a terminal.
           -p prefix   Make a prefix for backups. Rotation will only consider items matching this prefix.
           -t          Test mode. The script will go through its regular behaviour, EXCEPT for actually running rsync
           -v          Verbose mode. Print debug messages.
EOF
)"

  exit ${1:-0}
}

set_defaults(){
  # Debug Setting
  __default_verbose="0"
  __verbose="$__default_verbose"

  # Test mode flag
  __default_test="0"
  __test="$__default_test"

  # Rsync Rotation Count
  __default_count="7"
  __count="$__default_count"

  # Rsync Rotation Count
  __default_dupes="0"
  __count="$__default_dupes"
}

## Begin script content/functions below.

backup_directory (){

  if [ ! -d "$__output_path" ]; then
    notice "$(printf "Attempting to create destination directory: ${GREEN}$__output_path${NC}")"

    __command="mkdir -p \"$__output_path\""
    run_command mkdir
  fi

  backup_date="$(date +"%Y-%m-%d-%H-%M-%S")"
  if [ -n "${__arg_prefix}" ]; then
    backup_dest="${__output_path}/${__arg_prefix}-${backup_date}"
    old_pattern="^${__arg_prefix}\-[0-9]{4}(\-[0-9]{2}){5}$"
  else
    backup_dest="${__output_path}/${backup_date}"
    old_pattern='^[0-9]{4}(\-[0-9]{2}){5}$'
  fi
    # Check for old backups.
  last_backup="$(ls -r $__output_path/ 2> /dev/null  | egrep -m1 "${old_pattern}")"
  # Check for a previous backup to base our content on.
  if [ -n "$last_backup" ]; then
    notice "$(printf "Pre-existing backup (${GREEN}$last_backup${NC}). Making a hard linked copy to base our backup off of.")"

    __command="cp -rl \"$__output_path/$last_backup\" \"$backup_dest\""
    run_command cp
  fi

  # Perform rsync job
  notice "$(printf "Backing up '${GREEN}$__input_path${NC}' to '${GREEN}$backup_dest${NC}'. (Retaining ${RED}$__count${NC} copies)")"

  __command="rsync -av --delete --progress $__other_rsync_args \"$__input_path/\" \"$backup_dest/\""
  run_command rsync

  # If selected, attempt to use fdupes to replace duplicates with hard links.
  if (( "${__dupes:-__dupes_default}" )); then
    notice "Removing duplicates with hard links."
    __command="fdupes -rL \"$backup_dest\""
    run_command fdupes
  fi

  old_backup_count="$(ls -r "$__output_path/" 2> /dev/null | egrep "${old_pattern}" | tail -n +$((1+$__count)) | wc -l)"
  if (( "$old_backup_count" )); then
    # Old backups existed to be found.
    if [ "$old_backup_count" -gt 0 ]; then
      plural="s"
    fi
    notice "$(printf "Stripping out ${RED}$old_backup_count${NC} old backup$plural.")"
    unset plural

    # Strip out old backups.
    while read __old_backup; do
      [ -z "${__old_backup}" ] && continue

      notice "$(printf "Removing old backup: '${GREEN}$__output_path/$i${NC}'")"

      __command="rm -rf \"$__output_path/$i\""
      run_command rm
    done <<< "$(ls -r $__output_path/ 2> /dev/null | egrep "${old_pattern}" | tail -n +$((1+$__count)))"
  else
    notice "No old backups to remove."
  fi
}

run_command(){
  debug "${1} command: ${__command}"
  if (( "${__test:-0}" )); then
    notice "$(printf "${RED}TEST MODE ENABLED! ${BLUE}%s${RED} IS NOT ACTUALLY BEING RUN!${NC}" "${1}")"
  else
    # Run command, specified outside because of quoting funtimes.
    eval $__command
    local result="$?"
    if (( "$result" )); then
      error "$(printf "${BLUE}%s${NC} command failed (Return Code ${BOLD}%s${NC})" "${1}" "${result}")"
      exit 1
    fi
  fi
}

set_defaults

while [ -n "${1}" ]; do
  while getopts ":c:df:hi:mo:p:tv" OPT $@; do
    # Handle switches up until we encounter a non-switch option.
    case "${OPT}" in
      "c")
        __arg_count="$(grep -P '^\d+$' <<< "${OPT}")"
        if [ -z "$__arg_count" ]; then
            error "$(printf "Invalid value ${BOLD}\"\"${NC} for \"-c\" switch. Must be an integer." "${OPTARG}")"
        fi
        ;;
      "f")
        __other_rsync_args="${OPTARG}"
        ;;
      "d")
        # Further deduplication through fdupes and hard links
        __arg_dupes="1"
        ;;
      "h")
        hexit
        ;;
      "m")
        # Force monochrome output
        unset_colours
        ;;
      "p")
        __arg_prefix="${OPTARG}"
        ;;
      "t")
        # Enable test mode - commands will not actually run
        __arg_test="1"
        ;;
      "v")
        # Enable verbose output
        __arg_verbose="1"
        ;;
    *)
        mark_error "Unknown argument: $1"
        ;;
    esac
  done # getopts loop

  # Set ${1} to first operand, ${2} to second operands, etc.
  shift $((OPTIND - 1))
  while [ -n "${1}" ]; do
    # Break if the option began with a '-', going back to getopts phase.
    grep -q "^\-" <<< "${1}" && break

    if [ -z "${__input_path}" ]; then
      __input_path="$(sed 's/\/*$//' <<< "${1}")"
    elif [ -z "${__output_path}" ]; then
      __output_path="$(sed 's/\/*$//' <<< "${1}")"
    else
      error "$(printf "Got an additional path: ${GREEN}%s${NC}" "${1}")"
    fi

    # Do script-specific operand stuff here.
    shift
  done # Operand ${1} loop.
done # Outer ${1} loop.


# Assign values to outside-facing variables.
__verbose="${__arg_verbose:-$__default_verbose}"

__count="${__arg_count:-$__default_count}"
__test="${__arg_test:-$__default_test}"
__dupes="${__arg_dupes:-$__default_dupes}"

# Check script-specific items here (validate input).

if [ -z "$__input_path" ]; then
  error "Input path not provided"
elif [ ! -d "$__input_path" ]; then
  error "Source directory does not exist: ${GREEN}$__input_path${NC}"
fi

if [ -z "$__output_path" ]; then
  error "Output path not provided."
elif [ ! -d "$__output_path" ]; then
  notice "$(printf "Destination directory does not exist: (${GREEN}$__output_path${NC}). Will attempt to create this directory.")"
fi

if (( "${__dupes:-__dupes_default}" )); then
  # Use of fdupes is requested.
  if ! type fdupes 2> /dev/null >&2; then
    error "The fdupes command is not installed on this system."
  elif ! fdupes --help 2> /dev/null | grep -q '\-\-linkhard'; then
    # Some packagings of fdupes do not support the -L/--linkhard option to reduce duplicates with hard links.
    # For example, Ubuntu 12.04 supports this feature, while CentOS 6.5 does not.
    # Checking the --help menu for a listing
    error "Your version of fdupes does not support the -L/--linkhard option."
  fi
fi

# Double-check that rsync is installed.
if ! type rsync 2> /dev/null >&2; then
  mark_error "The rsync command is not installed on this system."
fi

# Print out errors if they exist and then exit.
if (( "${__error_count:-0}" )); then
  # Silly plural stuff
  if [ "${__error_count}" -gt 1 ]; then
    plural="s"
  fi

  error "$(printf "${BOLD}%d${NC} error${plural} found..." "${__error_count}")"
  hexit 2
fi

backup_directory
