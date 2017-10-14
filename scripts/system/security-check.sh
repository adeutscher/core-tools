#!/bin/bash

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
  __error_count=$((${__error_count:-0}+1))
}

# A more strongly phrased error (error also implies more of a misconfiguration).
alert(){
  printf "$RED"'ALERT'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __alert_count=$((${__alert_count:-0}+1))
}

notice(){
  printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

success(){
  printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __warning_count=$((${__warning:-0}+1))
}

# Script functions

check_key_logins(){

    # Look for users that have set up key-based logins.
    # Inspired by http://wiki.metawerx.net/wiki/LBSA

    local __key_file="$(grep -Pm1 "^\s*[^#]*\s*AuthorizedKeysFile" "/etc/ssh/sshd_config" 2> /dev/null | awk -F' ' '{ print $2}')"
    if [ -z "$__key_file" ]; then
        # If we cannot read SSH config for whatever reason, then assume default.
        local __key_file=".ssh/authorized_keys"
    fi
    notice "$(printf "Checking for users with SSH keyfiles at ${GREEN}~/%s${NC}" "$__key_file")."

    while read __line; do
        local __user="$(cut -d':' -f1 <<< "$__line")"
        local __home="$(cut -d':' -f6 <<< "$__line")"
        local __uid="$(cut -d':' -f3 <<< "$__line")"

        if grep -q "^\/home" <<< "$__home"; then
            local __in_home=1
            local __home_total=$((${__total_home:-0}+1))
        else
            local __in_home=0
            local __non_home_total=$((${__non_home_total:-0}+1))
        fi

        # Super-lazy concatenation convenience.
        local __user_key_file="$__home/$__key_file"

        if [ ! -d "$__home" ]; then
           # Home directory does not exist. Not really a problem for this script, do not raise any notice.
           # A chance of a false negative without a warning if even the directory
           # containing home is hidden behind some wacky permissions, but that
           # is very much an edge case.
           continue
        elif [ ! -r "$__home" ] || ( [ -d "$(dirname "$__user_key_file")" ] && [ ! -r "$(dirname "$__user_key_file")" ] ); then
            # We cannot read the home directory or an existing ~/.ssh directory
            if (( $__in_home )); then
                local __home_cannot_read=$((${__home_cannot_read:-0}+1))
            else
                local __non_home_cannot_read=$((${__non_home_cannot_read:-0}+1))
            fi

            if (( "$EUID" )); then
                # If we are not root, then it's expected that we would not be able to read the directories for some users.
                notice "$(printf "Cannot confirm SSH authorized keys file for ${BOLD}%s${NC} (probably because we aren't ${RED}%s${NC}): ${GREEN}%s${NC}" "$__user" "root" "$__user_key_file")"
            else
                # If we ARE root, then it's a bigger problem if we cannot read the home directory for a user.
                error "$(printf "Cannot confirm SSH authorized keys file for ${BOLD}%s${NC}: ${GREEN}%s${NC}" "$__user" "$__user_key_file")"
            fi
            continue
        fi
        if [ -f "$__user_key_file" ]; then
            if (( $__in_home )); then
                # /home/ user. These users are expected to possibly have a SSH key set up, so this just gets a notice.
                notice "$(printf "SSH key file exists for user ${BOLD}%s${NC}): ${GREEN}%s${NC}" "$__user" "$__user_key_file")"
                local __home_key_file=$((${__home_key_file:-0}+1))
            else
                alert "$(printf "SSH key file exists for non-/home/ user ${BOLD}%s${NC}): ${GREEN}%s${NC}" "$__user" "$__user_key_file")"
                local __non_home_key_file=$((${__non_home_key_file:-0}+1))
            fi
            if (( $EUID )) && [ -r "$__user_key_file" ] && [ "$EUID" -ne "$__uid" ]; then
                warning "$(printf "Non-root user ${BOLD}%s${NC} is able to read SSH authorized key file for user ${BOLD}%s${NC}" "$USER" "$__user" "$__user_key_file")"
            fi
        fi
    done <<< "$(sort -t":" -k 3n,3n "/etc/passwd")"

    # Summarize findings.
    if (( $__home_total )); then
        if (( $__home_cannot_read )); then
            # Some home-based dirs could not be read.
            local __c=error
            if (( $EUID )); then
                local __c=notice
            fi
            $__c "$(printf "Found SSH authorized keys installed for ${BOLD}%d${NC}/${BOLD}%s${NC} ${GREEN}/home${NC}-based users (${BOLD}%s${NC} could not be confirmed)." "${__home_key_file:-0}" "${__home_total:-0}" "${__home_cannot_read}")"
        elif (( "${__home_key_file:-0}" )); then
            notice "$(printf "Found SSH authorized keys installed for ${BOLD}%d${NC}/${BOLD}%s${NC} ${GREEN}/home${NC}-based users." "${__home_key_file:-0}" "${__home_total:-0}")"
        fi
    else
        notice "$(printf "Found absolutely no ${GREEN}/home${NC}-based users.")"
    fi

    if (( $__non_home_total )); then
        if (( $__non_home_cannot_read )); then
            # Some non-home-based dirs could not be read.
            local __c=error
            if (( $EUID )); then
                if (( "${__non_home_key_file:-0}" )); then
                    local __c=warning
                else
                    local __c=notice
                fi
            fi
            $__c "$(printf "Found SSH authorized keys installed for ${BOLD}%d${NC}/${BOLD}%s${NC} non-${GREEN}/home${NC}-based users (${BOLD}%s${NC} could not be confirmed)." "${__non_home_key_file:-0}" "${__non_home_total:-0}" "${__non_home_cannot_read:-0}")"
        elif (( "${__non_home_key_file:-0}" )); then
            warning "$(printf "Found SSH authorized keys installed for ${BOLD}%d${NC}/${BOLD}%s${NC} non-${GREEN}/home${NC}-based users." "${__non_home_key_file:-0}" "${__non_home_total:-0}")"
        fi
    else
        # I would be supremely worried if a normal system had zero non-/home users
        error "$(printf "Found absolutely no non-${GREEN}/home${NC}-based users.")"
    fi

    notice "Finished checking for users with SSH keyfiles."
}

check_shellshock(){
    # Confirm that the server's BASH version is not vulnerable to ShellShock.
    if env x='() { :;}; echo vulnerable' bash -c "echo Testing" | grep -q "vulnerable"; then
        alert "$(printf "Server is vunerable to ${BOLD}%s${NC} (${BOLD}%s${NC})." "ShellShock" "CVE-2014-6271")"
    else
        success "$(printf "Server is not vunerable to ${BOLD}%s${NC} (${BOLD}%s${NC})." "ShellShock" "CVE-2014-6271")"
    fi
}

check_key_logins
check_shellshock
