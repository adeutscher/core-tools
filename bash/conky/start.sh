#!/bin/bash

dir="$(dirname $0)"
. "$dir/functions/common"
countdown=3

get_pos(){

    gapX=10
    gapY=35

    if [ "$(xrandr --current 2> /dev/null | grep " connected" | wc -l)" -eq 1 ]; then
        posX=$gapX
        posY=$gapY
    else
        local totalX="$(xdpyinfo 2> /dev/null | grep dimensions | awk '{ print $2 }' | cut -d'x' -f1)"
        local totalY="$(xdpyinfo 2> /dev/null | grep dimensions | awk '{ print $2 }' | cut -d'x' -f2)"

        # If we have specified a CONKY_SCREEN variable in our BASH config and such a screen is present, use that one to calculate our offsets.
        if [ -n "$CONKY_SCREEN" ]; then
            local primary_monitor_info="$(xrandr --current 2> /dev/null | grep -m1 "^$CONKY_SCREEN " | grep -oPm1 "\d{1,}x\d{1,}(\+\d{1,}){2}")"
        else
            local primary_monitor_info="$(xrandr --current 2> /dev/null | grep -m1 "primary" | grep -oPm1 "\d{1,}x\d{1,}(\+\d{1,}){2}")"
        fi

        if [ -z "$primary_monitor_info" ]; then
            # If no valid output from CONKY_SCREEN attempt, or if xrandr does not clearly say which is the 'primary' monitor, 
            #     then simply go with the first connected one.
            local primary_monitor_info="$(xrandr --current 2> /dev/null | grep -m1 " connected" | grep -oPm1 "\d{1,}x\d{1,}(\+\d{1,}){2}")"
        fi

        local mainX="$(cut -d'x' -f1 <<< "$primary_monitor_info")"
        local mainY="$(cut -d'x' -f2 <<< "$primary_monitor_info" | cut -d'+' -f1)"

        local offX="$(cut -d'+' -f2 <<< "$primary_monitor_info")"
        local offY="$(cut -d'+' -f3 <<< "$primary_monitor_info")"

        if [ -n "$totalX" ] && [ -n "$totalY" ] && [ -n "$mainX" ] && [ -n "$mainY" ] && [ -n "$offX" ] && [ -n "$offY" ]; then
            #echo "$totalX- ($mainX+$offX) + $gapX"
            #echo "$totalY- ($mainY+$offY) + $gapY"
            posX="$(($totalX- ($mainX+$offX) + $gapX))"
            posY="$(($totalY- ($mainY+$offY) + $gapY))"
        else
            return 1
        fi
    fi

}

if ! get_pos; then
    message="Failed to get X dimensions! Is the DISPLAY variable set (e.g. export DISPLAY=:0.0)"

    printf "%s\n" "$message"
    timeout 0.5 notify-send --icon=important "$message" 2> /dev/null >&2

    exit 1
fi

# Clear cache.
rm -rf "$tempRoot/cache"
# Re-make cache, plus reports
mkdir -p "$tempRoot/cache" "$tempRoot/reports"

# Check for tmpfs, plus a crude check for debug mode.
if [ -n "$tempRoot" ] && mkdir -p "$tempRoot" && df "$tempRoot" 2> /dev/null | grep -q '^tmpfs' && [[ "$1" != "debug" ]]; then
    # Transfer to /tmp so that we're reading off of tmpfs instead of our hard drive
    printf "Stating conky from tmpfs.\n"
    configDir="$tempRoot/config"
    mkdir -p "$configDir" || printf "Failed to create directory: %s\n" "$configDir"
    (rsync -av "$dir/" "$configDir/" 2> /dev/null >&2 && printf "Successfully synced files to tmpfs...\n") || printf "Failed to sync files...\n"
    echo "$dir/../../" > "$tempRoot/tools-dir"
    cd "$configDir"
    location=tmpfs
else
    printf "Stating conky from regular location.\n"
    cd "$dir"
    location=tools
fi

# Lazy switch for debug mode...
if [ "$1" != "debug" ]; then
  message="$(printf "Conky should appear in %ds..." "$countdown")"
else
  message="Running conky in debug mode..."
fi

# Try running notify-send, ignoring all error messages
#   (like if notify-send is not present, for example)
timeout 0.5 notify-send --icon=esd "$(printf "%s\nLocation: %s" "$message" "$location")" 2> /dev/null >&2
# Print the message to stdout for good measure.
echo "$message"

# Lazy switch for debug mode...
if [ "$1" != "debug" ]; then
    # Standard mode
    # Sleep and start
    sleep $countdown && conky -c conkyrc -a bottom_right -x $posX -y $posY &
else
    # Debug mode
    # If we're in debug mode, run conky immediately in the foreground.

    # Print off the conky command being used for good measure.
    printf "\nconky -c conkyrc -a bottom_right -x $posX -y $posY\n\n"

    # Start conky
    conky -c conkyrc -a bottom_right -x $posX -y $posY
fi

cd "$OLDPWD"
