#!/bin/bash

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
[ -t 1 ] && set_colours

error(){
  printf "${RED}"'Error'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "${BLUE}"'Notice'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

get_path(){
  _PATH=""
  while [ -z "${_PATH}" ]; do
    _PATH=""
    read -p "Enter destination path: " _PATH

    [ -z "${_PATH}" ] && continue

    if [ -d "${_PATH}" ]; then
      error "$(printf "Path already exists: ${GREEN}%s${NC}" "${_PATH}")"
      _PATH=""
    fi
  done
}

get_label(){
  _LABEL=""
  while [ -z "${_LABEL}" ]; do
    _TITLE=""
    read -p "Enter internal label: " _LABEL

    [ -z "${_LABEL}" ] && continue

    if ! grep -iPq "^[\da-z_]+$" <<< "${_LABEL}"; then
      error "$(printf "Invalid label (must contain numbers, letters, and/or '_'): ${BOLD}%s${NC}" "${_LABEL}")"
      _LABEL=""
    fi
  done
}

get_title(){
  _TITLE=""
  while [ -z "${_TITLE}" ]; do
    _TITLE=""
    read -p "Enter display title: " _TITLE

    [ -z "${_TITLE}" ] && continue
  done
}

get_label
get_title
get_path

notice "$(printf "Label: ${BOLD}%s${NC}" "${_LABEL}")"
notice "$(printf "Title: ${BOLD}%s${NC}" "${_TITLE}")"
notice "$(printf "Path: ${BOLD}%s${NC}" "${_PATH}")"

_PATH_BASH="${_PATH}/bash"
_PATH_FUNCTIONS="${_PATH_BASH}/functions"

_FILE_BASHRC="${_PATH_BASH}/bashrc"
_FILE_TOOLS="${_PATH_FUNCTIONS}/03-tools.sh"

if ! mkdir -p "${_PATH_FUNCTIONS}"; then
  error "$(printf "Failed to create directory: ${GREEN}%s${NC}" "${_PATH_FUNCTIONS}")"
  exit 1
fi

# Populate bashrc

cat << EOF > "${_FILE_BASHRC}"

__default_dir="${_PATH}"

export ${_LABEL}ToolsDir="\${__current_module_dir:-\${__default_dir}}"

if [ -d "\$${_LABEL}ToolsDir/bash/functions" ]; then
  for functionFile in \$${_LABEL}ToolsDir/bash/functions/*sh; do
    # Note: Sourcing in one line by wildcard wouldn't work.
    . "\$functionFile"
  done
fi

# Load in host-specific definitions, if any exist.
if [ -f "\$${_LABEL}ToolsDir/bash/functions/hosts/\${HOSTNAME%-*}.sh" ]; then
  . "\$${_LABEL}ToolsDir/bash/functions/hosts/\${HOSTNAME%-*}.sh"
fi
EOF

# Populate tools

cat << EOF > "${_FILE_TOOLS}"
update-tools-${_LABEL}(){

  # Make sure that some joker didn't go and unset the ${_LABEL}ToolsDir
  #     variable after this function was defined.
  if [ -z "\$${_LABEL}ToolsDir" ]; then
    error '${_TITLE} directory is unknown! It should be recorded in the \$${_LABEL}ToolsDir variable.'
    return 1
  fi

  update-repo "\$${_LABEL}ToolsDir" "${_TITLE}"

  # Confirm the permissions on the module directory
  #     Do this whether or not the version control update actually succeeded.
  chmod 700 "\$${_LABEL}ToolsDir"
}
EOF

# Set up permissions
chmod -R 700 "${_PATH}"
while read f; do
  [ -z "${f}" ] && continue
  chmod 600 "${f}"
done <<< "$(find "${_PATH}" -type f)"

# Set up version control
git -C "${_PATH}" init
git -C "${_PATH}" add .
git -C "${_PATH}" commit -m "Initial commit of ${_TITLE}."
