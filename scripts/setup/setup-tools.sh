#!/bin/bash

# Get the path to the tools directory.
# Script is currently stored in 'scripts/setup/', relative to the root of the tools directory.
# No need to resolve the path with readlink.
toolsDir="$(readlink -f "$(dirname $0)/../..")"

setup(){

    cd "$toolsDir"

    if pwd | grep -Pq "$HOME($|/)"; then
        # Setting up the tools locally for a user.
        local marker="$(whoami)-tools-marker"
        global=0
    else
        # Setting up tools in a common directory (implied to be system-wide)
        local marker="core-tools-marker"
        global=1
    fi

    # Using the WINDIR environment variable as a lazy litmus test for
    #   whether or not we're in a Windows machine using MobaXterm.
    if [ -n "$WINDIR" ]; then
        # Windows
        # In MobaXterm-style tmux, .bashrc is not loaded for shell sessions within tmux.
        # Not using .bash_profile globally for the moment because a Debian-based system
        #     will not load .bashrc at all if .bash_profile is present. Will deal with that later.
        # Note: MobaXterm ignores the concept of a global setup. No use case for it.
        local file="$HOME/.bash_profile"
    else
        # Unix

        case "$SHELL" in
        "/bin/bash")
            if uname | grep -qi "^Darwin" || uname | grep -qi "FreeBSD"; then
                printf "BSD-like operations are not supported at this time.\n"
                exit 3
            fi

            if (( $global )); then
                # Global
                # The global file varies from distribution or distribution.
                # /etc/bashrc - Fedora/CentOS
                # /etc/bash.bashrc - Ubuntu
                for __file in /etc/bashrc /etc/bash.bashrc; do
                    if [ -f "$__file" ]; then
                        local file="$__file"
                    fi
                done

                if [ -z "$file" ]; then
                    printf "Unable to find a global BASH profile file to attach the tools loader to.\n"
                    exit 2
                fi
            else
                # Local
                local file="$HOME/.bashrc"
            fi

            ;;
        *)
            printf "Unsupported shell: %s\n" "$SHELL" >&2
            exit 1
            ;;
         esac
    fi

    if [ ! -f "$file" ] || ! grep -q "$marker" "$file"; then

        # If we are writing to a path outside of our home directory,
        #     then it is assumed that we have write permissions (probably from being root).
        printf "Applying source statement to $file\n"
        cat << EOF >> "$file"

#####################################
# $marker
export toolsDir="$(pwd)"
if printf "\$-" | grep -q i || ( [ -z "\$SSH_CLIENT" ] && printf "\$TERM" | grep -q '^dumb$' ); then
    # Load tools if we are in an interactive shell or if we are running a script from
    #     from within a "dumb" shell with no value to $SSH_CLIENT (suggesting a Desktop Startup Script).
    if [ -f "\$toolsDir/bash/bashrc" ]; then
        . \$toolsDir/bash/bashrc
    fi
fi
#####################################

EOF
    fi

}

setup
