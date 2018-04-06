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
##   Time Functions   ##
########################

# Lazy alias
# epochtime: report number of seconds since the Epoch
# AKA: Unix Timestamp
alias epochtime='date +%s'
alias unixtime=epochtime

__translate_seconds(){
  # Translate a time given in seconds (e.g. the difference between two Unix timestamps) to more human-friendly units.

  # So far, I've mostly used this in hook functions to give me a display of how long the parent process has lasted.
  # Example:
  #  local __ctime=$(date +%s)
  #  local __stime=$(stat -c%X /proc/$PPID)
  #  local __time_output="$(__translate_seconds "$(($__ctime - $__stime))")"

  local __num=$1
  local __c=0
  local __i=0

  # Each "module" should be a pairing of a name (in plural form),
  #  the number of that unit until the next phrasing,
  #  and (optionally) the phrasing of a single unit (in case lopping an 's' off of the end won't cut it)
  local __modules=(seconds:60 minutes:60 hours:24 days:7 weeks:52 years:100 centuries:100:century)

  local __modules_count="$(wc -w <<< "${__modules[*]}")"
  while [ "$__i" -lt "$__modules_count" ]; do
    # Cycling through to get values for each unit.
    local __value="$(cut -d':' -f2 <<< "${__modules[$__i]}")"

    local __mod_value="$(($__num % $__value))"
    local __num="$((__num / $__value))"

    local __times[$__i]="$__mod_value"
    local __c=$(($__c+1))
    local __i=$(($__i+1))
    if (( ! $__num )); then
      break
    fi
  done
  unset __module

  local __i=$(($__c-1))

  while [ "$__i" -ge "0" ]; do
    # Cycling through used units in reverse.
    if [ -z "${2}" ] && (( ! $__i )) && [ "$__c" -gt 1 ]; then
      printf "and "
    fi

    if [ "${__times[$__i]}" -eq 1 ]; then
      local __s="$(cut -d':' -f3 <<< "${__modules[$__i]}")"
      if [ -n "$__s" ]; then
        printf "${__times[$__i]} $__s"
      else
        printf "${__times[$__i]} $(cut -d':' -f1 <<< "${__modules[$__i]}" | sed 's/s$//')"
      fi
    else
      printf "${__times[$__i]} $(cut -d':' -f1 <<< "${__modules[$__i]}")"
    fi

    if (( $__i )); then
      if [ "$__c" -gt 2 ]; then
        # Prepare for the next unit.
        # If you aren't a fan of the Oxford comma, then you have some adjusting to do.
        printf ", "
      else
        printf " "
      fi
    fi

    local __i=$(($__i-1))
  done
}

timer(){
  while (( 1 )); do
    printf "\r%s elapsed" " " "$(__translate_seconds "${_c:-0}" 1)"
    local _c=$((${_c:-0}+1))
    sleep 1
  done
}

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

countdown-seconds(){

  # If not an integer, return
  egrep -q "^[0-9]{1,}$" <<< "${1}" || return 1

  local _c="${1}"
  local _max="$(expr length "$(__translate_seconds "${_c}" 1) remaining")"
  until (( ! "${_c:-0}" )); do
    local _c="$((${_c}-1))"
    printf "\r%-0${_max}s\r%s remaining" " " "$(__translate_seconds "${_c}" 1)"
    sleep 1
  done
  printf " \r%-0${_max}s\n" "$(__translate_seconds "${1}" 1) elapsed"
}

countdown-minutes(){
  # Count down minutes remaining.
  countdown-seconds $((60*${1}))
}

countdown-hours(){
  # Count down hours remaining.
  countdown-seconds $((60*60*${1}))
}

countdown-days(){
  # Count down days remaining.
  countdown-seconds $((24*60*60*${1}))
}

sleep-minutes(){
  # If not an integer, return
  egrep -q "^[0-9]{1,}$" <<< "$1" || return 1
  sleep $((60*$1))
}

sleep-hours(){
  # If not an integer, return
  egrep -q "^[0-9]{1,}$" <<< "$1" || return 1
  sleep $((60*60*$1))
}

sleep-days(){
  # If not an integer, return
  egrep -q "^[0-9]{1,}$" <<< "$1" || return 1
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
