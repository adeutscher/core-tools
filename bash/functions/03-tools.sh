
#####################
#####################
## Tools Functions ##
#####################
#####################

# Functions made around managing this tools/ directory and/or my other SVN utility checkouts.



# Aliases/Functions for reloading functions.
if __is_unix; then
    reload-tools(){
        unset __toolCount
        
        # Unset module directories so that they can be re-initialized as if freshly loaded if necessary.
        for __var in $((set -o posix; set) | grep ToolsDir= | cut -d'=' -f1); do
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

if type -ftptP git 2> /dev/null >&2 || type -ftptP git 2> /dev/null >&2; then

    update-repo(){
        if [ -z "$1" ]; then
            error "No repository path provided."
            return 1
        elif __is_svn_repo "$1"; then
            update-svn-repo "$1" "$2"
        elif __is_git_repo "$1"; then
            update-git-repo "$1" "$2"
        fi
    }

    ###########################
    # Tool Updating Functions #
    ###########################

    update-tools(){

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

        update-repo "$toolsDir" "tools"

    }

else
    alias update-tools="error 'The no version control commands found. Install SVN and/or Git, then run reload-tools.'"
fi

#################
# Git Functions #
#################
# Git functions are experimental at this stage.

# A general note on git:
## The switches used for working with a git repository when not directly in it are different between 1.X and 2.X versions of git,

__is_git_repo(){
    # Default, assume not a directory
    local __no=1

    if ! qtype git; then
        [ -n "$2" ] && error "$(printf "$Colour_Command%s$Colour_Off is not installed." "git")"
        return 1
    elif [ -n "$1" ] && [ -d "$1/.git" ]; then
        git-remote "$1" status 2> /dev/null >&2 && local __no=0
    fi

    (( "$__no" )) && [ -n "$2" ] && error "$(printf "$Colour_FilePath%s$Colour_Off does not appear to be a readable Git checkout!" "$1")"
    return $__no
}

# Check to see if Git is even installed.
# MobaXterm has an alias for saying that SVN isn not found which throws off qtype,
#     so we need to use specific flags on the type command
# Assuming that git is similar to this.
if type -ftptP git 2> /dev/null >&2; then


    git-remote(){


        # Switches on git 2.X to access a git checkout elsewhere on your file system
        #   are a bit different than 1.X

        # The purpose of this function is to not have to juggle distributions each time
        #   that I want to handle a remote checkout (will deal with exceptions on a case-by-case basis).
        # I also want to avoid 'cd'-ing into the directory if possible (in case I ctrl-c out of git and get planted there).

        if [ -z "$2" ] || [ ! -d "$1" ]; then
            return 1
        fi

        local repoDir="$(readlink -f "$1")"
        shift
        if git --version | grep -q "^git version 2\."; then
            # Git 2.X
            git -C "$repoDir" $@
        else
            # Git 1.X
            if ! git --version | grep -q "^git version 1.7.1"; then
                git --git-dir="$repoDir/.git" --work-tree="$repoDir" $@
            else
                # Found a problem with 1.7.1 (CentOS 6) where
                # pulling would fail.
                # Hitting the problem with a hammer and using 'cd'.
                # Will make the check more strict if we discover other problem cases.
                local OLD_OLDPWD="$OLDPWD"
                cd "$repoDir" && git $@
                cd "$OLDPWD"
                OLDPWD="$OLD_OLDPWD"
            fi
        fi
    }
    
    update-git-repo(){

        local repoDir="$1"
        local label="$2"
        local repoDirDisplay="$(sed "s|^$HOME|~|" <<< "$repoDir")"

        # Confirm that we have git.
        if ! qtype git; then
            error "Git is not detected on this machine. How exactly did you check this directory out?"
            # For someone to run into this, someone would have had to uninstalled git after loading their BASH session.
            return 1
        fi

        if [ -z "$repoDir" ]; then
            error "No repository path provided..."
            return 2
        fi

        # Confirm a valid repository
        if ! __is_git_repo "$repoDir" 1; then
            # Reminder: Error message is printed in __is_git_repo thanks to the extra argument
            return 3
        fi 

        # Check to see if the repository directory can be written to by the current user.
        # We have already checked to make sure that the directory exists and is readable
        #    (would have been caught in __is_git_repo).
        if [ ! -w "$repoDir" ]; then
            error "$(printf "Repository directory cannot be written to: ${Colour_FilePath}%s${Colour_Off}" "$repoDirDisplay")"
            return 4
        fi

        local __num=1

        local repoUrl="$(git-remote "$repoDir" remote -v | grep "(fetch)$" | awk 'BEGIN { count=0; remote="-" } { count=count+1; remote=$2 } END { if(count <= 1 && remote != "-" ){ print remote } else if(count > 1){ print "multiple" } }')"
        local remote="$(git-remote "$repoDir" remote | head -n1)"
        local branch="$(git-remote "$repoDir" branch | grep "^*" | head -n1 | cut -d' ' -f2)"

        if [ -z "$repoUrl" ]; then
            error "$(printf "Was unable to determine our upstream URL from our workspace: $Colour_FilePath%s$Colour_Off" "$repoDirDisplay")"
            return 5
        elif [[ "$repoUrl" =~ ^multiple$ ]]; then
            error "$(printf "More than one origin defined within repositority. Unable to know the authoritative one at the moment.: $Colour_FilePath%s$Colour_Off" "$repoDirDisplay")"
            return 5
        fi

        # Trimming a little bit of the file URI (for local checkouts) to save a character or two.
        local repoUrlDisplay="$(sed "s|^file://||" <<< "$repoUrl")"

        # Print our updating notice.
        if [ -n "$label" ]; then
            notice "$(printf "Updating $Colour_Bold%s$Colour_Off repository ($Colour_FilePath%s$Colour_Off<-${Colour_NetworkAddress}%s/${Colour_Off})" "$label" "$repoDirDisplay" "$repoUrlDisplay")"
        else
            # No label was given.
            notice "$(printf "Updating repository ($Colour_FilePath%s$Colour_Off<-${Colour_NetworkAddress}%s/${Colour_Off})" "$repoDirDisplay" "$repoUrlDisplay")"
        fi

        # Get our test domain name to try and resolve it.
        # If the domain name can be resolved, then it is assumed to be reachable.
        if grep -qP "^(https?|git)://" <<< "$repoUrl"; then
            # HTTP Clone
            local repoDomain=$(cut -d'/' -f 3 <<< "$repoUrl" | sed 's/^[^@]*@//')
        else
            # SSH Clone
            local repoDomain=$(cut -d':' -f 1 <<< "$repoUrl" | cut -d'@' -f2)
        fi
        if [ -z "$repoDomain" ]; then
            # If we can't tell the repository domain, then we have nothing to go on.
            error "$(printf "Was unable to determine our repository domain from our workspace: $Colour_FilePath%s$Colour_Off" "$repoDirDisplay")"
            return 6
        fi

        # Check to see if we can resolve a domain address address.
        if grep -qP '^(([0-9]){1,3}\.){3}([0-9]{1,3})$' <<< "$repoDomain"; then
            warning "Git workspace was checked out from an IP address."
            warning "Continuing under the assumption that it is reachable."
        elif ! qtype host; then
            warning "$(printf "The ${Colour_Command}host${Colour_Off} command was not detected on this machine.")"
            warning "Continuing, but unable to verify that we can resolve the domain name for the upstream git repository."
        elif ! timeout 1 host ${repoDomain} 2> /dev/null >&2; then
            # Note: This check will not account for cached entries in the local BIND server (if applicable)
            # Note: Avoiding "for" phrasing in non-comments to appease pluma colouring.
            error "$(printf "$Colour_Command%s$Colour_Off was unable to resolve the address of ${Colour_NetworkAddress}%s$Colour_Off. Quitting...\n" "host" "$repoDomain")"
            return 7
        fi # end else block executed after doing "pre-flight" checks for reaching the repository server.

        # Track old and new revisions (at least on our current branch).
        local oldCommit="$(git-remote "$repoDir" branch -v | sed -e '/^[^*]/d' | cut -d' ' -f3)"

        if git --version | grep -q "git version 1\."; then
            # Need to add another switch for older git versions
            local oldGitSwitch=-u
        fi

        # Update directory.
        if git-remote "$repoDir" pull $oldGitSwitch $remote $branch; then
            local newCommit="$(git-remote "$repoDir" branch -v | sed -e '/^[^*]/d' | cut -d' ' -f3)"

            if [[ "$oldCommit" != "$newCommit" ]]; then
                success "$(printf "Repository directory updated (${Colour_Bold}%s${Colour_Off} to ${Colour_Bold}r%s${Colour_Off})." "$oldCommit" "$newCommit")"
            else
                success "$(printf "Current branch is already up to date, or was checked out to a specific revision. At ${Colour_Bold}%s${Colour_Off}." "$oldCommit")"
            fi

        else
            error "$(printf "Update of repository at $Colour_FilePath%s$Colour_Off from $Colour_NetworkAddress%s$Colour_Off failed!" "$repoDirDisplay"  "$repoUrlDisplay")"
            return 8
        fi

    }
fi

#################
# SVN Functions #
#################

__is_svn_repo(){
    if ! qtype svn; then
        [ -n "$2" ] && error "$(printf "$Colour_Command%s$Colour_Off is not installed." "svn")"
        return 1
    elif [ ! -n "$1" ] || [ ! -d "$1/.svn" ] || ! svn info "$1" 2> /dev/null >&2; then
        [ -n "$2" ] && error "$(printf "$Colour_FilePath%s$Colour_Off does not appear to be a readable SVN checkout!" "$1")"
        return 1
    fi
}

# Check to see if SVN is even installed.
# MobaXterm has an alias for saying that SVN isn't found which throws off qtype,
#     so we need to use specific flags on the type command
if type -ftptP svn 2> /dev/null >&2; then

    update-svn-repo(){

        local repoDir="$1"
        local label="$2"
        local repoDirDisplay="$(sed "s|^$HOME|~|" <<< "$repoDir")"

        # Double-Check to see if SVN is even installed.
        # MobaXterm has an alias for saying that SVN is not found which throws off qtype,
        #     so we need to use specific flags on the type command
        if ! type -ftptP svn 2> /dev/null >&2; then
            error "Subversion is not detected on this machine. How exactly did you check this directory out?"
            return 1
        fi

        if [ -z "$repoDir" ]; then
            error "No repository path provided..."
            return 2
        fi

        # Check for SVN-specific errors
        if ! __is_svn_repo "$repoDir" 1; then
            # Reminder: Error message is printed in __is_svn_repo
            return 3
        elif svn status "$repoDir" 2> /dev/null | head -n1 | grep -q "\ *L"; then
            # To consider: Is there a better place to put this?
            # Also: Is there a better way to check for locks? Assuming a couple of things that I would rather not:
            #   - That the top dir will always be the repository dir.
            #   - That the lock status flag will never be pre-empted by another flag.
            error "$(printf "SVN workspace at $Colour_FilePath%s$Colour_Off is locked..." "$repoDir")"
            return 3
        fi

        # Check to see if the repository directory can be written to by the current user.
        # We have already checked to make sure that the directory exists and is readable
        #    (would have been caught in __is_svn_repo).
        if [ ! -w "$repoDir" ]; then
            error "$(printf "Repository directory cannot be written to: ${Colour_FilePath}%s${Colour_Off}" "$repoDirDisplay")"
            return 4
        fi

        local repoUrl="$(svn info "$repoDir" | grep "^URL" | cut -d' ' -f 2-)"
        if [ -z "$repoUrl" ]; then
            error "$(printf "Was unable to determine our repository URL from our workspace: $Colour_FilePath%s$Colour_Off" "$repoDirDisplay")"
            # If we can't tell the repository URL with `svn info`, then the svn command won't be able to tell either.
            return 5
        fi

        # Trimming a little bit of the file URI (for local checkouts) to save a character or two.
        local repoUrlDisplay="$(sed "s|^file://||" <<< "$repoUrl")"

        # Print our updating notice.
        if [ -n "$label" ]; then
            notice "$(printf "Updating $Colour_Bold%s$Colour_Off repository ($Colour_FilePath%s$Colour_Off<-${Colour_NetworkAddress}%s/${Colour_Off})" "$label" "$repoDirDisplay" "$repoUrlDisplay")"
        else
            # No label was given.
            notice "$(printf "Updating repository ($Colour_FilePath%s$Colour_Off<-${Colour_NetworkAddress}%s/${Colour_Off})" "$repoDirDisplay" "$repoUrlDisplay")"
        fi

        if grep '^file:///' <<< "$repoUrl"; then
            if [ -d "$repoUrlDisplay" ]; then
                if [ -r "$repoUrlDisplay" ]; then
                    notice "SVN workspace is checked out from a local path."
                else
                    error "SVN workspace could not be read."
                    return 7
                fi
            else
                # Directory does not exist.
                error "$(printf "Repository cannot be found at $Colour_FilePath%d$Colour_Off..." "$(sed "s|file://||" <<< "$repoUrl")")"
                return 8
            fi
        else
            # SVN workspace is checked out from a network location.

            # Get our test domain name to try and resolve it.
            # If the domain name can be resolved, then it is assumed to be reachable.
            local repoDomain=$(cut -d'/' -f 3 <<< "$repoUrl")
            if [ -z "$repoDomain" ]; then
                # If we can't tell the repository domain with `svn info`, then the svn command won't be able to tell either.
                error "$(printf "Was unable to determine our repository domain from our workspace: $Colour_FilePath%s$Colour_Off" "$repoDirDisplay")"
                return 6
            fi

            # Check to see if we can resolve a domain address address.
            if grep -qP '^(([0-9]){1,3}\.){3}([0-9]{1,3})$' <<< "$repoDomain"; then
                warning "SVN workspace was checked out from an IP address."
                warning "Continuing under the assumption that it is reachable."
            elif ! qtype host; then
                warning "$(printf "The ${Colour_Command}host${Colour_Off} command was not detected on this machine.")"
                warning "Continuing, but unable to verify that we can resolve the domain name for our SVN repository."
            elif ! timeout 1 host ${repoDomain} 2> /dev/null >&2; then   
                # Note: This check will not account for cached entries in the local BIND server (if applicable)
                # Note: Avoiding "for" phrasing in non-comments to appease pluma colouring.
                error "$(printf "$Colour_Command%s$Colour_Off was unable to resolve the address of ${Colour_NetworkAddress}%s$Colour_Off. Quitting...\n" "host" "$repoDomain")"
                return 7
            fi # end else block executed after doing "pre-flight" checks for reaching the repository server.
        fi

        # Track old and new revisions.
        
        local oldRev="$(svn info "$repoDir" 2> /dev/null | grep '^Revision' | cut -d' ' -f2)"
        # Update directory.
        if svn up "$repoDir"; then
            local newRev="$(svn info "$repoDir" 2> /dev/null | grep '^Revision' | cut -d' ' -f2)"
            if [ "$oldRev" -lt "$newRev" ]; then
                success "$(printf "Repository directory updated (${Colour_Bold}r%d${Colour_Off} to ${Colour_Bold}r%d${Colour_Off})." "$oldRev" "$newRev")"
            else
                success "$(printf "Repository is already up to date (at ${Colour_Bold}r%d${Colour_Off})." "$oldRev")"
            fi

        else
            error "$(printf "Update of repository at $Colour_FilePath%s$Colour_Off from $Colour_NetworkAddress%s$Colour_Off failed!" "$repoDirDisplay"  "$repoUrlDisplay")"
            return 8
        fi
    }

fi

