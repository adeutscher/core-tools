#!/bin/bash

# Update a segment in file.

# Target file is assumed to be a dotfile, with the following properties:
# * Plaintext Content
# * Supports basic single-line comments (default is '#'
# * Sectioning is either not an issue (i.e. a line can go anywhere in the config) or contained within content.

# This script was inspired by my compilation system for SSH configurations, is re-applied here to be used for general files.

# Usage
#    ./update-dotfile.sh target-file file-marker content-path [comment-character]
#
#        target-file: Path of file to be written to
#        file-marker: Internal marker to place within file. Each marker should be unique amongst sections.
#        content-path: Path to file containing contents. Set to '-' to instead read from stdin. If content is empty, then the script will abort without writing anything.
#        comment-character: Character used to initiate a comment. Defaults to '#'

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

warning(){
  printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __warning_count=$((${__warning_count:-0}+1))
}

# Script variables

TARGET_FILE="${1}"
# shellcheck disable=SC2001
TARGET_FILE_DISPLAY="$(sed "s|^${HOME}|~|" <<< "${TARGET_FILE}")"
CONTENT_MARKER="${2}" # e.g. core-tools-marker
CONTENT_TARGET="${3}"
COMMENT_CHARACTER="${4:-#}"

[ -z "${CONTENT_TARGET}" ] && exit 1

CONTENT="$(cat "${CONTENT_TARGET}")"

# If there is no content to append, then do not bother continuing.
[ -z "${CONTENT}" ] && exit 1

CONTENT_CHECKSUM="$(md5sum <<< "${CONTENT}" | cut -d' ' -f1)"
# Script functions

SECTION_START=$(grep -wnm1 "marker:${CONTENT_MARKER}" "${TARGET_FILE}" 2> /dev/null | cut -d':' -f1)
SECTION_END=$(grep -wnm1 "end:${CONTENT_MARKER}" "${TARGET_FILE}" 2> /dev/null | cut -d':' -f1)
SECTION_CHECKSUM=$(grep -wm1 "marker:${CONTENT_MARKER}" "${TARGET_FILE}" 2> /dev/null | grep -o "checksum:[^ ]*" | cut -d':' -f2)

if [ -n "${SECTION_START}" ] && [ -n "${SECTION_END}" ] && [ "${SECTION_START}" -ge "${SECTION_END}" ]; then
  error "$(printf "Start marker for ${BOLD}%s${NC} is at line ${BOLD}%d${NC}, under or at end marker at ${BOLD}%d${NC}." "${CONTENT_MARKER}" "${SECTION_START}" "${SECTION_END}")"
  exit 1
fi

if [ -f "${TARGET_FILE}" ] && [ ! -w "${TARGET_FILE}" ] || [ ! -w "$(dirname "${TARGET_FILE}")" ]; then
  error "$(printf "Content for ${BOLD}%s${NC} cannot be written to ${GREEN}%s${NC}." "${CONTENT_MARKER}" "${TARGET_FILE_DISPLAY}")"
  notice "We will still check for potential updates, though..."
  NO_WRITE=1
fi

if [ -z "$SECTION_END" ]; then
  # This section does not exist in the target file. Just append it onto the target file.

  if (( "${NO_WRITE:-0}" )); then
    if [ -z "${SECTION_START}" ]; then
      warning "$(printf "Content for ${BOLD}%s${NC} could not be inserted into unwritable file: ${GREEN}%s${NC}" "${CONTENT_MARKER}" "${TARGET_FILE_DISPLAY}")"
    else
      warning "$(printf "Content for ${BOLD}%s${NC} was corrupted. Data could not be inserted into file: ${GREEN}%s${NC}" "${CONTENT_MARKER}" "${TARGET_FILE_DISPLAY}")"
    fi
    exit 1
  fi

  if [ -n "${SECTION_START}" ]; then
    # If this executes (start is set, but end is not), then some joker deleted the end marker.
    # If we cannot determine the proper end, delete everything below then add in.
    sed -i "${SECTION_START},${SECTION_START}d;q" "${TARGET_FILE}"
  fi

  # Append header, content.
  # shellcheck disable=SC2188
  (printf "%s marker:%s checksum:%s\n\n%s\n\n%s end:%s\n" "${COMMENT_CHARACTER}" "${CONTENT_MARKER}" "${CONTENT_CHECKSUM}" "${CONTENT}" "${COMMENT_CHARACTER}" "${CONTENT_MARKER}" 2> /dev/null) >> "${TARGET_FILE}";

  if [ -z "${SECTION_START}" ]; then
    success "$(printf "${GREEN}Inserted${NC} content for ${BOLD}%s${NC} to ${GREEN}%s${NC}" "${CONTENT_MARKER}" "${TARGET_FILE_DISPLAY}")"
  else
    warning "$(printf "File markers for ${BOLD}%s${NC} in ${GREEN}%s${NC} were corrupted. Someone removed the end marker..." "${CONTENT_MARKER}" "${TARGET_FILE_DISPLAY}")"
  fi

elif [[ "${CONTENT_CHECKSUM}" != "${SECTION_CHECKSUM}" ]]; then
  # This section needs to be separate, as it involves inserting a config block into our existing config instead of just appending.

  if [ -n "${NO_WRITE}" ]; then
    warning "$(printf "Content updates for ${BOLD}%s${NC} could not be written to ${GREEN}%s${NC}." "${CONTENT_MARKER}" "${TARGET_FILE_DISPLAY}")"
    exit 1
  fi

  CONFIG_LINES=$(wc -l < "${TARGET_FILE}" 2> /dev/null)

  # Write previous content, header
  # shellcheck disable=SC2188
  (head -n "$((SECTION_START-1))" "${TARGET_FILE}"; printf "%s marker:%s checksum:%s\n\n%s\n\n%s end:%s \n" "${COMMENT_CHARACTER}" "${CONTENT_MARKER}" "${CONTENT_CHECKSUM}" "${CONTENT}" "${COMMENT_CHARACTER}" "${CONTENT_MARKER}"; 2> /dev/null) > "${TARGET_FILE}.new"

  # If trailing content exists, append it to new file.
  TAIL_TARGET="$((CONFIG_LINES-SECTION_END))"
  [ "${TAIL_TARGET}" -gt 0 ] && tail -n "${TAIL_TARGET}" "${TARGET_FILE}" >> "${TARGET_FILE}.new"

  # Overwrite old version.
  mv "${TARGET_FILE}.new" "${TARGET_FILE}"

  success "$(printf "${BLUE}Updated${NC} ${BOLD}%s${NC} content in ${GREEN}%s${NC}" "${CONTENT_MARKER}" "${TARGET_FILE_DISPLAY}")"
else
  notice "$(printf "No changes to ${BOLD}%s${NC} content in ${GREEN}%s${NC}" "${CONTENT_MARKER}" "${TARGET_FILE_DISPLAY}")"
fi

if (( "${__error_count}" )); then
  exit 1
fi
