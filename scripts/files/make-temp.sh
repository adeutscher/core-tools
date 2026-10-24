#!/bin/bash

# Pattern for daily temp directory names (e.g. 2026-10-19-monday).
readonly DATE_DIR_REGEX='^[0-9]{4}(-[0-9]{2}){2}(-[a-z]+day)?$'

# Common message functions.

# Define colours
if [ -t 1 ]; then
    BLUE='\033[1;34m'
    GREEN='\033[1;32m'
    RED='\033[1;31m'
    YELLOW='\033[1;93m'
    NC='\033[0m' # No Color
fi

error(){
    printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "$0")" "$@" >&2
}

notice(){
    [ -n "$QUIET" ] && return 0
    printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "$0")" "$@"
}

success(){
    printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "$0")" "$@"
}

warning(){
    printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "$0")" "$@" >&2
}

# Script functions

usage(){
    # Printed directly so that usage is still shown in quiet mode.
    printf "Usage: ./$GREEN%s$NC [-h] [-q] [-d temp-dir] [-l last-temp-link] [-c temp-link] [-w working-directory]\n" "$(basename "$0")"
}

options(){

    # Default
    # Location of our storage location and symbolic link, relative to the working directory.
    # Using relative links avoids problems with temp files in mounted locations.
    TEMPDIR=./.temp
    TEMPLINK=./temp
    LASTTEMPLINK=./last-temp
    WORKINGDIRECTORY=$HOME

    while [ $# -gt 0 ]; do
        case "$1" in
        "-d")
            shift
            if [ -z "$1" ]; then
                usage
                exit 1
            elif [[ $1 == -* ]]; then
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
            elif [[ $1 == -* ]]; then
                error "$(printf "Invalid directory name: $GREEN%s$NC" "$1")"
                exit 3
            elif [[ $1 == /* ]]; then
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
            elif [[ $1 == -* ]]; then
                error "$(printf "Invalid directory name: $GREEN%s$NC" "$1")"
                exit 3
            elif [[ $1 == /* ]]; then
                warning "$(printf "Setting the previous non-empty temp link to the absolute path of $GREEN%s$NC." "$1")"
                warning "This means that this link will not work properly if the filesystem is mounted remotely."
            fi
            _LASTTEMPLINK=$1
            ;;
        "-w")
            shift
            if [ -z "$1" ]; then
                usage
                exit 1
            elif [ ! -d "$1" ]; then
                error "$(printf "Working directory not found: $GREEN%s$NC" "$1")"
                exit 1
            fi
            _WORKINGDIRECTORY=$1
            ;;
        "-q")
            QUIET=1
            ;;
        "-h")
            usage
            exit 0
            ;;
        *)
            error "$(printf "Unknown option: $GREEN%s$NC" "$1")"
            usage
            exit 1
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

# Confirm that the parent directory of a link location exists.
# Must be run from the working directory, since link paths are relative to it.
check_link_parent(){
    local label="$1"
    local path="$2"
    if [ ! -d "$(dirname "$path")" ]; then
        error "$(printf "Parent directory for the %s does not exist: $GREEN%s$NC" "$label" "$(dirname "$path")")"
        exit 2
    fi
}

function make_temp {

    if ! cd "$WORKINGDIRECTORY"; then
        error "$(printf "Unable to enter working directory: $GREEN%s$NC" "$WORKINGDIRECTORY")"
        exit 1
    fi

    check_link_parent "current temp link" "$TEMPLINK"
    check_link_parent "previous temp link" "$LASTTEMPLINK"

    # Use the C locale so that day names always match DATE_DIR_REGEX.
    CURRENT_DATE=$(LC_ALL=C date +"%F-%A" | tr '[:upper:]' '[:lower:]')

    DAILYTEMPDIR="$TEMPDIR/$CURRENT_DATE"

    local lastDir

    # Step 1: Clear out empty directories from the temporary directory.
    ## Empty folders just add to the confusion.
    ## Trusting rmdir to preserve any foldes with content, but clear out empties.
    ## The exception to this is the current temporary directory
    ##       (if the script is run on the same day)

    # Apply lock to guard current day's directory (if such a directory exists)
    if [ -d "$DAILYTEMPDIR/" ]; then
        touch "$DAILYTEMPDIR/.rotate-lock"
    fi

    # Step 1.5: Remove next/previous navigation links
    ## Only look directly inside of each daily directory,
    ##   so that links with the same names inside of temp content are left alone.
    while IFS= read -r __link; do
        [ -n "${__link}" ] && rm "${__link}"
    done <<< "$(find "${TEMPDIR}" -mindepth 2 -maxdepth 2 -type l \( -name next -o -name previous \) 2> /dev/null | sort)"

    # Remove directories.
    # Soft delete. Will fail as intended if the directory has any contents.
    rmdir "$TEMPDIR/"* 2> /dev/null

    # Make sure that the temporary directory for the current day exists.

    if [ -d "$DAILYTEMPDIR/" ]; then
        # Remove lock, if it was placed.
        if [ -f "$DAILYTEMPDIR/.rotate-lock" ]; then
            rm "$DAILYTEMPDIR/.rotate-lock"
        fi
    else # End 'directory exists' block.
        # Directory does not currently exist. Create directory.
        mkdir -p "$DAILYTEMPDIR" 2> /dev/null

        # If we have just created the daily temp dir, then this is a proper rotation
        #    (as opposed to a re-do on the same day.

        # Get the most recent temp folder that is NOT the current daily temp directory.
        lastDir="$(__last_dir)"
        # If static resources exist, carry them forward from the last directory to today.
        if [ -n "$lastDir" ] && [ -d "$TEMPDIR/$lastDir/static/" ]; then

            # Weak rmdir to make sure that the static directory isn't empty.
            if ! rmdir "$TEMPDIR/$lastDir/static" 2> /dev/null; then
                mv "$TEMPDIR/$lastDir/static/" "$DAILYTEMPDIR/static/"
                # In case static/ was the only directory in the last temp/
                # Weakly try to remove the last temp directory again.
                rmdir "$TEMPDIR/$lastDir" 2> /dev/null
            fi # End weak rmdir check

        fi # End static check
    fi # End 'temp directory did not exist' block

    ## Step 2: Update the link to the current temporary directory if necessary.
    if [ ! -L "$TEMPLINK" ] || [[ "$(__abs_path "$DAILYTEMPDIR")" != "$(readlink -f "$TEMPLINK")" ]]; then
        # Temporary link doesn't exist
        # OR
        # Points to a different location.
        rm "$TEMPLINK" 2> /dev/null

        # Make new temp link.
        ln -s "$DAILYTEMPDIR" "$TEMPLINK"
    fi # End check to see if updating the current temporary directory link is necessary.

    # Step 3: Manage the link to our most recent temporary directory (other than the current day's directory).
    if [ -d "$TEMPDIR" ]; then
        lastDir="$(__last_dir)"

        # Make sure that the last dir doesn't only contain empty directories.
        # Very much doubt that I'll regret getting rid of a temp directory for its name alone.
        # Keep re-assigning lastDir until we find one with content.
        while [ -n "$lastDir" ] && rmdir "$TEMPDIR/$lastDir/"* 2> /dev/null && rmdir "$TEMPDIR/$lastDir" 2> /dev/null; do
            lastDir="$(__last_dir)"
        done

        # Make sure that we aren't removing and re-adding the very same link.
        if [ -n "$lastDir" ] && { [ ! -L "$LASTTEMPLINK" ] || [[ "$(__abs_path "$TEMPDIR/$lastDir")" != "$(readlink -f "$LASTTEMPLINK")" ]]; }; then
            rm "$LASTTEMPLINK" 2> /dev/null
            # Create link to previous directory if such a thing exists.
            [ -d "$TEMPDIR/$lastDir" ] && ln -s "$TEMPDIR/$lastDir" "$LASTTEMPLINK"
        # End check to see if updating the previous temporary directory link is necessary.
        elif [ -L "$LASTTEMPLINK" ] && [ ! -e "$LASTTEMPLINK" ]; then
            # If there is NO candidate for a last temp link and the link currently exists as a dead link, then axe the link.
            rm "$LASTTEMPLINK"
            # The likely cause of this is that you've cleaned out the contents all of the non-current days, leaving empty directories.
        fi
    fi # End double-check to check if the container folder exists.

    local __directories
    __directories="$(__date_dirs)"

    # Step 4: Create links to the next/previous directory.
    unset __previous_monitored
    while IFS= read -r __current_directory; do
      [ -z "${__current_directory}" ] && continue
      if [ -n "${__previous_monitored}" ]; then
        __nav_link "${__previous_monitored}" "${TEMPDIR}/${__current_directory}/previous"
      fi
      __previous_monitored="${__current_directory}"
    done <<< "${__directories}"

    unset __previous_monitored
    while IFS= read -r __current_directory; do
      [ -z "${__current_directory}" ] && continue
      if [ -n "${__previous_monitored}" ]; then
        __nav_link "${__previous_monitored}" "${TEMPDIR}/${__current_directory}/next"
      fi
      __previous_monitored="${__current_directory}"
    done <<< "$(tac <<< "${__directories}")"
}

# Function to get absolute path without realpath command.
__abs_path(){
    cd "$1" || return 1
    pwd -P
}

# List the names of daily temp directories, oldest first.
__date_dirs(){
    find "$TEMPDIR" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2> /dev/null | grep -E "$DATE_DIR_REGEX" | sort
}

# Get the most recent daily temp directory that is NOT the current daily temp directory.
__last_dir(){
    __date_dirs | grep -vxF "$CURRENT_DATE" | tail -n 1
}

# Create a navigation link to a sibling daily directory.
# Real content that already uses the link's name is left alone.
__nav_link(){
    if [ -e "$2" ] && [ ! -L "$2" ]; then
        notice "$(printf "Not replacing existing content with a navigation link: $GREEN%s$NC" "$2")"
        return 1
    fi
    ln -sfn "../$1" "$2"
}

options "$@"
make_temp
