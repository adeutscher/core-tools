#!/bin/bash

check-commands(){
  # No harm in setting up a tmux config with no tmux command,
  #   but we will give a quick reminder.
  if ! type tmux 2> /dev/null >&2; then
    printf "Reminder: tmux is not yet installed on this machine!\n"
  fi
}

build-tmux(){

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

    printf "Applying \"%s\" style...\n" "$style"
    
cat << EOF > $HOME/.tmux.conf

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
    
}

check-commands
build-tmux
