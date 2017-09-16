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

# Not like the tether function at all.
# Some would say it's the reverse.
android_tether_disconnect(){

    if [ -z "$1" ] || [[ ! "$1" =~ ^([a-zA-Z0-9]{2}:){5}([a-zA-Z0-9]{2}) ]]; then
        error "$(printf "Usage: ${BLUE}%s${NC} bssid" "$(basename $0)")"
        return 1
    fi

    local clean_mac=$(sed "s/:/_/g" <<< "$1")

    # If __get_mac_label is available from secure tools, try to resolve it.
    local label="$(__get_mac_label $1)"

    if [ -z "$label" ]; then
        # Try to use vendor as a fallback for more information.
        # If __get_mac_label is available, assume that __get_mac_vendor is available
        local vendor="$(__get_mac_vendor $1)"
    fi

    if ! hcitool con | grep -q "$1"; then
        if [ -n "$label" ]; then
            notice "$(printf "Device is not connected: ${BOLD}%s${NC} (${BOLD}%s${NC})" "$label" "$1")"
        elif [ -n "$vendor" ]; then
            notice "$(printf "Device is not connected: ${BOLD}%s${NC} device (${BOLD}%s${NC})" "$vendor" "$1")"
        else
            notice "$(printf "Device is not connected: ${BOLD}%s${NC}" "$1")"
        fi
        return 1
    fi

    if [ -n "$label" ]; then
        notice "$(printf "Untethering from device: ${BOLD}%s${NC} (${BOLD}%s${NC})" "$label" "$1")"
    elif [ -n "$vendor" ]; then
        notice "$(printf "Untethering from device: ${BOLD}%s${NC} device (${BOLD}%s${NC})" "$vendor" "$1")"
    else
        notice "$(printf "Untethering from device: ${BOLD}%s${NC}" "$1")"
    fi

    for __device in $(hciconfig | grep -o "^[a-z0-9]*"); do
        dbus-send --system --type=method_call --dest=org.bluez /org/bluez/$__device/dev_$clean_mac org.bluez.Network1.Disconnect
    done

    unset __device
}

if ! type dbus-send 2> /dev/null >&2; then
    error "$(printf "Command not found: ${BLUE}%s${NC}" dbus-send)"
    exit 1
fi

android_tether_disconnect "$1"
