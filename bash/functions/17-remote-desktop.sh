
##############################
 ############################
 # Remote Desktop Functions #
 ############################
##############################

# Functions for RDP/VNC, and anything else in a similar vein.

# Aliases for VNC
if qtype vncviewer; then
    alias vncviewer='\vncviewer -CompressLevel 9'
fi

if qtype vncserver; then
    alias vncserver-start='vncserver -autokill'
fi

if qtype x11vnc; then

    vnc-quick-read(){

        if [ -n "$1" ]; then
            notice "$(printf "Fast VNC Function. Password: ${Colour_Bold}%s${Colour_Off}" "${1:0:8}" )"
            # Sleep for a little bit in order to give the user time to read/notice the above message before x11vnc output floods the screen.
            # The function doesn't need to be instant-quick.
            sleep 2

            x11vnc -display :0 -auth guess -forever -shared -passwd "${1:0:8}" -viewonly
        else
            # Don't bother sleeping when there are no messages
            x11vnc -display :0 -auth guess -forever -shared -viewonly
        fi
    }

    vnc-quick-write(){
        if [ -z "$1" ]; then
            error "Please provide a password."
            return 1
        fi
        notice "$(printf "Fast VNC Function. Password: ${Colour_Bold}%s${Colour_Off}" "${1:0:8}" )"

        # Sleep for a little bit in order to give the user time to read/notice the above message before x11vnc output floods the screen.
        # The function doesn't need to be instant-quick.
        sleep 2

        x11vnc  -display :0 -auth guess -forever -shared -passwd "${1:0:8}"
    }

    # Quick VNC sharing, but with a specific monitor
    # Note: These are still a bit experimental

    # XDAMAGE is not working well... misses: 187/211
    # Maybe an OpenGL app like Beryl or Compiz is the problem?
    # Use x11vnc -noxdamage or disable the Beryl/Compiz app.
    # To disable this check and warning specify -xdamage twice.

    vnc-share-mon-read(){
        if [ -z "$1" ]; then
            error "No monitor provided."
            return 1
        fi

        local __option="$1"

        if grep -Pq "^\d*$" <<< "$__option" && [ "$__option" -gt 0 ]; then
            # Argument was a number. Confirm that we have a monitor X to share.

            local __monitorNumber=$__option
            local __monitorName=$(xrandr --current | grep -w "connected" | sed -n "$__monitorNumber{p;q}" | cut -d' ' -f 1)
            if [ -z "$__monitorName" ]; then
                error "$(printf "Monitor ${Colour_Bold}#%d${Colour_Off} does not exist on this system." "$__monitorNumber")"
                return 1
            fi
            echo $__monitorNumber
            local __monitor="xinerama$(($__monitorNumber - 1))"
        else
            # Argument was given as a monitor name.
            # Case-insensitive for leniency.

            local __monitorName=$__option
            local __monitorNumber=$(xrandr --current | grep -w connected | grep -in "^$__monitorName\ " | cut -d':' -f 1)

            if [ -z "$__monitorNumber" ]; then
                error "$(printf "Monitor \"${Colour_Bold}%s${Colour_Off}\" does not exist on this system." "$__monitorName")"
                return 1
            fi

            # Silly: For display, get the properly-cased name of the monitor that we asked for.
            local __monitorName=$(xrandr --current | grep -w connected | grep -i "^$__monitorName\ " | cut -d' ' -f 1)

            local __monitor="xinerama$(($__monitorNumber - 1))"
        fi

        notice "$(printf "Sharing monitor ${Colour_Bold}#%d${Colour_Off} (${Colour_Bold}%s${Colour_Off})" "$__monitorNumber" "$__monitorName")"

        if [ -n "$2" ]; then
            notice "$(printf "Fast VNC Function. Password: ${Colour_Bold}%s${Colour_Off}" "${2:0:8}" )"
        fi

        # Sleep for a little bit in order to give the user time to read/notice the above message(s) before x11vnc output floods the screen.
        # The function doesn't need to be instant-quick.
        sleep 2

        if [ -n "$2" ]; then
            x11vnc -display :0 -auth guess -forever -shared -clip "$__monitor" -passwd "${2:0:8}" -viewonly
        else
            x11vnc -display :0 -auth guess -forever -shared -clip "$__monitor" -viewonly
        fi
    }

    vnc-share-mon-write(){
        if [ -z "$1" ]; then
            error "No monitor provided."
            return 1
        elif [ -z "$2" ]; then
            error "Please provide a password."
            return 1
        fi

        local __option="$1"

        if grep -Pq "^\d*$" <<< "$__option" && [ "$__option" -gt 0 ]; then
            # Argument was a number. Confirm that we have a monitor X to share.

            local __monitorNumber=$__option
            local __monitorName=$(xrandr --current | grep -w "connected" | sed -n "$__monitorNumber{p;q}" | cut -d' ' -f 1)
            if [ -z "$__monitorName" ]; then
                error "$(printf "Monitor ${Colour_Bold}#%d${Colour_Off} does not exist on this system." "$__monitorNumber")"
                return 1
            fi
            local __monitor="xinerama$(($__monitorNumber - 1))"
        else
            # Argument was given as a monitor name.
            # Case-insensitive for leniency.

            local __monitorName=$__option
            local __monitorNumber=$(xrandr --current | grep -w connected | grep -in "^$__monitorName\ " | cut -d':' -f 1)

            if [ -z "$__monitorNumber" ]; then
                error "$(printf "Monitor \"${Colour_Bold}%s${Colour_Off}\" does not exist on this system." "$__monitorName")"
                return 1
            fi

            # Silly: For display, get the properly-cased name of the monitor that we asked for.
            local __monitorName=$(xrandr --current | grep -w connected | grep -i "^$__monitorName\ " | cut -d' ' -f 1)

            local __monitor="xinerama$(($__monitorNumber - 1))"
        fi

        notice "$(printf "Sharing monitor ${Colour_Bold}#%d${Colour_Off} (${Colour_Bold}%s${Colour_Off})" "$__monitorNumber" "$__monitorName")"
        notice "$(printf "Fast VNC Function. Password: ${Colour_Bold}%s${Colour_Off}" "${2:0:8}" )"
        # Sleep for a little bit in order to give the user time to read/notice the above messages before x11vnc output floods the screen.
        # The function doesn't need to be instant-quick.
        sleep 2
        x11vnc  -display :0 -auth guess -forever -shared -clip "$__monitor" -passwd "${2:0:8}"
    }
fi

####################
# Function for RDP #
####################

# If we are using the nightly FreeRDP build, add it to our path.
__add_to_path_if_dir "/opt/freerdp-nightly/bin"

# If xfreerdp is present, add shortcuts.
if qtype xfreerdp; then
  alias rdp="$toolsDir/scripts/networking/rdp.py"
  alias rdp-small="rdp -g 800x600"
fi
