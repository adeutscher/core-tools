#!/bin/sh
#########################
# rsync Rotation Script #
# Author: /u/tidal49    #
# Version: 2.1          #
#########################
#set -x

#############
# Functions #
#############

die_error (){
    print_error "$1"
    exit 3
}

die_help (){
    cat << EOF
    rsync Rotation Script switches:
        --help, -h  Print this menu
        -c count    Count of how many backups to keep on file (default 7)
        -d          Replace duplicate files in a backup using fdupes.
                        Your fdupes version must support the -L/--linkhard option.
        -f flags    Extra flags to pass to rsync
        -i          Directory to back up. Mandatory argument
        -m          Monochrome mode. Do not print terminal colours.
        -o          Directory that backups will be placed in. Mandatory argument
        -t          Test mode. The script will go through its regular behaviour, EXCEPT for actually running rsync
        -v          Verbose mode. Print more output.  
EOF
    exit 0
}

die_usage (){
    printf "Usage: $0 -o output_path -i input_path [-c retention-count] [-f \"extra-rsync-flags\"] [-v] [-m]\nFor help: $0 -h\n"
    exit ${1:-1}
}

disable_colours (){

    # Reset
    unset Color_Off       # Zip

    # Bold High Intensity
    unset BIRed        # Nada
    unset BIGreen      # Nothing
    unset BIYellow     # Zero
    unset BIBlue       # Blank
}

enable_colours (){
    # Reset
    Color_Off='\e[0m'       # Text Reset

    # Bold High Intensity
    BIRed='\e[1;91m'        # Red
    BIGreen='\e[1;92m'      # Green
    BIYellow='\e[1;93m'     # Yellow
    BIBlue='\e[1;94m'       # Blue
}

handle_arguments(){
    # Uncomment if arguments are mandatory.
    if [ "$#" == "0" ]; then
        die_usage
    fi

    set_defaults
    enable_colours

    while [ "$#" -gt 0 ]; do
        print_debug "Argument: $1"
        case "$1" in
        "-c")
            shift
            __arg_count="$(echo "$1" | grep -om1 '^[0-9]*$')"
            if [ -z "$__arg_count" ]; then
                mark_error "Invalid value \"$1\" for \"-c\" switch. Must be an integer."
            fi
            ;;
        "-f")
            shift
            __other_rsync_args="$1"
            ;;
        "--help")
            die_help
            ;;
        "-i")
            shift
            __input_path="$(echo "$1" | sed 's/\/*$//')"
            ;;
        "-o")
            shift
            __output_path="$(echo "$1" | sed 's/\/*$//')"
            ;;
        "-"[A-Za-z]*)
            # Fallback case for basic flags.
            for s in "$(echo "$1" | grep -o [A-Za-z])"; do
                case $s in
                    "d")
                        # Further deduplication through fdupes and hard links
                        __arg_dupes="1"
                        ;;
                    "h")
                        die_help
                        ;;
                    "m")
                        # Enable monochrome output.
                        disable_colours
                        ;;
                    "t")
                        # Enable test mode - rsync will not run
                        __arg_test="1"
                        ;;
                    "v")
                        # Enable verbose output
                        __arg_verbose="1"
                        ;;
                    *)
                        mark_error "Unknown flag \"-$s\""
                        ;;
                esac
            done
            unset s
            ;;
        *)
            mark_error "Unknown argument: $1"
        esac
        # Shift to next argument
        shift
    done

    # Assign values to outside-facing variables.
    __verbose="${__arg_verbose:-$__default_verbose}"

    __count="${__arg_count:-$__default_count}"
    __test="${__arg_test:-$__default_test}"
    __dupes="${__arg_dupes:-$__default_dupes}"

    # Check script-specific items here (validate input).

    if [ -z "$__input_path" ]; then
        mark_error "Input path not provided (-i switch)"
    elif [ ! -d "$__input_path" ]; then
        mark_error "Source directory does not exist: ${BIGreen}$__input_path${Color_Off}"
    fi

    if [ -z "$__output_path" ]; then
        mark_error "Output path not provided (-o switch)"
    elif [ ! -d "$__output_path" ]; then
        print_warning "Destination directory does not exist: ${BIGreen}$__output_path${Color_Off}. Will attempt to create this directory."
    fi

    if [ "${__dupes:-__dupes_default}" -gt 0 ]; then
        
        if ! type fdupes 2> /dev/null >&2; then
            mark_error "The fdupes command is not installed on this system."
        else
            # Some packagings of fdupes do not support the -L/--linkhard option to reduce duplicates with hard links.
            # For example, Ubuntu 12.04 supports this feature, while CentOS 6.5 does not.
            
            # Checking the --help menu for a listing
            fdupes --help 2> /dev/null | grep -q '\-\-linkhard'
            if [ "$?" -gt 0 ]; then
                mark_error "Your version of fdupes does not support the -L/--linkhard option."
            fi
        fi
    fi

    # Double-check that rsync is installed.
    if ! type rsync 2> /dev/null >&2; then
        mark_error "The rsync command is not installed on this system."
    fi

    # Print out errors if they exist and then exit.
    if [ "${error_count:-0}" -gt 0 ]; then
        if [ "${error_count}" -gt 1 ]; then
            plural="s"
        fi

        print_error "${error_count} error${plural} found..."
        
        die_usage 2
    fi
    }

mark_error(){
    print_error "${1}"
    error_count="$((${error_count:-0}+1))"
}

print_debug (){
    if [ "$__verbose" -gt 0 ]; then
        printf "${BIYellow}[Debug]${Color_Off} $1\n"
        
    fi
}

print_error (){
    printf "${BIRed}[Error]${Color_Off} $1\n"
}

print_notice (){
    printf "${BIBlue}[Notice]${Color_Off} $1\n"
}

print_warning (){
    printf "${BIYellow}[Warning]${Color_Off} $1\n"
}

set_defaults(){
    # Debug Setting
    __default_verbose="0"
    __verbose="$__default_verbose"

    # Test mode flag
    __default_test="0"
    __test="$__default_test"
    
    # Rsync Rotation Count
    __default_count="7"
    __count="$__default_count"

    # Rsync Rotation Count
    __default_dupes="0"
    __count="$__default_dupes"
}

handle_arguments "$@"

## Begin script content/functions below.

backup_directory (){

    if [ ! -d "$__output_path" ]; then
        print_notice "Attempting to create destination directory: ${BIGreen}$__output_path${Color_Off}"
        mkdir_command="mkdir -p \"$__output_path\""
        print_debug "mkdir command: $mkdir_command"
        if [ "$__test" -gt 0 ]; then
            print_notice ${BIRed}'TEST MODE ENABLED! MKDIR IS NOT ACTUALLY BEING RUN!'${Color_Off}
        else
            eval $mkdir_command
        fi
        result="$?"
        if [ "$result" -gt 0 ]; then
            die_error "Unable to create destination directory (Exit code ${result})."
        fi
    fi

    backup_date="$(date +"%Y-%m-%d-%H-%M-%S")"
    backup_dest="$__output_path/$backup_date"

    last_backup="$(ls -r $__output_path/ 2> /dev/null  | egrep -m1 '^[0-9]{4}(\-[0-9]{2}){5}$')"
    # Check for a previous backup to base our content on.
    if [ -n "$last_backup" ]; then
        print_notice "Pre-existing backup (${BIGreen}$last_backup${Color_Off}). Making a hard linked copy to base our backup off of.";
        
        cp_command="cp -rl \"$__output_path/$last_backup\" \"$backup_dest\""
        print_debug "cp command: $cp_command"
        if [ "$__test" -eq 0 ]; then

            eval $cp_command
            result="$?"
            if [ "$result" -gt 0 ]; then
                die_error "cp command failed (Return Code $result)"
            fi
        else

            print_notice ${BIRed}'TEST MODE ENABLED! CP IS NOT ACTUALLY BEING RUN!'${Color_Off}
        fi
    fi

    # Perform rsync job
    print_notice "Backing up '${BIGreen}$__input_path${Color_Off}' to '${BIGreen}$backup_dest${Color_Off}'. (Retaining ${BIRed}$__count${Color_Off} copies)";

    rsync_command="rsync -av --delete --progress $__other_rsync_args \"$__input_path/\" \"$backup_dest/\""
    print_debug "rsync command: $rsync_command"
    if [ "$__test" -eq 0 ]; then
        
        eval $rsync_command
        result="$?"
        if [ "$result" -gt 0 ]; then
            die_error "rsync operation failed (Return Code $result)"
        fi
    else
        print_notice ${BIRed}'TEST MODE ENABLED! RSYNC IS NOT ACTUALLY BEING RUN!'${Color_Off}
    fi
    
    # If selected, attempt to use fdupes to replace duplicates with hard links.
    if [ "${__dupes:-__dupes_default}" -gt 0 ]; then
        print_notice "Removing duplicates with hard links."
        fdupes_command="fdupes -rL \"$backup_dest\""
        print_debug "fdupes command: $fdupes_command"

        if [ "$__test" -eq 0 ]; then

            eval $fdupes_command
            result="$?"
            if [ "$result" -gt 0 ]; then
                die_error "fdupes operation failed (Return Code $result)"
            fi
        else
            print_notice ${BIRed}'TEST MODE ENABLED! FDUPES IS NOT ACTUALLY BEING RUN!'${Color_Off}
        fi
    fi

    # Check for old backups.
    old_backup_count="$(ls -r "$__output_path/" 2> /dev/null | egrep '^[0-9]{4}(\-[0-9]{2}){5}$' | tail -n +$((1+$__count)) | wc -l)"
    if [ "$old_backup_count" -gt 0 ]; then
        # Old backups existed to be found.
        if [ "$old_backup_count" -gt 0 ]; then
            plural="s"
        fi
        print_notice "Stripping out ${BIRed}$old_backup_count${Color_Off} old backup$plural."
        unset plural

        # Strip out old backups.
        for i in $(ls -r $__output_path/ 2> /dev/null | egrep '^[0-9]{4}(\-[0-9]{2}){5}$' | tail -n +$((1+$__count))); do
            print_notice "Removing old backup: '${BIGreen}$__output_path/$i${Color_Off}'";
            
            rm_command="rm -rf \"$__output_path/$i\""
            print_debug "rm command: $rm_command"
            if [ "$__test" -eq 0 ]; then
                eval $rm_command
                result=$?
                if [ "$result" -gt 0 ]; then
                    die_error "rm command failed (Return Code $result)"
                fi
            else
                print_notice ${BIRed}'TEST MODE ENABLED! RM IS NOT ACTUALLY BEING RUN!'${Color_Off}
            fi
        done
    else
        print_notice "No old backups to remove.";
    fi
}

backup_directory
