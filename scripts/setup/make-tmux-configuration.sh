#!/bin/bash

build-tmux(){

    case "$HOSTNAME" in
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
    "server."*)
        # Imitate gray brick colouring
        bg=colour244
        fg=black
        active_fg=white
        style=server
    ;;
    "keystone"*)
        bg=yellow
        fg=red
        style="Desktop Machine"
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

EOF
    
}

build-tmux
