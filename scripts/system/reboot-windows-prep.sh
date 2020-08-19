#!/bin/bash

##
## Reboot to Windows ##
##

# Reminder: To set this up (use grub2-__ commands on RHEL-based distributions):
## 1. In /etc/default/grub, confirm that GRUB_DEFAULT is set to saved
## 2. Run "grub-set-default X". Replace X with the zero-indexed entry in your GRUB config where you want to boot to by default.
## 3. Write the output of grub-mkconfig to overwrite your existing grub.cfg
##     (make a backup if it makes you feel better)

# Troubleshooting note: If your /boot/grub/grubenv file (or grubenv in a similar location) is a symlink to another grubenv
#     using an absolute path, you might have a bad time because GRUB will have no concept of the Linux system's /boot/ directory.
# If this applies to your system, try replacing the absolute symlink with a relative link that does not step
#     outside of the partition mounted on /boot/

# Other notes:
#   Different distributions have different ideas about where grub.cfg lives.
#   Tested on Fedora systems.
#   Non-root users may not even have permission to view it.
#   Trusting that the first 'grub.cfg' that we find to have the correct index.

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
  printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
}

success(){
  printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
  __warning_count=$((${__warning_count:-0}+1))
}

# Script Functions

check_env(){
    local defaults="/etc/default/grub"
    if ! grep -q "^GRUB_DEFAULT=saved" "$defaults"; then
        error "$(printf "${BOLD}%s${NC} not found in ${GREEN}%s${NC}." "GRUB_DEFAULT=saved" "$defaults")"
	exit 1
    fi
}

reboot_windows_prep(){
    if [ -z "$WINDOWS_BOOT_INDEX" ]; then
        return 1
    fi

    local command=grub-reboot
    if type grub2-reboot 2> /dev/null >&2; then
        # Assume if grub2-reboot then there is no grub-reboot
        local command=grub2-reboot
    fi

    # Assume that a distro will only have one grubenv until proven otherwise.
    local grubenv
    grubenv=$(find /boot -type f -name grubenv 2> /dev/null | head -n1)

    # Only call sudo if we cannot already write to the file.
    if [ -z "$grubenv" ]; then
        notice "$(printf "No ${GREEN}%s${NC} file found, ${BLUE}%s${NC} will be used." "grubenv" "sudo")"
        local sudo=sudo
    elif [ ! -w "$grubenv" ]; then
        notice "$(printf "The ${GREEN}%s${NC} file is not writable by current user ${BOLD}%s${NC}, ${BLUE}%s${NC} will be used." "${grubenv}" "$(whoami)" "sudo")"
        local sudo=sudo
    fi

    # The && does not really matter at the moment,
    #   since failing to set grub2-editenv will not
    #   give a non-zero exit code (with an unedited grub2-reboot script)...

    # Decrease by one to fix the variable to zero indexing.
    $sudo $command $((WINDOWS_BOOT_INDEX-1)) && warning "On this computer's next boot only, Windows will be the default."
}

check_env

# Use the first grub config that we can find.
GRUB_CONFIG=$(find /boot -name 'grub.cfg' 2> /dev/null | head -n1)

if [ -z "${GRUB_CONFIG}" ]; then
  error "$(printf "Unable to find a GRUB config file in ${GREEN}%s${NC}." "/boot")"
  # The most likely reason for not being able to find a configuration is that the directory is only readable by root.
  (( "${EUID}" )) && notice "$(printf "Does the ${BOLD}%s${NC} user have proper read permissions?" "${USER}")"
  exit 1
fi

if [ -n "$GRUB_CONFIG" ]; then
    # Trust that only the Windows OS will have "Windows" in the menuentry line.
    WINDOWS_BOOT_INDEX="$(grep "^menuentry" "$GRUB_CONFIG" | grep -winm1 windows | cut -d: -f1)" # Note: Not zero-indexed.
fi

if [ -n "$WINDOWS_BOOT_INDEX" ]; then
    reboot_windows_prep
else
    error "$(printf "No windows boot found in ${GREEN}%s${GREEN}" "$GRUB_CONFIG")"
    exit 1
fi
