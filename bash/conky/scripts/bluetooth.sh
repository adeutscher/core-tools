#!/bin/bash

# If CONKY_DISABLE_BLUETOOTH evaluates to true, then exit immediately
# Also do this if hcitool command is not available
if (( $CONKY_DISABLE_BLUETOOTH )) || ! type hcitool 2> /dev/null >&2; then
  exit 0
fi

# Load common utilities
. functions/common 2> /dev/null
. functions/network-labels 2> /dev/null

devices=$(hcitool con 2> /dev/null |sed -n /[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]/p | awk '{print $3}')

for device in ${devices}; do
    # We only have the Bluetooth device address to work with, so using hard-coded values.
    # For adding future device titles, I would advise a maximum length of 15 unless you want
    #    to bump up your Conky window width.

    if [ -f "$tempRoot/cache/bluetooth/$device.txt" ]; then
        report="${report}$(cat "$tempRoot/cache/bluetooth/$device.txt")\n"
    else

        label="$(__get_mac_label "$device")"

        # Append to current banner.
        entry=" ${label:-"Unknown Device"} [${device}]\n"

        if [ -z "$label" ]; then
            vendor="$(__get_mac_vendor "$device")"

            if [ -n "$vendor" ]; then
                entry="${entry}  └─Vendor: ${vendor}\n"
            fi
        fi

        report="${report}${entry}"
        # Cache entry for later.
        mkdir -p "$tempRoot/cache/bluetooth"
        printf "${entry}" > "$tempRoot/cache/bluetooth/$device.txt"     

        # TODO: What would be a nice colour to assign to some of this?
        ## Remember that this would require moving the sourcing of the 'common' file up a bit.
    fi
done

if [ -n "${report}" ]; then
    # Only bother to load in common items if there is report content to print.


    # Print banner and report content
    printf "\n\${color #${colour_network}}\${font Neuropolitical:size=16:bold}Bluetooth\$font\$color\$hr\n${report}"

fi
