#!/bin/bash

# Common message functions.

set_colours(){
  # Define colours
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  PURPLE='\033[1;95m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
  grep -Pq c <<< "${label_switches}" || label_switches="${label_switches}c"
}
[ -t 1 ] && set_colours

# Announce an error
error(){
  printf "${RED}"'Error'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

# Announce a session
session(){
  printf "${BLUE}"'Session'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

#
# Script Functions
##

do_mux(){
  if [ -z "$1" ]; then
    local sessions
    sessions="$(tmux list-sessions 2> /dev/null)"
    if [ -n "${sessions}" ]; then
      error "$(printf "No session name provided. Session(s) available: ${BOLD}%d${NC}" "$(wc -l <<< "${sessions}")")"
      while read -r s; do
        s_name="$(cut -d':' -f1 <<< "${s}")"
        s_other="$(cut -d':' -f2- <<< "${s}")"
        session "$(printf "${BOLD}%s${NC}:%s" "${s_name}" "${s_other}")"
      done <<< "${sessions}"
    else
      error "No session name provided. No sessions are currently available."
    fi
    return 1
  fi

  if [ -n "${TMUX}" ]; then
    # shellcheck disable=SC2059
    error "$(printf "sessions should be nested with care, unset ${PURPLE}\$TMUX${NC} to force" )"
    return 2
  fi

  if grep -w "mux-force" <<< "$(basename "${0}")"; then
    # Extra Tmux Attach Switch
    # If invoked via 'mux-force', then we want to detach other clients as we connect.
    # I find it useful to not necessarily do this most of the time, hence the extra legwork.
    # The function-name shenanigans are to avoid code duplication.
    local __etas="${__etas}d"
  fi

  if ! tmux -V | grep -qP "\s1\."; then
    # Extra Tmux Attach Switch
    # Version 1.8 does not seem to have the -E switch for attachments.
    # Until falsified, assuming that this is the case in all 1.x releases
    #   and that the switch is present for all 2.x releases and beyond.

    # The purpose of the -E switch is to prevent certain environment variables
    #  from updating our tmux server when we attach (the main noticable offender
    #  for me was the DISPLAY variable.
    local __etas="${__etas}E"
  fi

  # Check if the session already exists.
  if tmux list-sessions 2> /dev/null | grep -qP "^${1}:"; then
      # Session exists, attach.
      tmux attach "-${__etas}t" "$1"
  else
      # Session does not exist.

      # Prepare to export tool-specific variables.
      # The reason for these shenanigans is that tmux only seems to want to do
      #  a full pull of environment variables when a new tmux SERVER is created,
      #  as opposed to a SESSION within an existing server (the behavior
      #  of the DISPLAY variable without the -E switch doesn't seem to want to
      #  follow this, but some variables that I want to transfer do). Killing the server
      #  or establishing a new server per session to make a particular session
      #  inherit from outside tmux is not something that I want to do, so
      #  instead I am making an outside dump whenever we make a new session.

      # When a tmux pane starts up, tmux will provide the TMUX_PANE variable,
      #  which can be used to get the session name and load in the variables.
      mkdir -p "/tmp/${USER}/tmux"
      chmod 700 "/tmp/${USER}"

      # For the moment, the only variables that we care about exporting to a new session are:
      #   * Display username/hostname
      #   * Prompt flags
      #   * Conky variables
      #   * KDE variables
      #   * XDG variables
      # A reminder in case you are thinking about expanding on this:
      #   When I was developing this feature, I originally dumped all of my exported variables
      #   without a grep filter. This caused me grief because some bits were not parsing properly.
      # Quotes should help with values including spaces, but you may still run into problems with more exotic data.
      env | grep -P "^(AUDIO|CONKY|DISPLAY|KDE|PROMPT|XDG)_" | sed -r -e 's/(^[^=]+=)/\1"/' -e 's/$/"/g' -e 's/^/export /g' > "/tmp/${USER}/tmux/env.${1}"
      tmux new -s "$1"
  fi
}

if ! type tmux 2> /dev/null >&2; then
  error "$(printf "${BLUE}%s${NC} is not installed!" "tmux")"
  exit 1
fi

do_mux "${1}"
