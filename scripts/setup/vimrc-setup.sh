#!/bin/bash

# Load common functions.
. "$(dirname "${0}")/functions.sh"

CONTENT="$(cat << EOF
let b:did_indent = 1
EOF
)"

"${DOTFILE_SCRIPT}" "${HOME}/.vimrc" core-tools-vimrc - "\"" <<< "${CONTENT}"
