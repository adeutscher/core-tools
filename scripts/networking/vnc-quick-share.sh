#!/bin/bash

# Common message functions.

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  PURPLE='\033[1;95m'
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

question(){
  unset __response
  while [ -z "${__response}" ]; do
    printf "$PURPLE"'Question'"$NC"'['"$GREEN"'%s'"$NC"']: %s: ' "$(basename "${0}")" "${1}"
    [ -n "${2}" ] && local __o="-s"
    read -r ${__o?} -p "" __response
    [ -n "${2}" ] && printf "\n"
    if [ -z "${__response}" ]; then
      error "Empty input."
      # Negate error increment, not a true error
      __error_count=$((${__error_count:-0}-1))
    fi
  done
}

success(){
  printf "${GREEN}"'Success'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __warning_count=$((${__warning_count:-0}+1))
}

# Script functions

function check_environment(){
  local __command=x11vnc
  if ! type "${__command}" 2> /dev/null >&2; then
    error "$(printf "${BLUE}%s${NC} command not found." "${__command}")"
  fi

  if [ -z "$DISPLAY" ]; then
    error "$(printf "${BOLD}%s${NC} environment variable not set (recommended: export DISPLAY=:0.0 ).")"
  fi

  (( ${__error_count:-0} )) && return 1
  return 0;
}

function handle_arguments(){

  # Read Arguments
  while getopts "cd:hlm:p:Pw" OPT "$@"; do
    case "${OPT}" in
      "c")
        __continue=1
        ;;
      "d")
        if ! grep -Piq "^\d+x\d+(\+\d+){2}$" <<< "${OPTARG}"; then
          error "Custom dimensions must be of the following format: WxH+X+Y"
          continue
        fi
        __custom_dimensions="${OPTARG}"
        ;;
      "h")
        hexit 0
        ;;
      "l")
        notice "Connected monitors:"
        xrandr --current | grep -w connected | sed 's/^/ /g'
        exit 0
        ;;
      "m")
        if grep -Pq "^\d+$" <<< "${OPTARG}"; then
          # Monitor number provided, go for the Nth connected monitor on the list.
          __monitor_number=${OPTARG}
          __monitor=$(xrandr --current | grep -w connected | sed -n "${__monitor_number}{p;q}" | cut -d' ' -f 1)
          if [ -z "$__monitor" ]; then
            error "$(printf "Monitor ${BOLD}#%d${NC} does not exist on this system." "${OPTARG}")"
          fi
        else
          # Assumed to be an attempted monitor name.

          # Silly: For display, get the properly-cased name of the monitor that we asked for.
          local __monitor
          __monitor=$(xrandr --current | grep -w connected | grep -i "^${OPTARG}\ " | cut -d' ' -f 1)

          if [ -z "${__monitor}" ]; then
            error "$(printf "Monitor \"${BOLD}%s${NC}\" does not exist on this system." "${OPTARG}")"
            break
          fi
          __monitor_number=$(xrandr --current | grep -w connected | grep -in "^$__monitor\ " | cut -d':' -f 1)
        fi
        __monitor_info="$(xrandr --current 2> /dev/null | grep -m1 "^$__monitor " | grep -oPm1 "\d+x\d(\+\d{1,}){2}")"
        ;;
      "p")
        __password="${OPTARG}"
        ;;
      "P")
        unset __password
        question "Input password" 1
        __password="${__response}"
        ;;
      "w")
        __write=1
        ;;
      *)
        error "$(printf "Unhandled argument: ${BOLD}-%s${NC}" "$OPT")"
        ;;
    esac
  done

  # Check to validate arguments
  if (( ${__write:-0} )) && [ -z "${__password}" ]; then
    error "Please provide a password for write mode."
  fi

  if [ "$(wc -c <<< "${__password}")" -gt 8 ]; then
    warning "Due to VNC limitations, only the first 8 characters of the password will be used."
  fi

  (( ${__error_count:-0} )) && hexit 1
  return 0;
}

function hexit(){
    notice "Usage: ./vnc-quick-share [-c] [-d dimensions] [-h] [-l] [-m monitor] [-p passwd|-P] [-w]"
    exit "${1:-0}"
}

function vnc(){
  # "${2:0:8}"
  if [ -n "${__monitor}" ]; then
    notice "$(printf "Sharing monitor ${BOLD}#%d${NC} (${BOLD}%s${NC})" "${__monitor_number}" "${__monitor}")"
  fi

  if [ -n "${__custom_dimensions}" ]; then
    # Custom dimensions override monitor choice.
    __monitor_info="${__custom_dimensions}"
  fi

  __options=("")

  if [ -n "${__monitor_info}" ]; then
    notice "$(printf "Shared dimensions: ${BOLD}%s${NC}" "${__monitor_info}")"
    __opt=("-clip" "${__monitor_info}")
    __options=("${__options[@]}" "${__opt[@]}")
  fi

  if ! (( ${__write:-0} )); then
    __opt=("-viewonly")
    __options=("${__options[@]}" "${__opt[@]}")
    notice "Sharing display in read-only mode."
  else
    notice "Sharing display in write mode."
  fi

  if [ -n "${__password}" ]; then
    notice "Password \"security\" enabled."
    __options=("${__options[@]}" "${__opt[@]}")
  fi

  if (( "${__continue:-0}" )); then
    notice "Continually spawning VNC server in case of unexpected server process crashing."
    __opt=("-loop100")
    __options=("${__options[@]}" "${__opt[@]}")
  fi

  # Sleep briefly to give the user time to read above notices.
  echo x11vnc -display :0 -auth guess -noxrecord -forever -shared ${__options[@]}
  sleep 3

  local ret
  if [ -n "${__password}" ]; then
    # shellcheck disable=SC2086
    x11vnc -display :0 -auth guess -noxrecord -forever -shared ${__options[@]} -passwd "${__password}"
    ret=$?
  else
    # shellcheck disable=SC2086
    x11vnc -display :0 -auth guess -noxrecord -forever -shared ${__options[@]}
    ret=$?
  fi
  return "${ret}"
}

check_environment
handle_arguments "$@" || hexit 1
vnc
