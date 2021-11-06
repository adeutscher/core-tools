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
  printf "${RED}"'Error'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "${BLUE}"'Notice'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

success(){
  printf "${GREEN}"'Success'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

warning(){
  printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
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

device_file="${2:-/dev/video0}"
if [ -z "$2" ]; then
  error "No device file given" # Did someone enter in empty quotes?
elif ! [ -c "${device_file}" ]; then
  error "$(printf "Webcam device file path not found: $GREEN%s$NC" "${device_file}")"
fi

if [ -a "$target_path" ] && ! [ -f "$target_path" ]; then
  error "$(printf "${GREEN}%s${NC} already exists, and is not a file. Aborting..." "$target_path")"
fi

if ! [ -d "$(dirname "$target_path")" ] && ! mkdir -p "$(dirname "$target_path")"; then
  error "$(printf "Failed to confirm that the ${GREEN}%s${NC} directory exists." "$(dirname "$target_path")")"
fi

(( "${__error_count}" )) && exit 1

notice "$(printf "Using ${GREEN}%s${NC} for video capture." "$device_file")"

# Arguable a space saver, if only by cutting down on the number of printf's that I have to write...
for command in ffmpeg fswebcam avconv; do
  if type "$command" 2> /dev/null >&2; then
    notice "$(printf "Using ${BLUE}%s${NC} to take a webcam photo. Saving to ${GREEN}%s${NC}." "$command" "$target_path")"
    case "$command" in
      "avconv")
      ;& # Fall through, identical approach to ffmpeg
      "ffmpeg")
        if "${command}" -f video4linux2 -s 640x480 -i "${device_file}" -ss 0:0:2 -frames 1 "${target_path}"; then
          __done=1
        else
          warning "$(printf "${BLUE}%s${NC} failed (exit code ${BOLD}%d${NC}. This is likely because it does not play nice with PNGs, so this may be why it failed. Consider trying with a different format." "$command" "$val")"
        fi
      ;;
      "fswebcam")
        shopt -s nocasematch 2> /dev/null
        if [[ "$target_path" =~ \.png$ ]]; then
          other_args="--png 0"
        fi
        shopt -u nocasematch 2> /dev/null
        fswebcam -r 640x480 -d "${device_file}" $other_args "$target_path"
        val=$?
        if (( "${val}" )); then
          error "$(printf "${BLUE}%s${NC} failed (exit code ${BOLD}%d${NC})." "$command" "$val")"
        else
          __done=1
        fi
      ;;
    esac
    [ -n "$__done" ] && break
  fi
done

# Did not get a success marker from any of the commands.
if [ -z "$__done" ]; then
  error "No webcam programs found on this system..."
  exit 127
fi
