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

if ! type astyle 2> /dev/null >&2; then
  error "$(printf "$BLUE%s$NC is required for this script." "astyle")"
  exit 1
fi

if [ -z "$1" ]; then
  error "Usage: format-code.sh extension [target-directory]"
  exit 2
fi

extension=$1

if ! grep -q "^\." <<< "$extension"; then
  error "$(printf "Extensions must begin with a '.' (e.g. '$GREEN%s$NC', '$GREEN%s$NC')" ".c" ".cpp")"
  error "Usage: format-code.sh extension [target-directory]"
  exit 3
fi

case "$extension" in
  .c)
    ;&
  .cpp)
    ;&
  .h)
    switches="--style=linux -xj -c --lineend=linux -n"
    ;;
  *)
    error "$(printf "Unhandled extension: $GREEN%s$NC" "$extension")"
    exit 4
    ;;
esac

target="$(readlink -f "${2:-$(pwd)}")"
notice "$(printf "Formatting all '$GREEN%s$NC' files dir: $GREEN%s$NC" "$1" "$target")"
notice "$(printf "$BLUE%s$NC switches: $BOLD%s$NC" "astyle" "$switches")"

unset __code_file
while read __code_file; do
  if [ -z "$__code_file" ]; then
    continue
  elif [ ! -r "$__code_file" ]; then
    error "$(printf "Unable to read file: ${GREEN}%s${NC}" "$__code_file")"
    continue
  elif grep -qwm1 "$no_format_keyword" "$__code_file"; then
    notice "$(printf "Skipping ${GREEN}%s${NC}, found no-format keyword: ${BOLD}%s${NC}" "$__code_file" "$no_format_keyword")"
  else
    output="$(astyle $switches "$__code_file")"
    if [ -z "$output" ]; then
      error "$(printf "No output for file: ${GREEN}%s${NC}" "$__code_file")"
      continue
    fi
    notice "$(printf "${BOLD}%s${NC}: ${GREEN}%s${NC}" "$(cut -d' ' -f1 <<< "$output")" "$(cut -d' ' -f3 <<< "$output")")"
  fi
done <<< "$(find "$target" -name "*$extension")"
