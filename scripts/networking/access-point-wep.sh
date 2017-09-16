#!/bin/bash

# Set our variables BEFORE the root check in order to make use of some user-only environment variables.
interface=${1}
bridge=${2}
ssid="$3"
password="$4"

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
}

notice(){
    printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

success(){
    printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

warning(){
    printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

# Begin script logic.

if [ -z "$ssid" ]; then
    error "$(printf "Insufficient arguments. Usage: $GREEN%s$NC interface bridge ssid [password]" "$(basename $0)")" >&2
    exit 1
fi

if ! type 2> /dev/null >&2 hostapd; then
    error "$(printf "${BLUE}hostapd${NC} command is not available. Please install hostapd to continue.")" >&2
    exit 2
fi

# Confirm that the requested interface even exists before we try to use sudo.
if ! ip a s "$interface" 2> /dev/null >&2; then
    error "$(printf "No $BOLD%s$NC interface found." "$interface")" >&2
    exit 2
fi

# Confirm that the given interface is actually a wireless interface
if type iw 2> /dev/null >&2 && ! iw dev | grep -q "Interface $interface"; then
    error "$(printf "$BOLD%s$NC not actually a wireless interface. Abort!" "$interface")" >&2
    exit 2
fi

# Confirm that the given interface is not managed by NetworkManager
if type nmcli 2> /dev/null >&2 && nmcli device status 2> /dev/null | grep -v unmanaged | tail -n +2 | cut -d' ' -f1 | grep -q '^'$interface'$'; then
    error "$(printf "%s is still managed by NetworkManager. Abort!\n" "$interface")"
    exit 2
fi

# Confirm that the specified bridge exists.
if brctl show "${bridge}" 2>&1 | grep -iq "No such device"; then
    error "$(printf "Bridge interface \"$BOLD%s$NC\" not found." "${bridge}")" >&2
    exit 2
fi

# Naming the temporary configuration file in part off of the interface to allow us to
#  possibly review configurations for multiple simultaneous instances of hostapd.
hostapd_config="/tmp/hostapd-$interface-temp.conf"

# Using a template to manage settings in here
#   instead of managing multiple configurations

# Set a umask so that only the current user and root can read from the configuration file.
umask 077

# Write our initial template.
if ! cat << EOF > "$hostapd_config"
ssid=__SSID__
interface=__INTERFACE__
bridge=__BRIDGE__
channel=7
hw_mode=g
auth_algs=3

driver=nl80211

logger_stdout=-1
logger_stdout_level=2

max_num_sta=5

wep_default_key=1
wep_key1="__PASSPHRASE__"
wep_key_len_broadcast="__PASSPHRASE_LENGTH__"
wep_key_len_unicast="__PASSPHRASE_LENGTH__"
wep_rekey_period=300
EOF
then
    error "$(printf "Error writing to template file: ${GREEN}%s${NC}" "$hostapd_config")"
fi

# Access point password must be between 8 and 63 characters long
password_length="$(expr length "$password")"
if [ -n "$password" ]; then
    if [ "$password_length" -eq "5" ]; then
        key_size=64
    elif [ "$password_length" -eq "13" ]; then
        key_size=128
    else
        error "$(printf "WEP key must be 5 or 13 characters (given key was $BOLD%d$NC characters)." "$password_length")" >&2
        exit 3
    fi
fi

ssid_length="$(expr length "$ssid")"
if [ "$ssid_length" -gt 32 ]; then
   error "$(printf "Access point SSID cannot be more than 32 characters long (requested SSID was $BOLD%d$NC characters)." "$ssid_length")" >&2
   exit 4
fi

# Adjust our template with the appropriate values for our arguments

# Track exit codes. If anything fails, do not try to run hostapd.
result=0
sed 's/__SSID__$/'"$ssid"'/g' -i "$hostapd_config"
result=$(($? + $result))
sed 's/__INTERFACE__$/'"$interface"'/g' -i "$hostapd_config"
result=$(($? + $result))
sed 's/__BRIDGE__$/'"$bridge"'/g' -i "$hostapd_config"
result=$(($? + $result))

if [ -n "$password" ]; then
    # Password provided, WEP network.
    sed 's/__PASSPHRASE__"/'"$password"'"/g' -i "$hostapd_config"
    result=$(($? + $result))
    sed 's/__PASSPHRASE_LENGTH__"/'"$(expr length "$password")"'"/g' -i "$hostapd_config"
    result=$(($? + $result))
else
    # No password provides, open network
    sed '/^wep/d' -i "$hostapd_config"
    result=$(($? + $result))
fi
# Collect the result of either sed operation.
result=$(($? + $result))

if [ "$result" -gt 0 ]; then
    error "Errors occured with template substitution. Quitting...\n" >&2
    exit 5
fi

if [ -n "$password" ]; then
    notice "$(printf "Opening up a WEP-'protected' access point \"${BOLD}%s${NC}\" with ${BOLD}%d-bit key${NC} on ${BOLD}%s${NC} interface using ${BOLD}%s${NC} bridge." "$ssid" "$key_size" "$interface" "$bridge")"
    warning "$(printf "${BOLD}"'!!! WEP IS HILARIOUSLY INSECURE !!!'"${NC}")"
    warning "This script should only be used as part of a demonstration of how easy it is is to break into a WEP network."
else
    notice "$(printf "Opening up an open access point '${BOLD}%s${NC} on ${BOLD}%s${NC} interface using ${BOLD}%s${NC} bridge." "$ssid" "$interface" "$bridge")"
fi

sudo hostapd "$hostapd_config"
