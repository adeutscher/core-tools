#!/bin/bash

no_format_keyword="__CORE_TOOLS_NO_FORMAT__"

# Common message functions.

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi

error(){
  printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

notice(){
  printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

success(){
  printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

# Script functions

check_requirement(){
  if ! type "${1}" 2> /dev/null >&2; then
    error "$(printf "${BLUE}%s${NC} is required for this script." "${1}")"
    exit 1
  fi
}
check_requirement "astyle"
check_requirement "black"

if [ -z "$1" ]; then
  error "Usage: format-code.sh extension [target-directory]"
  exit 2
fi

while [ -n "${1}" ]; do
  if grep -Pq "^\.[^\.]+" <<< "${1}"; then
    extensions="${extensions} ${1}"
  else
    targets="$(printf "%s\n%s" "${targets}" "$(readlink -f "${1}")")"
  fi
  shift
done

if [ -z "${targets}" ]; then
  # Default to current directory if none were provided.
  targets="$(readlink -f "$(pwd)")"
fi

total=0
total_errors=0
total_formatted=0

while read target; do
  [ -z "${target}" ] && continue
  echo "${target}"
  # Trim out home directory for display purposes.
  displayTarget="$(sed 's|^'"$HOME"'|~|g' <<< "${target}")"

  cmd="astyle"
  for extension in ${extensions}; do
    case "${extension}" in
      .c)
        ;&
      .cpp)
        ;&
      .css)
        ;&
      .h)
        ;&
      .hpp)
        ;&
      .js)
        ;&
      .php)
        switches="--style=linux -xj -cnN --lineend=linux"
        ;;
      .py)
        cmd="black"
        switches="-S"
      *)
        error "$(printf "Unhandled extension: $GREEN%s$NC" "${extension}")"
        continue
        ;;
    esac

    results="$(find "$target" -name "*${extension}")"

    if [ -z "${results}" ]; then
      notice "$(printf "No ${GREEN}%s${NC}' files to format in dir: ${GREEN}%s${NC}" "${extension}" "${displayTarget}")"
      continue
    fi

    notice "$(printf "Formatting all '$GREEN%s$NC' files dir: $GREEN%s$NC" "${extension}" "${displayTarget}")"
    notice "$(printf "$BLUE%s$NC switches: $BOLD%s$NC" "${cmd}" "${switches}")"

    _total=0
    _formatted=0
    _error=0
    unset __code_file
    while read __code_file; do

      if [ -z "$__code_file" ]; then
        continue
      fi

      __code_file_display="$(sed 's|^'"${HOME}"'|~|g' <<< "${__code_file}")"
      _total="$((${_total}+1))"
      if [ ! -r "$__code_file" ]; then
        error "$(printf "Unable to read file: ${GREEN}%s${NC}" "$__code_file")"
        _error="$((${_error}+1))"
        continue
      elif grep -qwm1 "$no_format_keyword" "$__code_file"; then
        notice "$(printf "Skipping ${GREEN}%s${NC}, found no-format keyword: ${BOLD}%s${NC}" "$__code_file" "$no_format_keyword")"
      else
        output="$("${cmd}" $switches "$__code_file")"
        current_colour="${BOLD}"
        if [ -z "$output" ]; then
          error "$(printf "No output for file: ${GREEN}%s${NC}" "${__code_file_display}")"
          _error="$((${_error}+1))"
          continue
        elif grep -qi "^Formatted" <<< "${output}"; then
          current_colour="${GREEN}"
          _formatted="$((${_formatted}+1))"
        fi

        notice "$(printf "${current_colour}%s${NC}: ${GREEN}%s${NC}" "$(cut -d' ' -f1 <<< "$output")" "${__code_file_display}")"
      fi
    done <<< "${results}"
    if (( "${_error:-0}" )); then
      error "$(printf "Problems with reading ${BOLD}%d${NC} '${GREEN}%s${NC}' files in dir: ${GREEN}%s${NC}" "${_error}" "${extension}" "${displayTarget}")"
    fi
    notice "$(printf "Formatted ${BOLD}%d/%d${NC} '${GREEN}%s${NC}' files in dir: ${GREEN}%s${NC}" "${_formatted}" "${_total}" "${extension}" "${displayTarget}")"

    total="$((${total}+${_total}))"
    total_errors="$((${total_errors}+${_error}))"
    total_formatted="$((${total_formatted}+${_formatted}))"
  done
done <<< "${targets}"

if (( ! "${total:-0}" )); then
  notice "$(printf "No files to format in dir for specified extensions: ${GREEN}%s${NC}" "${displayTarget}")"
elif [ "${total}" -ne "${_total}" ]; then
  if (( "${total_errors:-0}" )); then
    error "$(printf "Problems with reading ${BOLD}%d${NC} '${GREEN}%s${NC}' files in dir: ${GREEN}%s${NC}" "${total_errors}" "${displayTarget}")"
  fi
  notice "$(printf "Formatted ${BOLD}%d/%d${NC} total files in dir: ${GREEN}%s${NC}" "${total_formatted}" "${total}" "${displayTarget}")"
fi
