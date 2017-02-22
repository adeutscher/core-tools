#!/bin/bash

# Make sure that this script has the paths it needs for cron.
PATH=/usr/bin:/bin

# Priority order for background directories.
# 1. Value of last-read directory given by an argument
#     e.g. Passing in two directories as arguments will overwrite the first one
# 2. Value of $backgroundDirectory variable (set in .bashrc logic)
# 3. ~/Pictures/backgrounds.
defaultImageDir="$HOME/Pictures/backgrounds"
imageDir=${backgroundDirectory:-$defaultImageDir}

# Indexing our backgrounds in /tmp to shave a few milliseconds off of our execution time for frequent background shifting (and avoid unnecessary disk IO).    
backgroundIndexFile=/tmp/$USER/background-index.txt

# Set default mode
mode=new

check-int(){
  if [ -z "$1" ] || ! grep -qP "^\d{1,}$" <<< "$1"; then
    return 1
  fi
}

# Handle arguments
while getopts "d:fhst:v" opt; do
    # Process CLI flags.
    case "$opt" in
    d)
        # Check if the user is trying to input a directory, overwrite the "imageDir" variable if so.
        if [ -d "$OPTARG" ]; then
            # Get the absolute path to our target directory WITHOUT using the 'realpath' command.
            # 'realpath' is not always available by default on some systems.
            imageDir="$(readlink -f "$OPTARG")"
        else
            printf "Requested image directory does not exist: %s\n" "$OPTARG"
            haveError=1
        fi
        ;;
    f)
        if [ -f "$backgroundIndexFile" ]; then
            rm "$backgroundIndexFile"
        fi
        ;;
    h)
        printf 'Usage: %s [-d image-directory-path] [-f] [-s] [-v]\n' "$0"

        # Describe switches.
        printf 'Switches:\n  -d: Set background directory (will need to flush old index with -f switch).'
        printf '  -f: Delete the background index, forcing the script to re-scan your directory\n'
        printf '  -h: Print this menu and exit\n'
        printf '  -s: Stream mode. Cycle through backgrounds every 4 seconds (use ctrl-c to abort at the desired background)\n'
        printf '  -t: Set a time delay for stream mode in seconds (must be an integer)\n'
        printf '  -v: Verbose mode\n'

        # Describe directory priority.
        printf 'Note: Priority order for potential background directories:\n'
        printf '  1. Value of last-read directory in CLI arguments (if two arguments were given, the second would be used)\n'
        printf '  2. Value of $backgroundDirectory variable (set in .bashrc logic)\n'
        printf '  3. %s\n' "$defaultImageDir"
        exit 0
        ;;
    s)
        mode=stream
        ;;
    t)
        if check-int "$OPTARG" && [ "$OPTARG" -gt 0 ]; then
            delay=$OPTARG
        else
            printf "Invalid time interval for stream mode: %s\n" "$OPTARG"
            haveError=1
        fi
        ;;
    v)
        verbose=1
        ;;
    esac
done

if (( ${haveError:-0} )); then
    exit 1
fi

# If the image directory does not exist, do not bother continuing the script.
if [ -z "$imageDir" ] && (( "$verbose" )); then
    printf "\$imageDir variable is blank. No image directory specified...\n"
    exit 1
fi

if [ ! -d "$imageDir" ] && (( "$verbose" )); then
    printf "Image directory not found at %s\n" "$imageDir"
    exit 1 
fi

# Define functions
__set_env(){

    # Replace old environment variables.

    # If a PID was not provided, get one from the first session that pgrep finds.
    pid=${1:-$(pgrep -U "$(whoami)" '(gnome|mate)-session' | head -n1)}

    # mate-session and gnome-session are reliable processes to search for to get our D-Bus session from.
    if [ -n "$pid" ]; then
        environmentType=$(ps -p $pid -o cmd= | sed 's/-session$//g')
        export $(</proc/$pid/environ tr \\0 \\n | grep -E '^DBUS_SESSION_BUS_ADDRESS=')
    fi
}

# Choose and set a random background.
__select_random_background(){

    # Fetch one set of variables to see if there's any point to going on.
    __set_env

    # Confirm one more time that we have the variables that we need.
    # If we do not have the variables by this point, skip this block and exit out
    if pgrep -U "$(whoami)" "(mate|gnome)-session" 2> /dev/null >&2; then

        # Preserve old value of DBUS_SESSION_BUS_ADDRESS to re-export after the script is complete.
        if [ -n "$DBUS_SESSION_BUS_ADDRESS" ]; then
            __old_dbus="$DBUS_SESSION_BUS_ADDRESS"
        fi

        # Delete an index that is older than 3 hours (.125 * 24)
        # Ignore any errors
        #   Any stderr output should be due to the index file not currently existing (fresh boot?)
        find "$backgroundIndexFile" -mtime +.125 2> /dev/null | xargs -I{} rm {}

        # Index our backgrounds if we have not already done so.
        if [ ! -f "$backgroundIndexFile" ]; then
            # Set our umask so that other users cannot view our backgrounds.
            umask 177
            # Create our index.
            # The call to sed is a crude way to exclude the "need-formatting/" directory in my personal backgrounds folder.
            # As the name implies, the folder has images that I need to do some formatting on before they're background-ready.
            if ! mkdir -p "$(dirname "$backgroundIndexFile")" || \
                ! find -L "$imageDir" -iname '*png' -o -iname '*jpg' | \
                    sed '/\/need-formatting\//d' > "$backgroundIndexFile"; then
                printf "Unable to make index at %s\n" "$backgroundIndexFile"
                local __return_value=1
            fi # End index file creation check
        fi # End index file check

        newBg=$(cat "$backgroundIndexFile" | shuf -n 1)
        if [ -n "$newBg" ]; then

            if (( "$verbose" )); then
                printf "Setting new background: %s\n" "$newBg"
            fi

            for __pid in $(pgrep -U "$(whoami)" "(mate|gnome)-session"); do

                __set_env $__pid

                # Different desktop environments use different commands to write settings.
                case "$environmentType" in
                "gnome")
                     gconftool-2 -t str -s /desktop/gnome/background/picture_filename "$newBg"
                ;;
                "mate")
                     dconf write /org/mate/desktop/background/picture-filename "'$newBg'"
                ;;
                esac
            done
        else
            # background was blank
            local __return_value=2
        fi

        if [ -n "$__old_dbus" ]; then
            export DBUS_SESSION_BUS_ADDRESS="$__old_dbus"
        fi
    fi

    # Using a variable to store our return code so that
    #     we don't need to restore __old_dbus in a million places
    return ${__return_value:-0}
}

case "$mode" in
    "stream")
        printf "Cycling through backgrounds. You will have about %d seconds to ctrl-c out and keep the one that you want.\n" "${delay:-4}"
        trap 'exit 0' INT
        # Shuffle once before we start the sleep-shuffle loop (since it starts with the sleep)
        __select_random_background
        while sleep ${delay:-4}; do __select_random_background || exit 1; done
       ;;
    *)
        # Default
        __select_random_background
        ;;
esac

