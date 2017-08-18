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

# Script content

if [ -n "$1" ]; then
    target_path="$1"
else
    if [ -d "$HOME/Pictures/" ]; then
        # Default path (depending on desktop environment using a lazy check)
        target_path="$HOME/Pictures/webcam-photos/$(date +"%Y-%m-%d-%H-%M-%S").jpg"
    else
        # Strange headless system with a webcam attached to it. Oh well, lets roll with it...
        target_path="$HOME/webcam/webcam-photos/$(date +"%Y-%m-%d-%H-%M-%S").jpg"
    fi
    notice "$(printf "No path provided as first argument. Using default: ${GREEN}%s${NC}" "$target_path")"
fi

if [ -n "$2" ]; then
    if [ -f "$2" ]; then
        device_file="$2"
    else
        error "$(printf "Webcam device file path not found: $GREEN%s$NC" "$2")"
    fi
else
    device_path="$2"
fi
notice "$(printf "Using ${GREEN}%s${NC} for video capture." "$device_path")"

if [ -a "$target_path" ] && ! [ -f "$target_path" ]; then
    error "$(printf "${GREEN}%s${NC} already exists, and is not a file. Aborting..." "$target_path")"
fi

if ! [ -d "$(dirname "$target_path")" ] && ! mkdir -p "$(dirname "$target_path")"; then
    error "$(printf "Failed to confirm that the ${GREEN}%s${NC} directory exists." "$(dirname "$target_path")")"
    return 1
fi

# Arguable a space saver, if only by cutting down on the number of printf's that I have to write...
for command in avconv fswebcam; do
    if type "$command" 2> /dev/null >&2; then
        notice "$(printf "Using ${BLUE}%s${NC} to take a webcam photo. Saving to ${GREEN}%s${NC}." "$command" "$target_path")"
        case "$command" in
        "avconv")
            if ! avconv -f video4linux2 -s 640x480 -i /dev/video0 -ss 0:0:2 -frames 1 "$target_path"; then
                val=$?
                warning "$(printf "${BLUE}%s${NC} failed (exit code ${BOLD}%d${NC}. This is likely because it does not play nice with PNGs, so this may be why it failed. Consider trying with a different format." "$command" "$val")"
            else
                __done=1
            fi
            ;;
        "fswebcam")
            shopt -s nocasematch 2> /dev/null
            if [[ "$target_path" =~ \.png$ ]]; then
                other_args="--png 0"
            fi
            shopt -u nocasematch 2> /dev/null
            if ! fswebcam -r 640x480 -d /dev/video0 $other_args "$target_path"; then
                val=$?
                error "$(printf "${BLUE}%s${NC} failed (exit code ${BOLD}%d${NC})." "$command" "$val")"
            else 
                __done=1
            fi
            ;;
        esac
        if [ -n "$__done" ]; then
            break
        fi
    fi
done
unset command

# Did not get a success marker from any of the commands.
if [ -z "$__done" ]; then
    error "No webcam programs found on this system..."
fi
