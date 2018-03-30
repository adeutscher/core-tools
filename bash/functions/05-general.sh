########################
 ######################
 # General Settings ##
 ######################
########################
# General functions and variables.
# Can be summed up as "anything that I don't consider large enough to get its own file".

export EDITOR=vi
export SVN_EDITOR=vi

# History Settings
export HISTSIZE=20000
export HISTTIMEFORMAT="%Y-%m-%d %T "

# KVM URI
export LIBVIRT_DEFAULT_URI='qemu:///system'

# Legacy alias - original name of reload-tools
# Keeping it in because there is no competing function in tab-complete yet.
alias reload="reload-tools"

# Alias for our most-used rsync switches.
alias rsync="rsync -av --progress"

########################
# More Misc. Functions #
########################

# epochtime: report number of seconds since the Epoch
# AKA: Unix Timestamp
alias epochtime='date +%s'
alias unixtime=epochtime

##########################
# Parsing functions #
##########################

# Show only lines that do not contain just whitespace or are commented out by '#' symbols.
alias grep-active='grep -v -e "^$" -e"^ *#"'

# URL encoding/decoding (source: https://gist.github.com/cdown/1163649)
urlencode() {
    # urlencode <string>

    local length="${#1}"
    for (( i = 0; i < length; i++ )); do
        local c="${1:i:1}"
        case $c in
            [a-zA-Z0-9.~_-]) printf "$c" ;;
            *) printf '%s' '$c' | xxd -p -c1 |
                   while read c; do printf '%%%s' "$c"; done ;;
        esac
    done
    # Clean-up loop variable.
    unset i
}

urldecode() {
    # urldecode <string>

    local url_encoded="${1//+/ }"
    printf '%b' "${url_encoded//%/\\x}"
}

# vsed - Remove lines containing '.svn/', '.hg/', or '.git/'.
#   Meant to filter out matches in version-control system directories
alias vsed="perl -ne 'print unless /(^|\/)((\.svn|\.hg|\.git)\/)/'"
# Strip out BASH colours
alias csed='sed -r "s/\x1B\[([0-9]{1,2}(;[0-9]{1,2})?)?[m|K]//g"'

# Xargs Aliases
alias xargs-0="xargs -0"

if __is_unix; then

    # The below two aliases will not work under Windows via MobaXterm.
    alias xargs-n="xargs -d '\n'"
    alias xargs-i="xargs -I{}"

    # Burn an ISO to a device in the CD drive
    alias burn='time wodim -v dev=/dev/cdrom speed=8 -eject'

    # For wine. Only make winetricks available in the prompt if wine is actually installed and the script exists.
    # I would also be very confused if wine were available on a Windows system, so placing this with in an __is_unix check.
    if qtype wine && [ -x "$toolsDir/scripts/utils/winetricks" ]; then
        alias winetricks="$toolsDir/scripts/utils/winetricks"
    fi

    # Download music from YouTube via youtube-dl
    if qtype youtube-dl; then

        alias youtube-dl='youtube-dl --no-mtime'

        if qtype avconv; then
            # If avconv is not available,
            #     then assume that we aren't able to convert our downloaded file(s) to mp3.
            alias youtube-dl-mp3='youtube-dl --audio-quality 0 --audio-format mp3 -x'
        fi
    fi

    # Conky
    # Off the top of my head, most of our functions would
    #     absolutely crash and burn under Windows via MobaXterm,
    #     so this is definitely a Linux-only thing.
    if qtype conky; then
       alias conky-command="\"$toolsDir/bash/conky/start.sh\""
       alias conky-restart="conky-command -r 2> /dev/null >&2 &"
       alias conky-start="conky-command 2> /dev/null >&2 &"
       alias conky-debug="conky-command -d"
    fi
else
    # Non-Unix environment. MobaXterm?

    # Basic LDAP functions/aliases.

    if qtype ldapsearch.exe; then
        # Tab-completion in MobaXterm hops to ldapsearch.exe.
        # Not that there's any performance difference,
        #    but for comfort making aliases that will complete to ldapsearch

        # Assuming for the moment that the commands are otherwise identical

        alias ldapcompare='ldapcompare.exe'
        alias ldapdelete='ldapdelete.exe'
        alias ldapmodify='ldapmodify.exe'
        alias ldapmodrdn='ldapmodrdn.exe'
        alias ldappasswd='ldappasswd.exe'
        alias ldapsearch='ldapsearch.exe'
        alias ldapwhoami='ldapwhoami.exe'
        alias ldapurl='ldapurl.exe'
    fi
fi

# For Passwords #
alias mkpasswd='mkpasswd -m sha-512'

########
# Super-duper-lazy sleep functions
########

sleep-minutes(){
    # Not an integer.
    if ! egrep -q "^[0-9]{1,}$" <<< "$1"; then
        return 1
    fi
    sleep $((60*$1))
}

sleep-hours(){
    # Not an integer.
    if ! egrep -q "^[0-9]{1,}$" <<< "$1"; then
        return 1
    fi
    sleep $((60*60*$1))
}

sleep-days(){
    # Not an integer.
    if ! egrep -q "^[0-9]{1,}$" <<< "$1"; then
        return 1
    fi
    sleep $((24*60*60*$1))
}

##########
# Super-duper-lazy wait functions
##########

# Wait for a specified process to be done.
# Different from the BASH built-in 'wait',
#   as the built-in will only support children of the current shell.
# The trade-off is that this function will not support returning exit codes.
# It will also not support multiple PIDs, though that may change in the future.
wait-for-pid(){
  if [ -z "$1" ]; then
    error "No PID provided."
    return 1
  fi
  if ! grep -Pq '\d*' <<< "$1" || ! [ -d "/proc/$1" ]; then
    error "$(printf "$BOLD%s$NC is not an active PID." "$1")"
    return 2
  fi

  # Loop so long as the process exists.
  # Assume that a replacement PIDs will not pop up in the meantime to replace the target.
  while [ -d "/proc/$1" ]; do
    sleep 1
  done
}

#########
# Silly #
#########

# Surviving silly aliases that were not converted to scripts.

# Silly catharsis
alias ffs='sudo'

# Only load on Ubuntu/Debian
if qtype apt-get && [ -f "/etc/debian_version" ]; then
  alias batman='sudo apt-get update'
  alias robin='sudo apt-get upgrade'
fi

# Silly telnet movies.
if qtype telnet; then
  alias telnet-nyan="telnet nyancat.dakko.us; reset"
  alias telnet-star-wars="telnet towel.blinkenlights.nl; reset"
fi

##################
# Temporary Data #
##################

# Ensure that a temporary directory exists for storing data in /tmp, then set permissions
# tmpfs is faster than reading off of an HDD or an SSD.

export toolsCache=/tmp/$USER

mkdir "$toolsCache" 2> /dev/null
chmod 700 "$toolsCache" 2> /dev/null
