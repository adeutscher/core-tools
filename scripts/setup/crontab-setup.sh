#!/bin/bash

# Load common functions.
. "$(dirname "${0}")/functions.sh"

crontab_contents="$(crontab -l)\n"

# Prep new tasks in case we need to use them.
# Mostly outside of the if statement just because it looks better without indentation shenanigans.
new_tasks="$(cat << EOF
# Rotate temporary directory.
@reboot "$toolsDir/scripts/files/make-temp.sh" 2>/dev/null >&2
1 0 * * * "$toolsDir/scripts/files/make-temp.sh" 2>/dev/null >&2
EOF
)"

temp_file="$(mktemp)"
printf "${crontab_contents}" > "${temp_file}"
temp_file_checksum="$(md5sum "${temp_file}" | cut -d' ' -f1)"
"${DOTFILE_SCRIPT}" "${temp_file}" core-tools-crontab - <<< "${new_tasks}"
temp_file_checksum_new="$(md5sum "${temp_file}" | cut -d' ' -f1)"

if [[ "${temp_file_checksum}" != "${temp_file_checksum_new}" ]]; then
  cat "${temp_file}" | crontab -
  success "Installing new crontab"
fi
rm "${temp_file}"
