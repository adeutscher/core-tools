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
                Note: Done just by running "killall conky" for the moment.
                Would not play nice with multiple simultaneous configurations.
EOF
}

# Variables for configuration files
CONKYRC_PRIMARY_TEMPLATE=conkyrc.primary
CONKYRC_PRIMARY=".$CONKYRC_PRIMARY_TEMPLATE"
CONKYRC_SECONDARY_TEMPLATE=conkyrc.secondary
CONKYRC_SECONDARY=".$CONKYRC_SECONDARY_TEMPLATE"

# Set up per-system conkyrc settings.
do_dynamic_setup(){
    # * Setting own_window_type to 'desktop' on Fedora 23 (conky 1.9) makes the conky
    #     display vanish when the desktop is clicked on. Fixed by
    #     setting to 'override'
    # * Setting own_window_type to 'override' on Fedora 25 (conky 1.10) makes the
    #     conky display crash and burn. Fixed by setting to 'desktop', with
    #     the above clicking issues not showing up.
    # To solve BOTH of the above problems, making a dynamic conkyrc file.
    # File contents are based on conky version, at least for the short-term.

    # To make things even more annoying, my laptop running Fedora 25
    #  in fact has problems with the desktop mode.
    # For the moment, only the affected datacomm machines shall go to "desktop" mode.

    # TODO: Get a better idea about why these problems occur.
    local window_type="override"

    # Original version-based check.
    #if conky --version | head -n1 | grep -qiP "^Conky 1\.1\d\."; then

    # Kludge fix for Datacomm machines.
    if [[ $HOSTNAME =~ ^datacomm$ ]]; then
        # Assuming override crashes, and desktop has no problem
        local window_type="desktop"
    fi

    cd "$configDir" || return 1

    cp -f "$CONKYRC_PRIMARY_TEMPLATE" "$CONKYRC_PRIMARY"

    sed -i "s/OWN_WINDOW_TYPE/$window_type/g" "$CONKYRC_PRIMARY"

    if (( ${CONKY_ENABLE_TASKS:-0} )); then
        cp -f "$CONKYRC_SECONDARY_TEMPLATE" "$CONKYRC_SECONDARY"
        sed -i "s/OWN_WINDOW_TYPE/$window_type/g" "$CONKYRC_SECONDARY"
    fi
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

get_primary_pos(){

    gapX=${CONKY_PADDING_X:-10}
    gapY=${CONKY_PADDING_Y:-35}

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
            # If no valid output from CONKY_SCREEN attempt,
            #     or if xrandr does not clearly say which is
            #     the 'primary' monitor, then simply go with
            #     the first connected one.
            local primary_monitor_info="$(xrandr --current 2> /dev/null | grep -m1 " connected" | grep -oPm1 "\d{1,}x\d{1,}(\+\d{1,}){2}")"
        fi

        # Example content of primary_monitor_info:
        #   1600x900+0+124
        #   * 1600x900 display
        #   * Display's left edge is offset 0px from the left of the overall X display.
        #   * Display's top edge is offset 124px from the top of the overall X display.

        # Width of Display
        local mainX="$(cut -d'x' -f1 <<< "$primary_monitor_info")"
        # Height of Display
        local mainY="$(cut -d'x' -f2 <<< "$primary_monitor_info" | cut -d'+' -f1)"

        # Left edge's offset from left of overall X display.
        local offX="$(cut -d'+' -f2 <<< "$primary_monitor_info")"
        # Top edge's offset from top of overall X display.
        local offY="$(cut -d'+' -f3 <<< "$primary_monitor_info")"

        if [ -n "$totalX" ] && [ -n "$totalY" ] && [ -n "$mainX" ] && [ -n "$mainY" ] && [ -n "$offX" ] && [ -n "$offY" ]; then
            # Uncomment below for debugging
            #echo "$totalX- ($mainX+$offX) + $gapX"
            #echo "$totalY- ($mainY+$offY) + $gapY"
            posX="$(($totalX- ($mainX+$offX) + $gapX))"
            posY="$(($totalY- ($mainY+$offY) + $gapY))"
        else
            return 1
        fi
    fi
}

get_secondary_pos(){

    secondaryGapX=${CONKY_SECONDARY_PADDING_X:-10}
    secondaryGapY=${CONKY_SECONDARY_PADDING_Y:-35}

    if [ "$(xrandr --current 2> /dev/null | grep " connected" | wc -l)" -eq 1 ]; then
        secondaryPosX=$secondaryGapX
        secondaryPosY=$secondaryGapY
    else
        local totalX="$(xdpyinfo 2> /dev/null | grep dimensions | awk '{ print $2 }' | cut -d'x' -f1)"
        local totalY="$(xdpyinfo 2> /dev/null | grep dimensions | awk '{ print $2 }' | cut -d'x' -f2)"

        # If we have specified a CONKY_SECONDARY_SCREEN variable in our BASH config and such a screen is present, use that one to calculate our offsets.
        if [ -n "$CONKY_SECONDARY_SCREEN" ]; then
            local secondary_monitor_info="$(xrandr --current 2> /dev/null | grep -m1 "^$CONKY_SECONDARY_SCREEN " | grep -oPm1 "\d{1,}x\d{1,}(\+\d{1,}){2}")"
        else
            local secondary_monitor_info="$(xrandr --current 2> /dev/null | grep -m1 "primary" | grep -oPm1 "\d{1,}x\d{1,}(\+\d{1,}){2}")"
        fi

        if [ -z "$secondary_monitor_info" ]; then
            # If no valid output from CONKY_SECONDARY_SCREEN attempt,
            #     or if xrandr does not clearly say which is
            #     the 'primary' monitor, then simply go with
            #     the first connected one.
            local secondary_monitor_info="$(xrandr --current 2> /dev/null | grep -m1 " connected" | grep -oPm1 "\d{1,}x\d{1,}(\+\d{1,}){2}")"
        fi

        # Example content of secondary_monitor_info:
        #   1600x900+0+124
        #   * 1600x900 display
        #   * Display's left edge is offset 0px from the left of the overall X display.
        #   * Display's top edge is offset 124px from the top of the overall X display.

        # Width of Display
        local mainX="$(cut -d'x' -f1 <<< "$secondary_monitor_info")"
        # Height of Display
        local mainY="$(cut -d'x' -f2 <<< "$secondary_monitor_info" | cut -d'+' -f1)"
        # Left edge's offset from left of overall X display.
        local offX="$(cut -d'+' -f2 <<< "$secondary_monitor_info")"
        # Top edge's offset from top of overall X display.
        local offY="$(cut -d'+' -f3 <<< "$secondary_monitor_info")"

        if [ -n "$totalX" ] && [ -n "$totalY" ] && [ -n "$mainX" ] && [ -n "$mainY" ] && [ -n "$offX" ] && [ -n "$offY" ]; then
            # Uncomment below for debugging
            #echo "$(($offX + $gapX))"
            #echo "$totalY- ($mainY+$offY) + $gapY"
            secondaryPosX="$(($offX + $secondaryGapX))"
            secondaryPosY="$(($totalY- ($mainY+$offY) + $secondaryGapY))"
        else
            return 1
        fi
    fi
}

# For killing multiple sessions in debug-mode.
kill_sessions(){
  printf "Clearing sessions\n"
  #killall conky 2> /dev/null
}

# Exit with a failure message to stdout and an attempt to a desktop environment.
setup_failure(){
    message="$1"

    printf "%s\n" "$message"
    timeout 0.5 notify-send --icon=important "$message" 2> /dev/null >&2

    exit 1
}

handle_arguments $@

if ! get_primary_pos; then
    setup_failure "Failed to get X dimensions for primary display! Is the DISPLAY variable set (e.g. export DISPLAY=:0.0)"
fi

if (( ${CONKY_ENABLE_TASKS:-0} )) && ! get_secondary_pos; then
    setup_failure "Failed to get X dimensions for secondary display! Is the DISPLAY variable set (e.g. export DISPLAY=:0.0)"
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

# Need to run dynamic setup after determining our run directory
if ! do_dynamic_setup; then
    setup_failure "Unexpected error with dynamicly setting own_window_type"
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
    printf "\nconky -c '$CONKYRC_PRIMARY' -a bottom_right -x $posX -y $posY\n\n"

    # Start conky session(s)
    if (( ${CONKY_ENABLE_TASKS:-0} )); then
      printf "\nconky -c '$CONKYRC_SECONDARY' -a bottom_left -x $secondaryPosX -y $secondaryPosY\n\n"
      conky -c "$CONKYRC_SECONDARY" -a bottom_left -x $secondaryPosX -y $secondaryPosY &
    fi
    conky -c "$CONKYRC_PRIMARY" -a bottom_right -x $posX -y $posY
else
    # Standard mode
    # Sleep and start
    sleep $countdown && conky -c "$CONKYRC_PRIMARY" -a bottom_right -x $posX -y $posY &
    if (( ${CONKY_ENABLE_TASKS:-0} )); then
        sleep $countdown && conky -c "$CONKYRC_SECONDARY" -a bottom_left -x $secondaryPosX -y $secondaryPosY &
    fi
fi

cd "$OLDPWD"
