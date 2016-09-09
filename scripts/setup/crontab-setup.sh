#!/bin/bash

# Fallback in case toolsDir isn't picked up by the script for some reason.
if [ -z "$toolsDir" ]; then
    toolsDir="$(readlink -f "${0%/*}")"
fi

crontab_marker=common-crontab-marker
crontab_contents="$(crontab -l)"

# Prep new tasks in case we need to use them.
# Mostly outside of the if statement just because it looks better without indentation shenanigans.
new_tasks=$(cat << EOF
# $crontab_marker for grep's benefit.
# Rotate temporary directory.
@reboot "$toolsDir/scripts/files/make-temp.sh" 2>/dev/null >&2
1 0 * * * "$toolsDir/scripts/files/make-temp.sh" 2>/dev/null >&2
# End $crontab_marker jobs
EOF
)

if ! grep -qm1 "$crontab_marker" <<< "$crontab_contents"; then
    printf "Installing common crontab jobs...\n"
    printf "%s\n\n%s\n" "$crontab_contents" "$new_tasks" | crontab -
else
    printf "Common crontab tools are already installed!\n"
fi
