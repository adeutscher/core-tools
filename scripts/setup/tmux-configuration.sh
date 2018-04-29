#!/bin/bash

# Load common functions.
. "$(dirname "${0}")/functions.sh"

build_tmux(){

    case "${DISPLAY_HOSTNAME:-$HOSTNAME}" in
    "datacomm")
        # Follow the example of the purple hostname promt that machines named 'datacomm' get.
        # Chosen for its similarity to the purple given to the hostname for 'datacomm' in the prompt.
        # I am not keen on spending the time to find exactly the right hue, so purple-ish will have to do.
        bg=colour134
        fg=colour195
        style=Datacomm
    ;;
    "nuc."*)
        # Imitate nuc colouring
        bg=colour15
        fg=colour124
        style=nuc
    ;;
    "laptop."*)
        # Imitate laptop colouring
        bg=colour34
        fg=colour220
        status_fg="black"
        style=laptop
    ;;
    "kali")
        # Red/Black colouring
        bg=colour160
        fg=colour233
        status_fg="black"
        style="Red Team"
    ;;
    "server-b."*)
    ;&
    "server."*)
        # Imitate gray brick colouring
        bg=colour244
        fg=black
        active_fg=white
        style=server
    ;;
    "machine-a"*)
        bg=yellow
        fg=red
        style="Desktop Machine"
    ;;
    "scudder"*)
        bg=green
        fg=colour208 # orange
        active_fg="black"
        status_fg="$active_fg"
        style="Spare Machine"
    ;;
    *)
        # If we cannot track down a specific hostname, try to style based on operating system
        . /etc/os-release 2> /dev/null
        local os="${ID} ${VERSION_ID}"
        case "${os:-unknown}" in
        "raspbian"*)
            # Bright fruit-y colours
            bg=colour161
            fg=colour11
            style="Fruity"
        ;;
        *)
            bg=blue
            fg=white
            style="Default Blue"
        ;;
        esac
    ;;
    esac

    notice "$(printf "Applying ${BOLD}\"%s\"${NC} style...\n" "$style")"

  # Note: Stretching command output across multiple lines makes geany colour formatting act strangely, but BASH has no problems with running it.
  CONTENT="$(cat << EOF

## Theming

set-window-option -g status-bg $bg
set-window-option -g status-fg $fg

set-option -g pane-border-fg ${border_bg:-$bg}
set-option -g pane-active-border-fg ${border_fg:-$fg}

set-window-option -g window-status-fg ${status_fg:-$fg}
set-window-option -g window-status-bg ${status_bg:-$bg}
set-window-option -g window-status-attr dim

set-window-option -g window-status-current-fg ${active_fg:-$bg}
set-window-option -g window-status-current-bg ${active_bg:-$fg}
set-window-option -g window-status-current-attr bright

## Hotkeys

# Toggle the window's panes between syncing and non-syncing.
bind M setw synchronize-panes

# Reload
bind R source-file ~/.tmux.conf

EOF
)"

  "${DOTFILE_SCRIPT}" "${HOME}/.tmux.conf" core-tools-tmux - <<< "${CONTENT}"
}

check_commands(){
  # No harm in setting up a tmux config with no tmux command,
  #   but we will give a quick reminder.
  if ! type tmux 2> /dev/null >&2; then
    warning "$(printf "Reminder: ${BLUE}%s${NC} is not yet installed on this machine. Configuration will still be written.\n" "tmux")"
  fi

  # Script is expected to be in scripts/setup/.
  # Need to get at an updater script in scripts/system/
  DOTFILE_SCRIPT="$(readlink -f "$(dirname "$(readlink -f "${0}")")/../system/update-dotfile.sh")"

  if ! ( [ -f "${DOTFILE_SCRIPT}" ] && [ -x "${DOTFILE_SCRIPT}" ] ); then
    error "$(printf "Dotfile update script not found or not runnable: ${GREEN}%s${NC}" "$(sed "s|^${HOME}|~|" <<< "${DOTFILE_SCRIPT}")")"
  fi

  (( ${__error_count:-0} )) && return 1
  return 0
}

check_commands || exit 1
build_tmux
