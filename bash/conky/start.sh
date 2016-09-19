#!/bin/bash

dir="$(dirname $0)"
. "$dir/functions/common"

usage(){
    cat << EOF
  Conky Start Script.
  Set CONKY_SCREEN to a monitor value to set a screen
    other than the rightmost of your desktop display

  Switches:
    -h          Print this menu and exit.
    -s screen   Select screen to use.
                Note: Overrides CONKY_SCREEN value.
    -d          Debug mode (will not run as a backup process or copy to tmpfs)
    -r          Restart by killing existing conky instances
                Note: This is done just by running "killall conky" for the moment.
                Would not play nice with multiple simultaneous configurations.
EOF
}

handle_arguments(){

    # Default values
    DEBUG=0
    RESTART=0

    if [ "$#" == "0" ]; then
        return 0
    fi

    while getopts "dhs:r" OPT $@; do
        case $OPT in
            d)
                printf "Enabling debug mode.\n"
                DEBUG=1
                ;;
            h)
                usage
                exit 0
                ;;
            r)
                RESTART=1
                ;;
            s)
                if xrandr --current 2> /dev/null | grep "^$OPTARG\ " | grep -qw connected; then
                    # If we have been given a valid connected monitor, set a value to CONKY_SCREEN
                    # The switch argument overrules any normal environment variable.
                    if [ -n "$CONKY_SCREEN" ]; then
                       printf "Screen set to %s (overriding CONKY_SCREEN value of %s).\n" "$OPTARG" "$CONKY_SCREEN"
                    else
                        printf "Screen set to %s.\n"
                    fi
                    CONKY_SCREEN=$OPTARG
                else
                    # Display option does not exist, or monitor is not connected.
                    printf "Monitor %s is not an active monitor.\n" "$OPTARG"
                    exit 1
                fi
                ;;
            \?)
                printf "Unknown option.\n"
                usage
                exit 2
                ;;
            esac
    done

    # Only kill previous instances if we've successfully parsed our arguments.
    if (( $RESTART )); then
        printf "Restarting conky...\n"
        killall conky
    fi
}

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

handle_arguments $@

if ! get_pos; then
    message="Failed to get X dimensions! Is the DISPLAY variable set (e.g. export DISPLAY=:0.0)"

    printf "%s\n" "$message"
    timeout 0.5 notify-send --icon=important "$message" 2> /dev/null >&2

    exit 1
fi

# Clear cache.
rm -rf "$tempRoot/cache"
# Re-make cache, plus reports directory
mkdir -p "$tempRoot/cache" "$tempRoot/reports"

# Check for tmpfs
if [ -n "$tempRoot" ] && mkdir -p "$tempRoot" && df "$tempRoot" 2> /dev/null | grep -q '^tmpfs' && [ "$DEBUG" -ne "1" ]; then
    # Transfer to /tmp so that we're reading off of tmpfs instead of our hard drive
    # Do not bother if we are on a distribution that doesn't put a tmpfs on /tmp
    printf "Starting conky from tmpfs.\n"
    configDir="$tempRoot/config"
    mkdir -p "$configDir" || printf "Failed to create directory: %s\n" "$configDir"
    (rsync -av "$dir/" "$configDir/" 2> /dev/null >&2 && printf "Successfully synced files to tmpfs...\n") || printf "Failed to sync files...\n"
    echo "$dir/../../" > "$tempRoot/tools-dir"
    cd "$configDir"
    location=tmpfs
else
    printf "Starting conky from regular location.\n"
    cd "$dir"
    location=tools
fi

# I have observed Conky not showing when run as a
#     startup application for a login after a fresh boot
#     (signing in immediately after the prompt showed up)
#     if I call it up too quickly. It would still show up as
#     a running process, suggesting that something with my display was wonky.

# Conky would always show up without troubles on a
#     laptop using the original 3s delay. The 3s delay
#     was originally in there from some vague memory of
#     this sort of problem in the pre-version-control days
#     when my documentation was even worse.

# My current theory is that the speed difference between the laptop's SSD
#     and machine B's HDD is enough to delay the script before the X display
#     can perform some necessary shenanigans (See also: https://xkcd.com/963/)

# The current experiment is to implement a longer startup delay for systems
#     not using an SSD. If this comment survives to be submitted, then it was a success!

# sda is assumed to be the only disk that matters for the moment (though we'll still double-check that we have one).
# Food for thought: The value of /sys/block/___/queue/rotational seems to be 1 for everything but SSDs (so far, though it'd still need to be confirmed that it is a relevent SSD...).
# Also check to see if the TERM variable has a value of "dumb", suggesting a startup application instead of a terminal.

# I have observed the HDD system starting conky properly with only a 3s delay sometimes if
#    the computer has been on for a while (drawing the line at 10 minutes), so leaving the uptime check in for the moment.
if [[ "$TERM" =~ ^dumb$ ]]; then
  if [ -f "/sys/block/sda/queue/rotational" ] && [ "$(cat /sys/block/sda/queue/rotational)" -gt 0 ]; then
    # Will be experimenting with exactly how little of a delay I can get away with over time, but this is good enough for an initial commit of the feature.
    if [ "$(grep -om1 "^[^\.]*" < /proc/uptime)" -lt 600 ]; then
      # Desktop login on fresh boot ( uptime < 10min )
      countdown=25
    else
      # Desktop login on older boot ( uptime >= 10min )
      countdown=5
    fi
  else
    # /dev/sda is not an HDD
    countdown=3
  fi
  # Justified delay
  message="$(printf "Conky should appear in %ds..." "$countdown")"
elif (( "$DEBUG" )); then
  message="Running conky in debug mode..."
else
  message="Starting conky..."
  countdown=0
fi

# Try running notify-send, ignoring all error messages
#   (like if notify-send is not present, for example)
timeout 0.5 notify-send --icon=esd "$(printf "%s\nLocation: %s" "$message" "$location")" 2> /dev/null >&2
# Print the message to stdout for good measure.
echo "$message"

if (( "$DEBUG" )); then
    # Debug mode
    # If we're in debug mode, run conky immediately in the foreground.

    # Print off the conky command being used for good measure.
    printf "\nconky -c conkyrc -a bottom_right -x $posX -y $posY\n\n"

    # Start conky
    conky -c conkyrc -a bottom_right -x $posX -y $posY
else
    # Standard mode
    # Sleep and start
    sleep $countdown && conky -c conkyrc -a bottom_right -x $posX -y $posY &
fi

cd "$OLDPWD"
