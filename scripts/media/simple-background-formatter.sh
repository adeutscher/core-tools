#!/bin/bash

# This script was made because I had a sizable backlog of small images
#  with uniform backgrounds that would make for fun backgrounds.

# The basic steps to do this are:
#  1. Make a blank canvas with a uniform colour and made to the size of your desired resolution.
#  2. Resize your subject image if desired.
#  3. Place your resized image on top of your canvas.

# I thought that the above steps were super-tedious, especially with positioning trial-and-error.
# Because of this, I made this script to condense everything that I needed down to one line.

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
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

success(){
  printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __warning_count=$((${__warning:-0}+1))
}

# Script Functions

get_corner_colours(){
  local __target="${1}"
  local __cx="$(get_image_width "${__target}")"
  local __cy="$(get_image_height "${__target}")"

  if [ -z "${__cx}" ] || [ -z "${__cy}" ]; then
    error "$(printf "Unable to get corner information from ${GREEN}%s${NC}" ${__target})"
    return
  fi

  # Get corner colours
  local __corner_a="$(get_pixel_hex "${__target}" 0 0)"
  local __corner_b="$(get_pixel_hex "${__target}" 0 "${__cy}")"
  local __corner_c="$(get_pixel_hex "${__target}" "${__cx}" 0)"
  local __corner_d="$(get_pixel_hex "${__target}" "${__cx}" "${__cy}")"

  # Average out RBG values
  local __red="$(((0x${__corner_a:0:2}+0x${__corner_b:0:2}+0x${__corner_c:0:2}+0x${__corner_d:0:2})/4))"
  local __blue="$(((0x${__corner_a:2:2}+0x${__corner_b:2:2}+0x${__corner_c:2:2}+0x${__corner_d:2:2})/4))"
  local __green="$(((0x${__corner_a:4:2}+0x${__corner_b:4:2}+0x${__corner_c:4:2}+0x${__corner_d:4:2})/4))"
  # Put back in hex code format.
  CANVAS="$(printf "%x%x%x" "${__red}" "${__blue}" "${__green}")"
}

get_image_height(){
  local _f="${1}"
  identify "${_f}" | grep -oPm1 "\d{1,}x\d{1,}(\+\d{1,}){2}" | cut -d'+' -f1 | cut -d'x' -f2
}

get_image_width(){
  local _f="${1}"
  identify "${_f}" | grep -oPm1 "\d{1,}x\d{1,}(\+\d{1,}){2}" | cut -d'+' -f1 | cut -d'x' -f1
}

get_pixel_hex(){
    local _f="${1}"
    local _x="${2}"
    local _y="${3}"
    convert "${_f}"[1x1+${_x}+${_y}] txt: | grep -ioPm1 "#[a-f]{6}" | cut -d'#' -f2
}

hexit(){
  printf "${GREEN}./%s${NC} -i in-file -o out-file -c canvas/colour [-C|-L|-R] [-D|-U] [-H] [-h canvas-height] [-w canvas-width] [-x pos-x] [-y pos-y]\n" "$(basename "$(readlink -f "$0")")"
  exit ${1:-1}
}

handle_arguments(){

  while getopts "c:CDi:h:HLo:Rs:Uw:x:y:" OPT $@; do
    case "${OPT}" in
      "c")
        CANVAS="${OPTARG}"
        ;;
      "C")
        GRAVITY_X="center"
        ;;
      "D")
        GRAVITY_Y="south"
        ;;
      "i")
        FILE_INPUT="${OPTARG}"
        ;;
      "h")
        RES_Y="${OPTARG}"
        ;;
      "H")
        hexit 0
        ;;
      "L")
        GRAVITY_X="west"
        ;;
      "o")
        FILE_OUTPUT="${OPTARG}"
        ;;
      "R")
        GRAVITY_X="east"
        ;;
      "s")
        SCALE="${OPTARG}"
        ;;
      "U")
        GRAVITY_Y="north"
        ;;
      "w")
        RES_X="${OPTARG}"
        ;;
      "x")
        POS_X="${OPTARG}"
        ;;
      "y")
        POS_Y="${OPTARG}"
        ;;
      *)
        error "$(printf "Unknown option: ${BOLD}%s${NC}" "${OPT}")"
        ;;
    esac
  done

  if [ -z "${FILE_INPUT}" ]; then
    error "No input file specified"
  fi

  if [ -z "${FILE_OUTPUT}" ]; then
    error "No output file specified"
  fi

  if [ -n "${CANVAS}" ]; then
    if grep -iPq "^[0-f]{6}$" <<< "${CANVAS}"; then
      # Canvas is a manual hex code.
      MAKE_CANVAS=1
    elif [ -f "${CANVAS}" ]; then
      # Canvas is a pre-existing file.
      CANVAS_FILE="${CANVAS}"

      if [ -n "${RES_X}" ]; then
        warning "A canvas width was given, but canvas is a file. Using file width."
      fi

      if [ -n "${RES_X}" ]; then
        warning "A canvas height was given, but canvas is a file. Using file height."
      fi

      RES_X="$(get_image_width "${CANVAS}")"
      RES_Y="$(get_image_height "${CANVAS}")"
    else
      error "$(printf "Invalid canvas: ${BOLD}%s${NC}" "${CANVAS}")"
    fi
  else
    # No canvas provided.

    if [ -z "${FILE_INPUT}" ]; then
      error "Could not guess canvas colour, input file not provided."
    elif [ ! -f "${FILE_INPUT}" ]; then
      error "Could not guess canvas colour, input file does not exist."
    else
      # No canvas information was given.
      # Using the average of the four corners of our input file.

      MAKE_CANVAS=1
      get_corner_colours "${FILE_INPUT}"
    fi
  fi

  if [[ "${GRAVITY_X}" == "center" ]] && [ -n "${GRAVITY_Y}" ]; then
    GRAVITY_X=""
  fi
  GRAVITY="${GRAVITY_Y}${GRAVITY_X}"

  if ! grep -Pq "^\d+$" <<< "${POS_X:-0}"; then
      error "X position must be an integer."
  fi

  if ! grep -Pq "^\d+$" <<< "${POS_Y:-0}"; then
      error "Y position must be an integer."
  fi

  if (( "${MAKE_CANVAS:-0}" )); then
    if [ -z "${RES_X}" ]; then
      error "No image width provided."
    elif ! grep -Pq "^\d+$" <<< "${RES_X}"; then
      error "Canvas width must be an integer."
    elif grep -Pq "^\d+$" <<< "${POS_X:-0}" && [ "${RES_X}" -lt "${POS_X:-0}" ]; then
      error "Image would be placed beyond canvas width."
    fi

    if [ -z "${RES_Y}" ]; then
      error "No image width provided."
    elif ! grep -Pq "^\d+$" <<< "${RES_Y}"; then
      error "Canvas height must be an integer."
    elif grep -Pq "^\d+$" <<< "${POS_Y:-0}" && [ "${RES_Y}" -lt "${POS_Y:-0}" ]; then
      error "Image would be placed beyond canvas height."
    fi
  fi

  if [ -n "${SCALE}" ] && ! grep -Pq "^\d+%$" <<< "${SCALE}";then
    error "Scale must be expressed as a percentage (e.g. '50%')."
  fi

  (( "${__error_count:-0}" )) && hexit 1
}

run_script(){

  if [ -n "${SCALE}" ]; then
    local FILE_INPUT_SIZED="/tmp/$$-resized.png"
    convert "${FILE_INPUT}" -resize ${SCALE} "${FILE_INPUT_SIZED}"
  fi

  if (( "${MAKE_CANVAS:-0}" )); then
    # Using a hex code.
    local CANVAS_FILE="/tmp/$$-canvas.png"
    convert -size "${RES_X}x${RES_Y}" "xc:#${CANVAS}" "${CANVAS_FILE}"
  fi

  convert "${CANVAS_FILE}" "${FILE_INPUT_SIZED:-${FILE_INPUT}}" -gravity "${GRAVITY:-southwest}" -geometry "+${POS_X:-0}+${POS_Y:-0}" -compose over -composite "${FILE_OUTPUT}"

  if [ -n "${FILE_INPUT_SIZED}" ]; then
    rm "${FILE_INPUT_SIZED}"
  fi

  if (( "${MAKE_CANVAS:-0}" )); then
    rm "${CANVAS_FILE}"
  fi
}

handle_arguments $@
run_script
