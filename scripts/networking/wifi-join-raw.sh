#!/bin/bash

# Main script functions.

check_commands(){
    # Double-check that we have the necessary commands for each task.

    for comm in iw nmcli wpa_supplicant ifconfig iwconfig; do
        if ! type $comm 2> /dev/null >&2; then
            local missing="$missing $comm"
        fi
    done

    if [ -n "$missing" ]; then
        error "$(printf "The following missing commands are required in order to use this script: ${BLUE}%s${NC}" "$missing")"
        exit 1
    fi
}

join(){
    
    # Set our variables BEFORE the root check in order to make use of some user-only environment variables.
    interface=${1:-wlan1}
    ssid="$2"
    password="$3"

    if [ -z "$ssid" ]; then
        error "$(printf "Insufficient arguments. Usage: ${GREEN}%s${NC} interface ssid [password]" "$(basename "$0")")" >&2
        exit 1
    fi

    # Confirm that the requested interface even exists before we try to use sudo.
    if ! ip a s "$interface" 2> /dev/null >&2; then
        error "$(printf "No \"${BOLD}%s${NC}\" interface found." "$interface")" >&2
        exit 2
    fi
    
    # Confirm that the given interface is actually a wireless interface
    if ! iw dev | grep -q "Interface $interface"; then
        error "$(printf "${BOLD}%s${NC} is not actually a wireless interface. Abort!" "$interface")" >&2
        exit 2
    fi
    
    # Confirm that the given interface is not managed by NetworkManager
    if nmcli device status 2> /dev/null | grep -v unmanaged | tail -n +2 | cut -d' ' -f1 | grep -q '^'$interface'$'; then
        error "$(printf "${BOLD}%s${NC} is still managed by NetworkManager. Abort!" "$interface")" >&2
        exit 3
    fi

    # Access point SSID cannot be more than 33 characters long
    ssid_length="$(($(wc -c <<< "$ssid")-1))"
    if [ "$(echo "$ssid" | wc -c)" -gt 33 ]; then
       error "$(printf "Access point SSID cannot be more than 33 characters long (requested SSID was $BOLD%d$NC characters)." "$ssid_length")" >&2
       exit 4
    fi

    # Naming the temporary configuration file in part off of the interface to allow us to
    #  possibly review configurations for multiple simultaneous instances of wpa-supplicant.
    wpa_config="/tmp/wpa-supplicant-$interface-temp.conf"

    # Set a umask so that only the current user and root can read from the configuration file.
    umask 077
        
    # Track exit codes while building our configuration file. If anything fails, exit out.
    result=0
    
    if [ -z "$password" ]; then
        # Open network
        printf 'network={\nssid="%s"\nkey_mgmt=NONE\n}\n' "$ssid" > "$wpa_config"
        result=$(($? + $result))
    else
        # Secure network, need to use a template
    
        # Passphrase must be 8..63 characters
        password_length="$(($(wc -c <<< "$password")-1))"
        if [ "$password_length" -lt 8 ] || [ "$password_length" -gt 63 ]; then
            error "Passphrase must be 8..63 characters" >&2
            exit 5
        fi
    
        # Set up template file
        
        wpa_passphrase "$ssid" <<< "$password" > "$wpa_config"
        result=$(($? + $result))
    fi # End password check's else-statement.

    echo "ctrl_interface=/var/run/wpa_supplicant_$interface" >> "$wpa_config"
    result=$(($? + $result))
    echo "ctrl_interface_group=wheel" >> "$wpa_config"
    result=$(($? + $result))

    if [ "$result" -gt 0 ]; then
        # Cut out if there was an error making our template file.
        # I do not expect there to be any problem, but just in case...
        error "Error creating template file: ${GREEN}%s${NC}" "$wpa_config" >&2
        exit 3
    fi

    # Note: wpa_supplicant is confirmed to be case-insensitive.
    if grep -iPq '^([a-f0-9]{2}[:|-]){5}[a-f0-9]{2}$' <<< "$ssid"; then
        notice "Our \"SSID\" is actually in the format of a MAC address. Assuming that a specific BSSID was actually requested."
        sed -i "s/ssid=\"$ssid\"/bssid=$ssid/g" "$wpa_config"
        prefix="B"
    fi

    # Print type-specific messages after successfully making the template file.
    if [ -z "$password" ]; then
        # Open network
        notice "$(printf "Attempting to connect to open network. ${prefix}SSID: \"${BOLD}%s${NC}\"" "$ssid")"
    else
        # WEP/WPA/WPA2-secured network.
        notice "$(printf "Attempting to connect to secured wireless network. ${prefix}SSID: ${BOLD}%s${NC}" "$ssid")"
    fi
    warning "$(printf "${BOLD}Remember!${NC} If successful, you will still need to run ${BLUE}dhclient${NC} or set an IP address manually!")"

    # Finally, run wpa_suplicant
    # Note: wpa_supplicant will hold this terminal while it runs.
    sudo wpa_supplicant -i $interface -c "$wpa_config"
}

# Notice colours and functions for formatted output.

# Define colours
BLUE='\033[1;34m'
GREEN='\033[1;32m'
RED='\033[1;31m'
YELLOW='\033[1;93m'
BOLD='\033[1m'
NC='\033[0m' # No Color

error(){
    printf "$RED"'Error'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

notice(){
    printf "$BLUE"'Notice'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

warning(){
    printf "$YELLOW"'Warning'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

# Now that everything is loaded, run the actual script.

check_commands
join $@
