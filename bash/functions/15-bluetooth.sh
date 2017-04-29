
if qtype bluetoothctl; then

    # Only add bluetooth features for machines with bluez installed.

    # Note: The Bluetooth connection function assumes that the device has already been fully paired in the past.

    bluetooth-connect(){

        if [ -z "$1" ] || [[ ! "$1" =~ ^([a-zA-Z0-9]{2}:){5}([a-zA-Z0-9]{2}) ]]; then
           # No argument or invalid format.
            error "$(printf "Usage: ${Colour_Command}%s${Colour_Off} device-bssid" "${FUNCNAME[0]}")"
            return 1
        fi

        if qtype __get_mac_label; then
            # If __get_mac_label is available from secure tools, try to resolve it.
            local label="$(__get_mac_label $1)"

            if [ -z "$label" ]; then
                # Try to use vendor as a fallback for more information.
                # If __get_mac_label is available, assume that __get_mac_vendor is available
                local vendor="$(__get_mac_vendor $1)"
            fi
        fi

        # Check to see whether or not we are already connected to this device.
        if hcitool con 2> /dev/null |sed -n /[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]/p | awk '{print $3}' | grep -qm1 "$1"; then
            # Device is already connected.
   
            if [ -n "$label" ]; then
                notice "$(printf "Already connected to device: ${Colour_Bold}%s${Colour_Off} (${Colour_Bold}%s${Colour_Off})" "$label" "$1")"
            elif [ -n "$vendor" ]; then
                notice "$(printf "Already connected to device: ${Colour_Bold}%s${Colour_Off} device (${Colour_Bold}%s${Colour_Off})" "$vendor" "$1")"
            else
                notice "$(printf "Already connected to device: ${Colour_Bold}%s${Colour_Off}" "$1")"
            fi

            # Do not bother continuing if we are already connected.
            # Not really an error condition.
            return 0

        elif ! qtype expect; then
            # Humour the user up to the point of announcing the pending connection to check for the expect command.
	    error "$(printf "${Colour_Command}%s${Colour_Off} is not installed. Install or connect manually with ${Colour_Command}%s${Colour_Off}" "expect" "bluetoothctl")"
            return 127
        else
            # Device is not currently connected.
            if [ -n "$label" ]; then
                notice "$(printf "Trying to connect to device: ${Colour_Bold}%s${Colour_Off} (${Colour_Bold}%s${Colour_Off})" "$label" "$1")"
            elif [ -n "$vendor" ]; then
                notice "$(printf "Trying to connect to device: ${Colour_Bold}%s${Colour_Off} device (${Colour_Bold}%s${Colour_Off})" "$vendor" "$1")"
            else
                notice "$(printf "Trying to connect to device: ${Colour_Bold}%s${Colour_Off}" "$1")"
            fi

            $toolsDir/scripts/bluetooth/bluetooth-connect.exp "$1"
        fi

    }    

    bluetooth-disconnect(){

        if [ -z "$1" ] || [[ ! "$1" =~ ^([a-zA-Z0-9]{2}:){5}([a-zA-Z0-9]{2}) ]]; then
           # No argument or invalid format.
            error "$(printf "Usage: ${Colour_Command}%s${Colour_Off} device-bssid" "${FUNCNAME[0]}")"
            return 1
        fi

        if qtype __get_mac_label; then
            # If __get_mac_label is available from secure tools, try to resolve it.
            local label="$(__get_mac_label $1)"

            if [ -z "$label" ]; then
                # Try to use vendor as a fallback for more information.
                # If __get_mac_label is available, assume that __get_mac_vendor is available
                local vendor="$(__get_mac_vendor $1)"
            fi
        fi

        # Check to see whether or not we are already connected to this device.
        if ! hcitool con 2> /dev/null |sed -n /[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]/p | awk '{print $3}' | grep -qm1 "$1"; then
            # Device is already connected.
   
            if [ -n "$label" ]; then
                notice "$(printf "Device is not connected: ${Colour_Bold}%s${Colour_Off} (${Colour_Bold}%s${Colour_Off})" "$label" "$1")"
            elif [ -n "$vendor" ]; then
                notice "$(printf "Device is not connected: ${Colour_Bold}%s${Colour_Off} device (${Colour_Bold}%s${Colour_Off})" "$vendor" "$1")"
            else
                notice "$(printf "Device is not connected: ${Colour_Bold}%s${Colour_Off}" "$1")"
            fi
        else
            # Device is connected.

            if [ -n "$label" ]; then
                notice "$(printf "Disconnecting from device: ${Colour_Bold}%s${Colour_Off} (${Colour_Bold}%s${Colour_Off})" "$label" "$1")"
            elif [ -n "$vendor" ]; then
                notice "$(printf "Disconnecting from device: ${Colour_Bold}%s${Colour_Off} device (${Colour_Bold}%s${Colour_Off})" "$vendor" "$1")"
            else
                notice "$(printf "Disconnecting from device: ${Colour_Bold}%s${Colour_Off}" "$1")"
            fi

            $toolsDir/scripts/bluetooth/bluetooth-disconnect.exp "$1"

        fi
    }

    bluetooth-disconnect-all(){
        local devices="$(hcitool con 2> /dev/null |sed -n /[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]:[0-9A-F][0-9A-F]/p | awk '{print $3}')"

        for __device in ${devices}; do
            
            bluetooth-disconnect "$__device"

            # Cycling through multiple devices failed with no delay. Unsure why.
            # Wait until hcitool registers the device in the device in the current loop as gone.
            while hcitool con | grep -q "$__device"; do
                sleep .5
            done

        done

        # Axe loop variable
        unset __device
    }

    if qtype dbus-send; then
        # Android Phone Tether Function
        android-tether(){

            if [ -z "$1" ] || [[ ! "$1" =~ ^([a-zA-Z0-9]{2}:){5}([a-zA-Z0-9]{2}) ]]; then
                error "$(printf "Usage: ${Colour_Command}android-tether${Colour_Off} bssid")"
                return 1
            fi

            local clean_mac=$(sed "s/:/_/g" <<< "$1")

            if qtype __get_mac_label; then
                # If __get_mac_label is available from secure tools, try to resolve it.
                local label="$(__get_mac_label $1)"

                if [ -z "$label" ]; then
                    # Try to use vendor as a fallback for more information.
                    # If __get_mac_label is available, assume that __get_mac_vendor is available
                    local vendor="$(__get_mac_vendor $1)"
                fi
            fi

            if ! hcitool con | grep -q "$1"; then
                if [ -n "$label" ]; then
                    notice "$(printf "Device is not connected: ${Colour_Bold}%s${Colour_Off} (${Colour_Bold}%s${Colour_Off})" "$label" "$1")"
                elif [ -n "$vendor" ]; then
                    notice "$(printf "Device is not connected: ${Colour_Bold}%s${Colour_Off} device (${Colour_Bold}%s${Colour_Off})" "$vendor" "$1")"
                else
                    notice "$(printf "Device is not connected: ${Colour_Bold}%s${Colour_Off}" "$1")"
                fi
                return 1
            fi

            if [ -n "$label" ]; then
                notice "$(printf "Tethering to device (device settings permitting): ${Colour_Bold}%s${Colour_Off} (${Colour_Bold}%s${Colour_Off})" "$label" "$1")"
            elif [ -n "$vendor" ]; then
                notice "$(printf "Tethering to device (device settings permitting): ${Colour_Bold}%s${Colour_Off} device (${Colour_Bold}%s${Colour_Off})" "$vendor" "$1")"
            else
                notice "$(printf "Tethering to device (device settings permitting): ${Colour_Bold}%s${Colour_Off}" "$1")"
            fi

            for __device in $(hciconfig | grep -o "^[a-z0-9]*"); do
                dbus-send --system --type=method_call --dest=org.bluez /org/bluez/$__device/dev_$clean_mac org.bluez.Network1.Connect string:'nap'
            done

            unset __device
        }

        # Not like the tether function at all.
        # Some would say it's the reverse.
        android-tether-disconnect(){

            if [ -z "$1" ] || [[ ! "$1" =~ ^([a-zA-Z0-9]{2}:){5}([a-zA-Z0-9]{2}) ]]; then
                error "$(printf "Usage: ${Colour_Command}android-tether-disconnect${Colour_Off} bssid")"
                return 1
            fi

            local clean_mac=$(sed "s/:/_/g" <<< "$1")

            if qtype __get_mac_label; then
                # If __get_mac_label is available from secure tools, try to resolve it.
                local label="$(__get_mac_label $1)"

                if [ -z "$label" ]; then
                    # Try to use vendor as a fallback for more information.
                    # If __get_mac_label is available, assume that __get_mac_vendor is available
                    local vendor="$(__get_mac_vendor $1)"
                fi
            fi

            if ! hcitool con | grep -q "$1"; then
                if [ -n "$label" ]; then
                    notice "$(printf "Device is not connected: ${Colour_Bold}%s${Colour_Off} (${Colour_Bold}%s${Colour_Off})" "$label" "$1")"
                elif [ -n "$vendor" ]; then
                    notice "$(printf "Device is not connected: ${Colour_Bold}%s${Colour_Off} device (${Colour_Bold}%s${Colour_Off})" "$vendor" "$1")"
                else
                    notice "$(printf "Device is not connected: ${Colour_Bold}%s${Colour_Off}" "$1")"
                fi
                return 1
            fi

            if [ -n "$label" ]; then
                notice "$(printf "Untethering from device: ${Colour_Bold}%s${Colour_Off} (${Colour_Bold}%s${Colour_Off})" "$label" "$1")"
            elif [ -n "$vendor" ]; then
                notice "$(printf "Untethering from device: ${Colour_Bold}%s${Colour_Off} device (${Colour_Bold}%s${Colour_Off})" "$vendor" "$1")"
            else
                notice "$(printf "Untethering from device: ${Colour_Bold}%s${Colour_Off}" "$1")"
            fi

            for __device in $(hciconfig | grep -o "^[a-z0-9]*"); do
                dbus-send --system --type=method_call --dest=org.bluez /org/bluez/$__device/dev_$clean_mac org.bluez.Network1.Disconnect
            done

            unset __device
        }
    fi

fi
