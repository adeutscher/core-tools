#!/bin/bash

dir="$(dirname "${0}")"
# shellcheck disable=SC1090
. "$dir/functions/common.sh"

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
CONKYRC_PRIMARY=".${CONKYRC_PRIMARY_TEMPLATE}"
CONKYRC_SECONDARY_TEMPLATE=conkyrc.secondary
CONKYRC_SECONDARY=".${CONKYRC_SECONDARY_TEMPLATE}"

# Store default values in one place.
DEFAULT_PADDING_X=10
DEFAULT_PADDING_Y=45

if grep -q Fedora /etc/redhat-release 2> /dev/null; then
  # As of 2020-01-04, Fedora 31 has a problem where the cairo bindings don't work.
  #   Apparently this is a problem with conky just not being compiled with them.
  #   For the moment, force-disabling Lua on any Fedora 31 machine until I can confirm
  #     that this is no longer a problem.
  version_number="$(rpm -E %fedora)"
  if [ "${version_number:0}" -ge 31 ]; then
    CONKY_DISABLE_LUA=1
  fi
fi

disable_lua(){
    sed -r -i '/^lua_(load|draw)/d' "${1}"
    sed -i 's/^own_window_transparent yes/own_window_transparent no/g' "${1}"
    sed -i 's/^#own_window_colour/own_window_colour/g' "${1}"
}

# Set up per-system conkyrc settings.
do_dynamic_setup(){

    if [ -n "$configDir" ]; then
        cd "$configDir" || return 1
    fi
    cp -f "${CONKYRC_PRIMARY_TEMPLATE}" "${CONKYRC_PRIMARY}"
    (( ${CONKY_ENABLE_TASKS:-0} )) && cp -f "${CONKYRC_SECONDARY_TEMPLATE}" "${CONKYRC_SECONDARY}"

    # * Setting own_window_type to 'desktop' on Fedora 23 (conky 1.9) makes the conky
    #     display vanish when the desktop is clicked on. Fixed by
    #     setting to 'override'
    # * Setting own_window_type to 'override' on Fedora 25 (conky 1.10) once made the
    #     conky display crash and burn. Fixed by setting to 'desktop', with
    #     the above clicking issues not showing up.
    # * Setting own_window_type to 'override' on Fedora 27 (conky 1.10.7) makes the
    #     conky display not appear at all (joy).
    # To try to solve ALL of the above problems, making a dynamic conkyrc file with a configurable mode.

    # To make things even more annoying, my laptop running Fedora 25
    #  in fact has problems with the desktop mode.

    # TODO: Get a better idea about why these problems occur.

    if [[ "${GDMSESSION}" =~ ^(cinnamon|ubuntu)$ ]]; then
      # If using Cinnamon or Ubuntu Unity,
      #  set to dock unless we explicitly override it.
      local default_window_type=dock
    elif [[ "${XDG_CURRENT_DESKTOP}" =~ ^KDE$ ]]; then
      # KDE observed on Kubuntu 18.04
      local default_window_type=dock
    fi

    # Default
    local window_type="${CONKY_WINDOW_TYPE:-${default_window_type:-override}}"
    if [[ "$window_type" == "none" ]]; then
        # Eliminate the line altogether
        sed -i "/OWN_WINDOW_TYPE/d" "${CONKYRC_PRIMARY}"
        (( ${CONKY_ENABLE_TASKS:-0} )) && sed -i "/OWN_WINDOW_TYPE/d" "${CONKYRC_SECONDARY}"
    else
        sed -i "s/OWN_WINDOW_TYPE/$window_type/g" "${CONKYRC_PRIMARY}"
        (( ${CONKY_ENABLE_TASKS:-0} )) && sed -i "s/OWN_WINDOW_TYPE/$window_type/g" "${CONKYRC_SECONDARY}"
    fi
    # Original version-based check.
    #if conky --version | head -n1 | grep -qiP "^Conky 1\.1\d\."; then

    sed -i "s/__CONKY_INTERVAL__/${CONKY_INTERVAL:-2.0}/g" "${CONKYRC_PRIMARY}"
    (( ${CONKY_ENABLE_TASKS:-0} )) && sed -i "s/__CONKY_INTERVAL_SECONDARY__/${CONKY_INTERVAL_SECONDARY:-3.14}/g" "${CONKYRC_SECONDARY}"

    if (( "${CONKY_DISABLE_LUA}" )); then
        disable_lua "${CONKYRC_PRIMARY}"
        (( "${CONKY_ENABLE_TASKS:-0}" )) && disable_lua "${CONKYRC_SECONDARY}"
    fi

    return 0
}

handle_arguments(){

    # Default values
    DEBUG=0
    RESTART=0

    if [ "$#" == "0" ]; then
        return 0
    fi

    while getopts "dhs:r" OPT "$@"; do
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
                        printf "Screen blanked out.\n"
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
    if (( RESTART )); then
        printf "Restarting conky...\n"
        killall conky
    fi
}

get_coords(){
    local __target="${1}"
    local __add_x=${2:-0}
    local __add_y=${3:-0}
    # Adjust X calculation for secondary bottom-left display.
    local __is_bl=${4:-0}
    local __note="${5}"

    if [ -z "$__target" ]; then
        return 1
    fi

    if (( ${DEBUG:-0} )); then
        printf "Fetching Monitor Points for %s\n" "${__target}"
        [ -n "${__note}" ] && echo "${__note}"
    fi

    if ! get_monitor_info "$__target"; then
        printf "Failed to get monitor info for %s\n" "${__target}"
        return 1
    fi

    if (( __is_bl )); then
        # Bottom-left display.
        # Despite my ongoing troubles with right-aligned displays,
        #   the bottom-left display remains more consistent.
        TARGET_X="$((- ( __primary_monitor_bl_x - MONITOR_CORNER_BL_X ) + __add_x ))"
    else
        # Bottom-right

        # The "0" point on the X-axis as a user sees with Xinerama is calculated as:
        #   primary_monitor_offset + primary_monitor_right_edge_position
        # A bit strange and unintuitive, especially when it could easily toss the the "0" position far off the screen. Oh well...
        # Tested on Fedora 28 (2017-07-07).
        # Something similar seems to the "0" point for the Y-axis too for vertical stacking (just for the secondary display?)
        # The Y-axis issue is currently unsolved (see below by the TARGET_Y calculation).

        # Calculate the value required to place the display on the right edge of our overall conky display.
        X_POS_CORRECTION="$(((__primary_monitor_offset_x + __primary_monitor_br_x) - __total_x))"
        # Calculate number required to reach target screen.
        # This is a separate calculation from X_POS_CORRECTION to make debugging easier and to leave room for all these comments.
        # The two uses of $__total_x that cancel each other out are also intentionally left in.
        TARGET_X=$((X_POS_CORRECTION + (__total_x - MONITOR_CORNER_BR_X) + __add_x))
    fi

    # With testing for the most recent X co-ordinates fix, it appears that there
    #   is something wrong with Y positioning. However, there is also some fundamental problem
    #   conky displaying at all in certain configurations. For example, the display was seen
    #   to cut out in the middle of a screen. If conky will not display even when everything is
    #   arranged properly, then it makes troubleshooting very difficult.
    # Taking the win with X positioning for the moment and shelving Y-axis
    #   problem for another session.
    TARGET_Y=$(( MONITOR_CORNER_BR_Y - __primary_monitor_br_y + __add_y ))
}

# Get dimensions for a monitor.
get_monitor_info(){

    local __monitor="$1"
    local __is_primary=${2:-0}

    [ -z "$__monitor" ] && return 1
    local __monitor_info
    __monitor_info="$(xrandr --current 2> /dev/null | grep -m1 "^$__monitor " | grep -oPm1 "\d{1,}x\d{1,}(\+\d{1,}){2}")"

    [ -z "$__monitor_info" ] && return 1

    # Example content of monitor info:
    #   1600x900+0+124
    #   * 1600x900 display
    #   * Display's left edge is offset 0px from the left of the overall X display.
    #   * Display's top edge is offset 124px from the top of the overall X display.

    # Width of Display
    MONITOR_WIDTH="$(cut -d'x' -f1 <<< "$__monitor_info")"
    # Height of Display
    MONITOR_HEIGHT="$(cut -d'x' -f2 <<< "$__monitor_info" | cut -d'+' -f1)"
    # Left edge's offset from left of overall X display.
    MONITOR_OFFSET_X="$(cut -d'+' -f2 <<< "$__monitor_info")"
    # Top edge's offset from top of overall X display.
    MONITOR_OFFSET_Y="$(cut -d'+' -f3 <<< "$__monitor_info")"

    # If we are trying to get info on our primary monitor during initialization,
    #   then the __primary_monitor_* variables will not be set yet.
    if (( ${__is_primary:-0} )); then
        __primary_monitor_offset_x=$MONITOR_OFFSET_X
        __primary_monitor_offset_y=$MONITOR_OFFSET_Y
        __primary_monitor_width=$MONITOR_WIDTH
        __primary_monitor_height=$MONITOR_HEIGHT
    fi

    # So far as I understand, the main conky display's positioning in my setup is relative to the
    #     bottom-right of my primary monitor (as opposed to the first monitor, largest monitor, or otherwise).
    # From that, a positive X value places the bottom-right display more to the left and a positive Y value moves it up.

    # X coordinates work a bit differently, with (0,0) being in the top-right. +Y is down, and +X is right
    # For convenience, calculating the coordinates of the bottom-right corner with (0,0) being the bottom-left. +Y is up, +X is right
    MONITOR_CORNER_BR_X=$((MONITOR_WIDTH+MONITOR_OFFSET_X))
    MONITOR_CORNER_BR_Y=$((__total_y-MONITOR_OFFSET_Y-MONITOR_HEIGHT))

    # For future use with the secondary display (which is relative to bottom-left), also collecting the co-ords of the bottom-left corner.
    MONITOR_CORNER_BL_X=$MONITOR_OFFSET_X
    MONITOR_CORNER_BL_Y=$MONITOR_CORNER_BR_Y
}

# For killing multiple sessions in debug-mode.
kill_sessions(){
  printf "Clearing sessions\n"
  killall conky 2> /dev/null
}

# Confirm that the provided monitors exist.
monitor_check(){
    local __primary="$1"
    # Screen for secondary display
    local __secondary="$2"

    # If/Else shenanigans only really to confirm potential error phrasing.
    # Announce any errors, but defer exiting to the bottom of the function.
    if [ -z "$__primary" ]; then
        setup_failure "No screen name detected for primary display (CONKY_SCREEN variable)." 0
    elif (( ! ${CONKY_ENABLE_TASKS:-0} )); then
        # Only primary display is enabled.
        if ! monitor_exists "$__primary"; then
            setup_failure "$(printf "Unable to find primary display: %s" "$__primary")" 0
        fi
    else
        # Secondary display is enabled.
        if [ -z "$__secondary" ]; then
            setup_failure "No screen name detected for secondary display (CONKY_SECONDARY_SCREEN or CONKY_SCREEN variables)." 0
        elif [[ "$__primary" == "$__secondary" ]]; then
            # Both displays enabled, on the same screen
            if ! monitor_exists "$__primary"; then
                setup_failure "$(printf "Unable to find screen for primary and secondary displays: %s" "$__primary")" 0
            fi
        else
            # Both displays enabled, on different screens
            if ! monitor_exists "$__primary"; then
                setup_failure "$(printf "Unable to find primary display: %s" "$__primary")" 0
            fi
            if ! monitor_exists "$__secondary"; then
                setup_failure "$(printf "Unable to find secondary display: %s" "$__secondary")" 0
            fi
        fi
    fi

    if (( ${__setup_failure:-0} )); then
        # A setup error occurred.

        # List Displays
        setup_failure "$(printf "Available connected displays: %s\n" "$(xrandr --current | grep -w connected | cut -d' ' -f1 | tr '\n' ' ')")"
    fi
}

monitor_exists(){
    if [ -n "$1" ] && xrandr --current 2> /dev/null | grep -qw "^$1"; then
        return 0
    fi
    return 1
}

# Exit with a failure message to stdout and an attempt to a desktop environment.
setup_failure(){
    message="$1"

    printf "%s\n" "$message"
    timeout 0.5 notify-send --icon=important "$message" 2> /dev/null >&2

    # Exit out by default unless otherwise requested
    (( ${2:-1} )) && exit 1
    # Set a variable for deferred shutdown.
    __setup_failure=1
}

setup_global_values(){
    __total_dimensions="$(xrandr --current | head -n1 | grep -oP "current \d+ x \d+" | sed -e 's/current//' -e 's/\s//g')"
    __total_x="$(cut -d'x' -f1 <<< "${__total_dimensions}")"
    __total_y="$(cut -d'x' -f2 <<< "${__total_dimensions}")"

    [ -z "$__total_y" ] && return 1

    __primary_monitor="$(xrandr --current 2> /dev/null | grep -wm1 "primary" | grep -w connected | cut -d' ' -f1)"

    # Fall back to first connected monitor if none are designated by "primary".
    if [ -z "$__primary_monitor" ]; then
        __primary_monitor="$(xrandr --current 2> /dev/null | grep -w "connected" | cut -d' ' -f1)"
    fi

    __num_monitors="$(xrandr --current | grep -cw connected)"
    if [ "$__num_monitors" -le 1 ]; then
      # If we only have the one monitor, then ignore any monitor settings.
      if [[ "${CONKY_SCREEN:-${__primary_monitor}}" != "${__primary_monitor}" ]] || [[ "${CONKY_SECONDARY_SCREEN:-${__primary_monitor}}" != "${__primary_monitor}" ]]; then
        # If values were set to something other than what the only monitor is,
        #     then remind the user that settings are being ignored.
        for __method in notify-send echo; do
          $__method "Only one connected monitor detected, ignoring screen choices." 2> /dev/null
        done
        unset __method
      fi
      unset CONKY_SCREEN CONKY_SECONDARY_SCREEN
    fi

    monitor_check "${CONKY_SCREEN:-$__primary_monitor}" "${CONKY_SECONDARY_SCREEN-${CONKY_SCREEN:-$__primary_monitor}}"

    get_monitor_info "$__primary_monitor" 1 || return 1

    __primary_monitor_width=$MONITOR_WIDTH
    __primary_monitor_height=$MONITOR_HEIGHT
    __primary_monitor_offset_x=$MONITOR_OFFSET_X
    __primary_monitor_offset_y=$MONITOR_OFFSET_Y

    # For convenience, storing the coordinates of the bottom-right corner with (0,0) being the bottom-left.
    __primary_monitor_br_x=$MONITOR_CORNER_BR_X
    __primary_monitor_br_y=$MONITOR_CORNER_BL_Y

    # For future use with the secondary display (which is relative to bottom-left), also storing the co-ords of the bottom-left corner.
    __primary_monitor_bl_x=$MONITOR_CORNER_BL_X
    __primary_monitor_bl_y=$MONITOR_CORNER_BR_Y
}

handle_arguments "$@"

setup_global_values

__primary_display_screen="${CONKY_SCREEN:-$__primary_monitor}"
__secondary_display_screen="${CONKY_SECONDARY_SCREEN-${CONKY_SCREEN:-$__primary_monitor}}"

if ! get_coords "${__primary_display_screen}" "${CONKY_PADDING_X:-$DEFAULT_PADDING_X}" "${CONKY_PADDING_Y:-$DEFAULT_PADDING_Y}" 0 "  Primary Display"; then
    setup_failure "$(printf "Failed to get X dimensions for primary conky display (%s)! Is the DISPLAY variable set (e.g. export DISPLAY=:0.0)" "${__primary_display_screen}")"
fi

POS_PRIMARY_X=$TARGET_X
POS_PRIMARY_Y=$TARGET_Y

if (( ${CONKY_ENABLE_TASKS:-0} )); then
   if ! get_coords "${__secondary_display_screen}" "${CONKY_SECONDARY_PADDING_X:-${CONKY_PADDING_X:-$DEFAULT_PADDING_X}}" "${CONKY_SECONDARY_PADDING_Y:-${CONKY_PADDING_Y:-$DEFAULT_PADDING_Y}}" 1 "  Secondary Display"; then
       setup_failure "$(printf "Failed to get X dimensions for secondary conky display (%s)! Is the DISPLAY variable set (e.g. export DISPLAY=:0.0)" "${__secondary_display_screen}")"
   fi
   POS_SECONDARY_X=$TARGET_X
   POS_SECONDARY_Y=$TARGET_Y
fi

# tempRoot is defined in common.sh
# shellcheck disable=SC2154
if [ -n "${tempRoot}" ]; then
    # Clear cache.
    rm -rf "$tempRoot/cache"
    # Re-make cache, plus reports directory
    mkdir -p "$tempRoot/cache" "$tempRoot/reports"
fi

# Check for tmpfs
# tempRoot is defined in common.sh
# shellcheck disable=SC2154
if [ -n "$tempRoot" ] && mkdir -p "$tempRoot" && df "$tempRoot" 2> /dev/null | grep -q '^tmpfs' && [ "$DEBUG" -ne "1" ]; then
    # Transfer to /tmp so that we're reading off of tmpfs instead of our hard drive
    # Do not bother if we are on a distribution that doesn't put a tmpfs on /tmp
    printf "Starting conky from tmpfs.\n"

    configDir="$tempRoot/config"
    mkdir -p "$configDir" || printf "Failed to create directory: %s\n" "$configDir"
    (rsync -av "$dir/" "$configDir/" 2> /dev/null >&2 && printf "Successfully synced files to tmpfs...\n") || printf "Failed to sync files...\n"
    echo "$dir/../../" > "$tempRoot/tools-dir"
    if ! cd "${configDir}"; then
      print "Failed to navigate to directory: %s\n" "${configDir}"
      exit 1
    fi
    location=tmpfs
else
    printf "Starting conky from regular location.\n"
    if ! cd "$dir"; then
      print "Failed to navigate to directory: %s\n" "${dir}"
      exit 1
    fi
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
elif (( DEBUG )); then
  message="Running conky in debug mode..."
else
  message="Starting conky..."
  countdown=0
fi

# Try running notify-send, ignoring all error messages
#   (like if notify-send is not present, for example)
timeout 0.5 notify-send --icon=esd "Starting Conky" "$(printf "%s\n  Display: %s\n  Location: %s" "$message" "${CONKY_SCREEN:-$__primary_monitor}" "$location")" 2> /dev/null >&2
# Print the message to stdout for good measure.
echo "$message"

if (( "${DEBUG:-0}" )); then
    # Debug mode
    # If we're in debug mode, run conky immediately in the foreground.

    # Print off the conky command being used for good measure.
    # shellcheck disable=SC2059
    printf "\nconky -c '${CONKYRC_PRIMARY}' -a bottom_right -x $POS_PRIMARY_X -y $POS_PRIMARY_Y\n\n"

    # Start conky session(s)
    if (( ${CONKY_ENABLE_TASKS:-0} )); then
      # shellcheck disable=SC2059
      printf "\nconky -c '${CONKYRC_SECONDARY}' -a bottom_left -x $POS_SECONDARY_X -y $POS_SECONDARY_Y\n\n"
      conky -c "${CONKYRC_SECONDARY}" -a bottom_left -x $POS_SECONDARY_X -y $POS_SECONDARY_Y &
    fi
    conky -c "${CONKYRC_PRIMARY}" -a bottom_right -x $POS_PRIMARY_X -y $POS_PRIMARY_Y
else
    # Standard mode
    # Sleep and start
    sleep $countdown && conky -c "${CONKYRC_PRIMARY}" -a bottom_right -x $POS_PRIMARY_X -y $POS_PRIMARY_Y &
    if (( ${CONKY_ENABLE_TASKS:-0} )); then
        sleep $countdown && conky -c "${CONKYRC_SECONDARY}" -a bottom_left -x $POS_SECONDARY_X -y $POS_SECONDARY_Y &
    fi
fi

cd "${OLDPWD}" || exit 1
