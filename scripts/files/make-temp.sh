#!/bin/bash

#set -x

# Commands
readonly DATE=/bin/date
readonly EGREP=/bin/egrep
readonly LN="/bin/ln -s"
readonly LS=/bin/ls
readonly MKDIR="/bin/mkdir -p"
readonly MV=/bin/mv
readonly READLINK="/bin/readlink -f"
readonly RM=/bin/rm
readonly RMDIR=/bin/rmdir
readonly SED=/bin/sed
readonly TAIL=/usr/bin/tail
readonly TOUCH=/bin/touch

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
}

notice(){
    printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

success(){
    printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

warning(){
    printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

# Script functions

usage(){
    notice "$(printf "Usage: ./$GREEN%s$NC [-h] [-d temp-dir] [-l last-temp-link] [-c temp-link] [-w working-directory]" "$(basename $0)")"
}

options(){

    # Default 
    # Location of our storage location and symbolic link, relative to the working directory.
    # Using relative links avoids problems with temp files in mounted locations.
    TEMPDIR=./.temp
    TEMPLINK=./temp
    LASTTEMPLINK=./last-temp
    WORKINGDIRECTORY=$HOME

    while [ -n "$1" ]; do
        local opt=$1
        case "$opt" in
        "-d")
            shift
            if [ -z "$1" ]; then
                usage
                exit 1
            elif grep -q '^-' <<< "$1"; then
                error "$(printf "Invalid directory name: $GREEN%s$NC" "$1")"
                exit 2
            fi
            _TEMPDIR=$1
            ;;
        "-c")
            shift
            if [ -z "$1" ]; then
                usage
                exit 1
            elif [ ! -d "$(dirname $1)" ]; then
                error "$(printf "Parent directory for current temp link does not exist: $GREEN%s$NC" "$(dirname $1)")"
                exit 2
            elif grep -q '^-' <<< "$1"; then
                error "$(printf "Invalid directory name: $GREEN%s$NC" "$1")"
                exit 3
            elif grep -q '^/' <<< "$1"; then
                warning "$(printf "Setting the current temp link to the absolute path of $GREEN%s$NC." "$1")"
                warning "This means that this link will not work properly if the filesystem is mounted remotely."
            fi
            _TEMPLINK=$1
            ;;
        "-l")
            shift
            if [ -z "$1" ]; then
                usage
                exit 1
            elif [ ! -d "$(dirname $1)" ]; then
                error "$(printf "Parent directory for current temp link does not exist: $GREEN%s$NC" "$(dirname $1)")"
                exit 2
            elif grep -q '^-' <<< "$1"; then
                error "$(printf "Invalid directory name: $GREEN%s$NC" "$1")"
                exit 3
            elif grep -q '^/' <<< "$1"; then
                warning "$(printf "Setting the previous non-empty temp link to the absolute path of $GREEN%s$NC." "$1")"
                warning "This means that this link will not work properly if the filesystem is mounted remotely."
            fi
            _LASTTEMPLINK=$1
            ;;
        "-w")
            shift
            if [ ! -d "$1" ]; then
                error "$(printf "Working directory not found: $GREEN%s$NC" "$1")"
                exit 1
            fi
            _WORKINGDIRECTORY=$1
            ;;
        "-h")
            usage
            exit 0
            ;;
        esac
        shift
    done
    
    if [ -n "$_TEMPDIR" ]; then
        TEMPDIR="$_TEMPDIR"
        notice "$(printf "Temporary directories will be stored in $GREEN%s$NC" "$TEMPDIR")"
    else
        notice "$(printf "Temporary directories will be stored in $GREEN%s$NC (default location)" "$TEMPDIR")"
    fi
    
    if [ -n "$_TEMPLINK" ]; then
        TEMPLINK="$_TEMPLINK"
        notice "$(printf "The link to the current temp dir will be placed at $GREEN%s$NC" "$TEMPLINK")"
    else
        notice "$(printf "The link to the current temp dir will be placed at $GREEN%s$NC (default location)" "$TEMPLINK")"
    fi
    
    if [ -n "$_LASTTEMPLINK" ]; then
        LASTTEMPLINK="$_LASTTEMPLINK"
        notice "$(printf "The link to the previous temp dir will be placed at $GREEN%s$NC" "$LASTTEMPLINK")"
    else
        notice "$(printf "The link to the previous temp dir will be placed at $GREEN%s$NC (default location)" "$LASTTEMPLINK")"
    fi
    
    if [ -n "$_WORKINGDIRECTORY" ]; then
        WORKINGDIRECTORY="$_WORKINGDIRECTORY"
        notice "$(printf "Relative links will be based out of $GREEN%s/$NC" "$WORKINGDIRECTORY")"
    else
        notice "$(printf "Relative links will be based out of $GREEN%s/$NC (default location)" "$WORKINGDIRECTORY")"
    fi
}

function make_temp {

    cd "$WORKINGDIRECTORY"

    CURRENT_DATE=$($DATE +"%F")

    DAILYTEMPDIR="$TEMPDIR/$CURRENT_DATE"

    # Step 1: Clear out empty directories from the temporary directory.
    ## Empty folders just add to the confusion.
    ## Trusting rmdir to preserve any foldes with content, but clear out empties.
    ## The exception to this is the current temporary directory
    ##       (if the script is run on the same day)

    # Apply lock to guard current day's directory (if such a directory exists)
    if [ -d "$DAILYTEMPDIR/" ]; then
        $TOUCH "$DAILYTEMPDIR/.rotate-lock"
    fi

    # Remove directories.
    # Soft delete. Will fail as intended if the directory has any contents.
    $RMDIR "$TEMPDIR/"* 2> /dev/null
    
    # Make sure that the temporary directory for the current day exists.
    
    if [ -d "$DAILYTEMPDIR/" ]; then
        # Remove lock, if it was placed.
        if [ -f "$DAILYTEMPDIR/.rotate-lock" ]; then
            $RM "$DAILYTEMPDIR/.rotate-lock"
        fi
    else # End 'directory exists' block.
        # Directory does not currently exist. Create directory.
        $MKDIR -p "$DAILYTEMPDIR" 2> /dev/null
    
        # If we have just created the daily temp dir, then this is a proper rotation
        #    (as opposed to a re-do on the same day.
        
        # Get the most recent temp folder that is NOT the current daily temp directory.
        local lastDir=$($LS "$TEMPDIR" | $EGREP '[0-9]{4}(\-[0-9]{2}){2}' | $SED '/^'$CURRENT_DATE'$/d' | $TAIL -n 1)
        # If static resources exist, carry them forward from the last directory to today.
        if [ -d "$TEMPDIR/$lastDir/static/" ]; then
        
            # Weak rmdir to make sure that the static directory isn't empty.
            if ! $RMDIR "$TEMPDIR/$lastDir/static" 2> /dev/null; then
                $MV "$TEMPDIR/$lastDir/static/" "$DAILYTEMPDIR/static/"
                # In case static/ was the only directory in the last temp/
                # Weakly try to remove the last temp directory again.
                $RMDIR "$TEMPDIR/$lastDir" 2> /dev/null
            fi # End weak rmdir check
            
        fi # End static check
    fi # End 'temp directory did not exist' block


    # If static resources exist, carry them forward from the last directory to today.
        if [ -d "$lastDir/static/" ]; then
            $MV "$lastDir/static/" "$DAILYTEMPDIR/static/"
        fi

    ## Step 2: Update the link to the current temporary directory if necessary.
    if [ ! -L "$TEMPLINK" ] || [[ $(__abs_path "$DAILYTEMPDIR") != "$($READLINK $TEMPLINK)" ]]; then
        # Temporary link doesn't exist
        # OR   
        # Points to a different location.
        $RM "$TEMPLINK" 2> /dev/null

        # Make new temp link.
        $LN "$DAILYTEMPDIR" "$TEMPLINK"
    fi # End check to see if updating the current temporary directory link is necessary.

    # Step 3: Manage the link to our most recent temporary directory (other than the current day's directory).
    if [ -d "$TEMPDIR" ]; then
        local lastDir=$($LS "$TEMPDIR" | $EGREP '[0-9]{4}(\-[0-9]{2}){2}' | $SED '/^'$CURRENT_DATE'$/d' | $TAIL -n 1)

        # Make sure that the last dir doesn't only contain empty directories.
        # Very much doubt that I'll regret getting rid of a temp directory for its name alone.
        # Keep re-assigning lastDir until we find one with content.
        while [ -n "$lastDir" ] && $RMDIR "$TEMPDIR/$lastDir/"* 2> /dev/null && $RMDIR "$TEMPDIR/$lastDir" 2> /dev/null; do
            local lastDir=$($LS "$TEMPDIR" | $EGREP '[0-9]{4}(\-[0-9]{2}){2}' | $SED '/^'$CURRENT_DATE'$/d' | $TAIL -n 1)
        done

        # Make sure that we aren't removing and re-adding the very same link.
        if [ -n "$lastDir" ] && ([ ! -L "$LASTTEMPLINK" ] || [[ "$TEMPDIR/$lastDir" != "$($READLINK $LASTTEMPLINK)" ]]); then
            $RM "$LASTTEMPLINK" 2> /dev/null
            if [ -d "$TEMPDIR/$lastDir" ]; then
                $LN "$TEMPDIR/$lastDir" "$LASTTEMPLINK"
            fi # End directory exists check.
        # End check to see if updating the previous temporary directory link is necessary.
        elif [ -L "$LASTTEMPLINK" ] && [ ! -d "$(readlink "$LASTTEMPLINK")" ]; then
            # If there is NO candidate for a last temp link and the link currently exists as a dead link, then axe the link.
            rm "$LASTTEMPLINK"
            # The likely cause of this is that you've cleaned out the contents all of the non-current days, leavinng empty directories.
        fi
    fi # End double-check to check if the container folder exists.
    
}

# Function to get absolute path without realpath command.
__abs_path(){
    cd "$1"
    pwd -P
}

options $@
make_temp

