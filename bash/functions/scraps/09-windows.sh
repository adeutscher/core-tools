
##
## Reboot to Windows ##
##

# I originally made this function as a global thing to automatically check for a Windows boot
#     on every system with the core tools (and only load the function if one was found),
#     but I reminded myself that I only have one such system.
# It made more sense to put a copy of this in a host-specific configuration in a private module,
#     but leaving this here in scraps/ in case someone finds it useful.

# Reminder: To set this up (use grub2-__ commands on RHEL-based distributions):
## 1. In /etc/default/grub, confirm that GRUB_DEFAULT is set to saved
## 2. Run "grub-set-default X". Replace X with the zero-indexed entry in your GRUB config where you want to boot to by default.
## 3. Write the output of grub-mkconfig to overwrite your existing grub.cfg
##     (make a backup if it makes you feel better)

# Troubleshooting note: If your /boot/grub/grubenv file (or grubenv in a similar location) is a symlink to another grubenv
#     using an absolute path, you might have a bad time because GRUB will have no concept of the Linux system's /boot/ directory.
# If this applies to your system, try replacing the absolute symlink with a relative link that does not step
#     outside of the partition mounted on /boot/

# Different distributions have different ideas about where grub.cfg lives.
# Non-root users may not even have permission to view it.
# Trusting that the first 'grub.cfg' that we find to have the correct index.

if __is_unix; then

    GRUB_CONFIG=$(find /boot -name 'grub.cfg' 2> /dev/null | head -n1)

    if [ -n "$GRUB_CONFIG" ]; then
        # Trust that only the Windows OS will have "Windows" in the menuentry line.
        WINDOWS_BOOT_INDEX="$(grep "^menuentry" "$GRUB_CONFIG" | grep -winm1 windows | cut -d: -f1)" # Note: Not zero-indexed.
    else
        unset GRUB_CONFIG WINDOWS_BOOT_INDEX
    fi

    if [ -n "$WINDOWS_BOOT_INDEX" ]; then
        reboot-windows-prep(){
            if [ -z "$WINDOWS_BOOT_INDEX" ]; then
                return 1
            fi

            local command=grub-reboot
            if qtype grub2-reboot; then
                # Assume if grub2-reboot then there is no grub-reboot
                local command=grub2-reboot
            fi

            # Assume that a distro will only have one grubenv until proven otherwise.
            local grubenv=$(find /boot -type f -name grubenv 2> /dev/null | head -n1)

            # Only call sudo if we cannot already write to the file.
            if [ ! -w "$grubenv" ]; then
                local sudo=sudo
            fi
            
            # The && does not really matter at the moment,
            #   since failing to set grub2-editenv will not
            #   give a non-zero exit code (with an unedited grub2-reboot script)...

            # Decrease by one to fix the variable to zero indexing.
            $sudo $command $(($WINDOWS_BOOT_INDEX-1)) && warning "On this computer's next boot only, Windows will be the default."
        }
    fi
fi:w

