#!/bin/bash

# This script was made to try and extract PDF data from Mac '.pages' files.
# '.pages' files are apparently glorified zip files, so it's possible enough to extract readable data.

# The script is currently incomplete.
# The problem is that it assumes a 'QuickLook/Preview.pdf' file, but not all '.pages' files are consistent.
# In the future, I need to add in better handling for PDFs with a differing structure.

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
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

success(){
  printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __warning_count=$((${__warning_count:-0}+1))
}

# Script content

pages_file="$(readlink -f "$1")"
if [ -z "$2" ]; then
    # No second argument provided, default to current directory.
    # Same file name as the original barring the file extension.
    output_file="$(readlink -f ".")/$(basename "$pages_file" | sed 's/pages$/pdf/g')"
elif [ -d "$2" ]; then
    # If we were fed a directory as output, then feed into that directory.
    # Same file name as the original barring the file extension.
    output_file="$(readlink -f "$2/$(basename "$pages_file" | sed 's/pages$/pdf/g')")"
else
    # Set as argument directly
    output_file="$(readlink -f "$2")"
fi

if ! type unzip 2> /dev/null >&2; then
    error "$(printf "${BLUE}%s${NC} command not found." "$unzip")"
    exit 1
elif [ -z "$1" ]; then
    error "$(printf "No ${GREEN}%s${NC} file provided." ".pages")"
    exit 1
elif [ ! -f "$pages_file" ]; then
    error "$(printf "${GREEN}%s${NC} does not exist." "$pages_file")"
    exit 1
elif ! grep -q "\.pages$" <<< "$pages_file"; then
    error "$(printf "${GREEN}%s${NC} is not ${GREEN}.pages${NC} file, improper extension." "$pages_file")"
    exit 1
fi

temp_dir="$(printf "/tmp/%s/pages-conversion/conversion-%d" "$USER" "$(date +%s)")"

if mkdir -p "$temp_dir" && cd "$temp_dir" && unzip "$pages_file" && mv -i "QuickLook/Preview.pdf" "$output_file"; then
    success "$(printf "Extracted ${GREEN}%s${NC} to ${GREEN}%s${NC}." "$pages_file" "$output_file")"
    ret=0
else
    error "$(printf "Problem with extracting ${GREEN}%s${NC} to ${GREEN}%s${NC}." "$pages_file" "$output_file")"
    ret=1
fi

cd "$OLDPWD"
# Paranoid safety check before removing directory.
[ -n "$temp_dir" ] && rm -rf "$temp_dir"

exit $ret
