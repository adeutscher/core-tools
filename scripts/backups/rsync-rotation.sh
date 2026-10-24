#!/bin/bash
#########################
# rsync Rotation Script #
# Author: /u/tidal49    #
# Version: 4.0          #
#########################
#set -x

# Rotate a backup of local files with rsync.
# I originally created this script because I was not satisfied
#  with how indicative the names of rsnapshot backups were.

# Sort globbed backup names by byte value so that timestamps sort chronologically.
LC_COLLATE=C
shopt -s dotglob

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
  usage "$(printf "Usage: ${GREEN}./%s${NC} input_path output_path [-c retention-count] [-d] [-f \"extra-rsync-flags\"] [-m] [-p prefix] [-t] [-v]" "$(basename "${0}")")"
  usage "$(cat << EOF
rsync Rotation Script switches:
           --help, -h  Print this menu
           -c count    Count of how many backups to keep on file (default 7). Must be at least 1.
           -d          Replace duplicate files within a backup with hard links, using
                       the hardlink command from util-linux. Only files with identical
                       content, mode, owner, and timestamp are linked.
           -f flags    Extra flags to pass to rsync. Flags are split on whitespace,
                       and quotes are not interpreted. May be given more than once.
           -m          Monochrome mode. Do not print colours. Redundant if stdout is not a terminal.
           -p prefix   Make a prefix for backups. Rotation will only consider items matching this prefix.
           -t          Test mode. The script will go through its regular behaviour, EXCEPT for actually running commands
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

  # hardlink deduplication
  __default_dupes="0"
  __dupes="$__default_dupes"

  # Extra rsync arguments
  __other_rsync_args=()
}

## Begin script content/functions below.

strip_slashes(){
  # Remove trailing slashes from a path, but leave "/" intact.
  local __path="${1}"
  while [[ "${__path}" == */ && "${__path}" != "/" ]]; do
    __path="${__path%/}"
  done
  printf '%s' "${__path}"
}

list_backups(){
  # Print the names of backup directories in the output path, oldest first.
  # ${1} is an optional regex suffix after the timestamp (e.g. '\.partial').
  local __entry __name __stamp
  for __entry in "${__output_path}"/*; do
    [ -d "${__entry}" ] || continue
    __name="${__entry##*/}"
    if [ -n "${__arg_prefix}" ]; then
      [[ "${__name}" == "${__arg_prefix}-"* ]] || continue
      __stamp="${__name#"${__arg_prefix}-"}"
    else
      __stamp="${__name}"
    fi
    [[ "${__stamp}" =~ ^[0-9]{4}(-[0-9]{2}){5}${1}$ ]] && printf '%s\n' "${__name}"
  done
}

acquire_lock(){
  # Prevent two runs from rotating the same set of backups at the same time.
  # The lock is held on file descriptor 9 until the script exits.
  local __lock_file="${__output_path}/.rsync-rotation${__arg_prefix:+-${__arg_prefix}}.lock"

  if ! type flock 2> /dev/null >&2; then
    warning "The flock command is not installed on this system. Concurrent runs will not be prevented."
    return 0
  fi

  if [ ! -d "${__output_path}" ]; then
    # Only reachable in test mode, where the output directory is not created.
    debug "Output directory does not exist. Skipping lock."
    return 0
  fi

  if ! exec 9> "${__lock_file}"; then
    error "$(printf "Unable to open lock file: ${GREEN}%s${NC}" "${__lock_file}")"
    exit 1
  fi

  if ! flock -n 9; then
    error "$(printf "Another backup is already running against ${GREEN}%s${NC} (lock file: ${GREEN}%s${NC})" "${__output_path}" "${__lock_file}")"
    exit 1
  fi
  debug "Acquired lock: ${__lock_file}"
}

backup_directory(){
  local backup_date backup_name backup_dest partial_dest last_backup old_backup remove_count plural
  local -a backups stale_backups rsync_command

  if [ ! -d "$__output_path" ]; then
    notice "$(printf "Attempting to create destination directory: ${GREEN}%s${NC}" "$__output_path")"
    run_command mkdir mkdir -p -- "$__output_path"
  fi

  acquire_lock

  # Clear out incomplete backups left by interrupted runs.
  # These are not reused, since rsync could alter the attributes of files that
  #  are still hard linked to older backups.
  mapfile -t stale_backups < <(list_backups '\.partial')
  for old_backup in "${stale_backups[@]}"; do
    warning "$(printf "Removing incomplete backup from an earlier run: '${GREEN}%s${NC}'" "$__output_path/$old_backup")"
    run_command rm rm -rf -- "$__output_path/$old_backup"
  done

  backup_date="$(date +"%Y-%m-%d-%H-%M-%S")"
  backup_name="${__arg_prefix:+${__arg_prefix}-}${backup_date}"
  backup_dest="${__output_path}/${backup_name}"
  partial_dest="${backup_dest}.partial"

  if [ -e "$backup_dest" ]; then
    error "$(printf "Backup destination already exists: ${GREEN}%s${NC}" "$backup_dest")"
    exit 1
  fi

  rsync_command=(rsync -av --delete)
  [ -t 1 ] && rsync_command+=(--progress)

  # Check for a previous backup to base our content on.
  mapfile -t backups < <(list_backups)
  if [ "${#backups[@]}" -gt 0 ]; then
    last_backup="${backups[-1]}"
    notice "$(printf "Pre-existing backup (${GREEN}%s${NC}). Unchanged files will be hard linked from it." "$last_backup")"
    # --link-dest is resolved relative to the destination, so give it an absolute path.
    rsync_command+=("--link-dest=$(cd "$__output_path" && pwd)/${last_backup}")
  fi

  rsync_command+=("${__other_rsync_args[@]}" -- "${__input_path%/}/" "$partial_dest/")

  # Perform rsync job
  notice "$(printf "Backing up '${GREEN}%s${NC}' to '${GREEN}%s${NC}'. (Retaining ${RED}%s${NC} copies)" "$__input_path" "$backup_dest" "$__count")"
  run_command rsync "${rsync_command[@]}"

  # If selected, replace duplicates with hard links.
  # -m keeps the copy with the most links, which is usually the one already
  #  shared with older backups.
  if (( "${__dupes:-0}" )); then
    notice "Removing duplicates with hard links."
    run_command hardlink hardlink -m -- "$partial_dest"
  fi

  # The backup is complete. Give it its final name.
  run_command mv mv -- "$partial_dest" "$backup_dest"

  mapfile -t backups < <(list_backups)
  if (( "${__test:-0}" )) && [ ! -d "$backup_dest" ]; then
    # Account for the backup that test mode did not actually create.
    backups+=("$backup_name")
  fi

  remove_count=$(( ${#backups[@]} - __count ))
  if [ "$remove_count" -gt 0 ]; then
    if [ "$remove_count" -gt 1 ]; then
      plural="s"
    fi
    notice "$(printf "Stripping out ${RED}%s${NC} old backup%s." "$remove_count" "$plural")"

    # Strip out old backups.
    for old_backup in "${backups[@]:0:remove_count}"; do
      # Never remove the backup we just made, even if the clock went backwards.
      [ "$old_backup" = "$backup_name" ] && continue

      notice "$(printf "Removing old backup: '${GREEN}%s${NC}'" "$__output_path/$old_backup")"
      run_command rm rm -rf -- "$__output_path/$old_backup"
    done
  else
    notice "No old backups to remove."
  fi
}

run_command(){
  # Usage: run_command label command [args...]
  local label="${1}"
  shift
  debug "$(printf '%s command: %s' "${label}" "$(printf '%q ' "${@}")")"
  if (( "${__test:-0}" )); then
    notice "$(printf "${RED}TEST MODE ENABLED! ${BLUE}%s${RED} IS NOT ACTUALLY BEING RUN!${NC}" "${label}")"
  else
    "${@}"
    local result="$?"
    if (( "$result" )); then
      error "$(printf "${BLUE}%s${NC} command failed (Return Code ${BOLD}%s${NC})" "${label}" "${result}")"
      exit 1
    fi
  fi
}

set_defaults

while [ "$#" -gt 0 ]; do
  OPTIND=1
  while getopts ":c:df:hmp:tv" OPT "$@"; do
    # Handle switches up until we encounter a non-switch option.
    case "${OPT}" in
      "c")
        if [[ "${OPTARG}" =~ ^[1-9][0-9]*$ ]]; then
          __arg_count="${OPTARG}"
        else
          error "$(printf "Invalid value ${BOLD}\"%s\"${NC} for \"-c\" switch. Must be a positive integer." "${OPTARG}")"
        fi
        ;;
      "f")
        read -r -a __extra_flags <<< "${OPTARG}"
        __other_rsync_args+=("${__extra_flags[@]}")
        ;;
      "d")
        # Further deduplication through hard links
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
      ":")
        error "$(printf "Switch ${BOLD}-%s${NC} requires an argument." "${OPTARG}")"
        ;;
      *)
        error "$(printf "Unknown switch: ${BOLD}-%s${NC}" "${OPTARG}")"
        ;;
    esac
  done # getopts loop

  # If getopts stopped at "--", treat everything after it as operands.
  if [ "$OPTIND" -gt 1 ] && [ "${@:OPTIND-1:1}" = "--" ]; then
    __end_of_switches=1
  fi

  # Set ${1} to first operand, ${2} to second operands, etc.
  shift $((OPTIND - 1))
  while [ "$#" -gt 0 ]; do
    # Break if the option began with a '-', going back to getopts phase.
    if ! (( "${__end_of_switches:-0}" )) && [[ "${1}" == -?* ]]; then
      break
    fi

    if [ -z "${1}" ]; then
      error "Got an empty path argument."
    elif [ -z "${__input_path}" ]; then
      __input_path="$(strip_slashes "${1}")"
    elif [ -z "${__output_path}" ]; then
      __output_path="$(strip_slashes "${1}")"
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
  error "$(printf "Source directory does not exist: ${GREEN}%s${NC}" "$__input_path")"
fi

if [ -z "$__output_path" ]; then
  error "Output path not provided."
elif [ ! -d "$__output_path" ]; then
  notice "$(printf "Destination directory does not exist: (${GREEN}%s${NC}). Will attempt to create this directory." "$__output_path")"
fi

if [[ "${__arg_prefix}" == */* ]]; then
  error "$(printf "Prefix may not contain a slash: ${GREEN}%s${NC}" "${__arg_prefix}")"
fi

if (( "${__dupes:-0}" )); then
  # Use of hardlink is requested.
  if ! type hardlink 2> /dev/null >&2; then
    error "The hardlink command is not installed on this system. It is provided by util-linux."
  elif ! hardlink --help 2> /dev/null | grep -q -- '--maximize'; then
    # Older, standalone versions of hardlink predate the util-linux one and use different options.
    error "Your version of hardlink does not support the -m/--maximize option. Use the util-linux version (2.34 or newer)."
  fi
fi

# Double-check that rsync is installed.
if ! type rsync 2> /dev/null >&2; then
  error "The rsync command is not installed on this system."
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
