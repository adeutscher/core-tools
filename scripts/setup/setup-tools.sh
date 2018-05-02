#!/bin/bash

# Load common functions.
. "$(dirname "${0}")/functions.sh"

setup(){

    cd "$toolsDir"

    if pwd | grep -Pq "$HOME($|/)"; then
        # Setting up the tools locally for a user.
        global=0
    else
        # Setting up tools in a common directory (implied to be system-wide)
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
            if uname | grep -qi -e "^Darwin" -e "FreeBSD"; then
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
            error "$(printf "Unsupported shell: ${GREEN}%s${NC}" "$SHELL")" >&2
            exit 1
            ;;
         esac
    fi

    # If we are writing to a path outside of our home directory,
    #     then it is assumed that we have write permissions (probably from being root).
    CONTENTS="$(cat << EOF
#####################################
# Core-Tools Suite
export toolsDir="${toolsDir}"
if [[ \$- == *i* ]] || (( \${ANSIBLE:-0} )) || ( [ -z "\$SSH_CLIENT" ] && [[ "\$TERM" == 'dumb' ]] ); then
  # Load tools if one of the following is true:
  #   * We are in an interactive shell
  #   * ANSIBLE variable is set to a non-zero number (library author's addition)
  #   * We are running a script from from within a "dumb" shell with no value to \$SSH_CLIENT (suggesting a Desktop Startup Script).
  if [ -f "\${toolsDir}/bash/bashrc" ]; then
    . \${toolsDir}/bash/bashrc

    # Convenient marker that tools have been loaded for later in bashrc.
    TOOLS_LOADED=1
  fi
fi
#####################################
EOF
)"
    "${DOTFILE_SCRIPT}" "${file}" core-tools-marker - <<< "${CONTENTS}"

}

setup
