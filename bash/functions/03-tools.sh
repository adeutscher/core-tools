
#####################
#####################
## Tools Functions ##
#####################
#####################

# Aliases/Functions for reloading functions.
if __is_unix; then
    reload-tools(){
        unset __toolCount

        # Unset module directories so that they can be re-initialized as if freshly loaded if necessary.
        for __var in $(env | grep -P "^[^=]+ToolsDir=" | cut -d'=' -f1); do
            unset $__var
        done

        # Loading tools file directly, as the tools may be installed locally or system-wide.
        . "$toolsDir/bash/bashrc"
    }
else
    # Windows via MobaXterm
    # Will only ever be set up locally.
    reload-tools(){
        unset __toolCount
        . ~/.bash_profile
    }

fi

if type -ftptP git 2> /dev/null >&2 || type -ftptP svn 2> /dev/null >&2; then

    ###########################
    # Tool Updating Functions #
    ###########################

    function update-tools(){

        # Confirm SSH permissions in advance, because some tools might be git repos with SSH remotes.
        ssh-fix-permissions

        local tools="$(compgen -A function update-tools-)"
        local toolsCount="$(wc -w <<< "$tools")"

        if [ "$toolsCount" -eq 0 ]; then
            error "$(printf "Detected no update functions for tools. Update functions must begin with '${Colour_Bold}update-tools-${Colour_Off}'.")"
            return 1
        fi

        notice "$(printf "Updating tool repositories ($Colour_Bold%d$Colour_Off update functions to run)" "$toolsCount")"
        for updateFunction in $tools; do
            local currentCount=$((${currentCount:-0}+1))
            notice "$(printf "Running $Colour_Command%s$Colour_Off ($Colour_Bold%d$Colour_Off of $Colour_Bold%d$Colour_Off)" "$updateFunction" "$currentCount" "$toolsCount")"
            "$updateFunction"
        done
        unset updateFunction

        # Double-check that SSH permissions are still solid.
        ssh-fix-permissions

        # Only re-compile SSH config after we've cycled through all possible repositories to source from.
        # Making a separate update-tools-_ function for SSH would execute in an unreliable order,
        #     and I don't want to implement the shenanigans neeeded just for the sake of SSH.
        if qtype ssh-compile-config; then
            ssh-compile-config
        fi
    }

    update-tools-core(){

        if [ -z "$toolsDir" ]; then
            error 'Tool directory is unknown! It should be recorded in the $toolsDir variable.'
            return 1
        fi

        update-repo "$toolsDir" "tools" || return 1

        # Apply updates to various files.
        for __script in setup-tools crontab-setup tmux-configuration vimrc-setup; do
            "${toolsDir}/scripts/setup/${__script}.sh"
        done
        unset __script
    }

else
    alias update-tools="error 'No version control commands found. Install SVN and/or Git, then run \"reload\"'"
fi
