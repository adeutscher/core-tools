#!/bin/bash

# Load common functions.
. "$(dirname "${0}")/functions.sh"

crontab_contents="$(crontab -l)\n"
marker="core-tools-crontab"

# Prep new tasks in case we need to use them.
# Mostly outside of the if statement just because it looks better without indentation shenanigans.
new_tasks="$(cat << EOF
# Example of job definition:
# .---------------- minute (0 - 59)
# |  .------------- hour (0 - 23)
# |  |  .---------- day of month (1 - 31)
# |  |  |  .------- month (1 - 12) OR jan,feb,mar,apr ...
# |  |  |  |  .---- day of week (0 - 6) (Sunday=0 or 7) OR sun,mon,tue,wed,thu,fri,sat
# |  |  |  |  |
# *  *  *  *  * command to be executed

# Phrasing also accepts time ranges:
#   * Every hour, both on the hour and at 30 minutes: 0,30 * * * * <command>
#   * To run at every hour between 9am and 5pm: 0 9-17 * * * <command>

# Rotate temporary directory.
@reboot "$toolsDir/scripts/files/make-temp.sh" 2>/dev/null >&2
1 0 * * * "$toolsDir/scripts/files/make-temp.sh" 2>/dev/null >&2
EOF
)"

temp_file="$(mktemp)"
printf "${crontab_contents}" > "${temp_file}"
temp_file_checksum="$(md5sum "${temp_file}" | cut -d' ' -f1)"
"${DOTFILE_SCRIPT}" "${temp_file}" "${marker}" - <<< "${new_tasks}"
temp_file_checksum_new="$(md5sum "${temp_file}" | cut -d' ' -f1)"

if [[ "${temp_file_checksum}" != "${temp_file_checksum_new}" ]]; then
  cat "${temp_file}" | crontab -
  success "Installing new crontab"
fi
rm "${temp_file}"
