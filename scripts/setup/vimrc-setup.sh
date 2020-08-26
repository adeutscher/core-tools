#!/bin/bash

# Load common functions.
# shellcheck disable=SC1090
. "$(dirname "${0}")/functions.sh"

CONTENT="$(cat << EOF
let b:did_indent = 1 " Disable auto-indent
set mouse-=a         " Disable auto-visual select.
EOF
)"

"${DOTFILE_SCRIPT}" "${HOME}/.vimrc" core-tools-vimrc - '"' <<< "${CONTENT}"
