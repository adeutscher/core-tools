#!/bin/bash

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
  printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

success(){
  printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __warning_count=$((${__warning:-0}+1))
}

# Label Functions

cacheFile="${INDEX_NETWORK_CACHE:-$toolsCache/network-index.csv}"
dataFile="${INDEX_NETWORK_DATA:-$secureToolsDir/files/tool-data/network-index.csv}"

vendorCacheFile="${INDEX_NETWORK_CACHE:-$toolsCache/vendor-mac.psv}"
vendorDataFile="${INDEX_NETWORK_DATA:-$secureToolsDir/files/tool-data/vendor-mac.psv}"

# Look in a data file in the secure/ directory to try to resolve MAC addresses to a record.
# If the file doesn't exist or there is no entry, print nothing and let above logic handle it.
__get_mac_record(){
    if [ -n "$1" ] && [ -f "$dataFile" ]; then
        grep -Pim1 "^([^,]*,){2}$1," "$cacheFile" 2> /dev/null || grep -Pim1 "^([^,]*,){2}$1," "$dataFile" 2> /dev/null | tee -a "$cacheFile"
    fi
}

__get_mac_description(){
    if [ -n "$1" ]; then
        __get_mac_record "$1" | cut -d',' -f 7
    fi
}

__get_mac_label(){
    if [ -n "$1" ]; then
        __get_mac_record "$1" | cut -d',' -f 4
    fi
}

__get_mac_type(){
    if [ -n "$1" ]; then
        __get_mac_record "$1" | cut -d',' -f 2
    fi
}

__get_mac_vendor_inner(){
    if [ -n "$1" ] && [ -f "$vendorDataFile" ]; then
        grep -im1 "^${1:0:8}" "$vendorCacheFile" 2> /dev/null ||  grep -im1 "^${1:0:8}" "$vendorDataFile" | tee -a "$vendorCacheFile" 2> /dev/null
    fi
}

bluetooth_disconnect(){
    if [ -z "$1" ] || [[ ! "$1" =~ ^([a-zA-Z0-9]{2}:){5}([a-zA-Z0-9]{2}) ]]; then
       # No argument or invalid format.
        error "$(printf "Usage: ${BLUE}%s${NC} device-bssid|all" "$(basename "$0")")"
        return 1
    fi

    # If __get_mac_label is available from secure tools, try to resolve it.
    local label="$(__get_mac_label $1)"

    if [ -z "$label" ]; then
        # Try to use vendor as a fallback for more information.
        # If __get_mac_label is available, assume that __get_mac_vendor is available
        local vendor="$(__get_mac_vendor $1)"
    fi

    # Check to see whether or not we are already connected to this device.
    if ! hcitool con 2> /dev/null |sed -n /[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]/p | awk '{print $3}' | grep -qm1 "$1"; then
        # Device is not already connected.

        if [ -n "$label" ]; then
            notice "$(printf "Device is not connected: ${BOLD}%s${NC} (${BOLD}%s${NC})" "$label" "$1")"
        elif [ -n "$vendor" ]; then
            notice "$(printf "Device is not connected: ${BOLD}%s${NC} device (${BOLD}%s${NC})" "$vendor" "$1")"
        else
            notice "$(printf "Device is not connected: ${BOLD}%s${NC}" "$1")"
        fi
    elif ! type expect 2> /dev/null >&2; then
        # Humour the user up to the point of announcing the pending connection to check for the expect command.
        error "$(printf "${BLUE}%s${NC} is not installed. Install or connect manually with ${BLUE}%s${NC}" "expect" "bluetoothctl")"
        return 127
    else
        # Device is not connected.

        if [ -n "$label" ]; then
            notice "$(printf "Disconnecting from device: ${BOLD}%s${NC} (${BOLD}%s${NC})" "$label" "$1")"
        elif [ -n "$vendor" ]; then
            notice "$(printf "Disconnecting from device: ${BOLD}%s${NC} device (${BOLD}%s${NC})" "$vendor" "$1")"
        else
            notice "$(printf "Disconnecting from device: ${BOLD}%s${NC}" "$1")"
        fi
        $toolsDir/scripts/bluetooth/bluetooth-disconnect.exp "$1"
    fi
}

bluetooth_disconnect_all(){
    local devices="$(hcitool con 2> /dev/null |sed -n /[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]/p | awk '{print $3}')"

    if [ -z "$devices" ]; then
        notice "No Bluetooth devices are currently connected."
        return
    fi

    notice "$(printf "Disconnecting from all currently connected ${BOLD}%s${NC} Bluetooth devices." "$(wc -w <<< "$devices")")"

    for __device in ${devices}; do
        bluetooth_disconnect "$__device"

        # Cycling through multiple devices failed with no delay. Unsure why.
        # Wait until hcitool registers the device in the device in the current loop as gone.
        while hcitool con | grep -q "$__device"; do
            sleep .5
        done
    done

    # Axe loop variable
    unset __device
}

if grep -iqw "^all$" <<< "$1"; then
    bluetooth_disconnect_all
else
    bluetooth_disconnect "$1"
fi
