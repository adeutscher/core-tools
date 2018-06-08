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

  # The optional second argument to this function specifies the format mode.
  # Mode and format examples:
  # 0: 3 hours, 2 minutes, and 1 second (DEFAULT)
  # 1: 3 hours, 2 minutes, 1 second
  # 2: 3h 2m 1s

  local __num=$1
  local __c=0
  local __i=0

  if [ "${2:-0}" -eq 2 ]; then
    # Each "module" should be the unit and the number of that unit until the next phrasing.
    local __modules=(s:60 m:60 h:24 d:7 w:52 y:100 c:100)
  else
    # Each "module" should be a pairing of a name (in plural form),
    #  the number of that unit until the next phrasing,
    #  and (optionally) the phrasing of a single unit (in case lopping an 's' off of the end won't cut it)
    local __modules=(seconds:60 minutes:60 hours:24 days:7 weeks:52 years:100 centuries:100:century)
  fi

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
    # Splitting logic for compressed version (mode 2) and
    #   other phrasings requires much less tangled code.
    if [ "${2:-0}" -eq 2 ]; then
      # Short, compressed, and space-efficient version.

      printf "${__times[$__i]}$(cut -d':' -f1 <<< "${__modules[$__i]}")"

      if (( $__i )); then
        printf " "
      fi
    else
      # Long version

      # Cycling through used units in reverse.
      if [ "${2:-0}" -eq 0 ] && (( ! $__i )) && [ "$__c" -gt 1 ]; then
        printf "and "
      fi

      # Handle plural
      if [ "${__times[$__i]}" -eq 1 ]; then
        # Attempt special singluar unit.
        local __s="$(cut -d':' -f3 <<< "${__modules[$__i]}")"
        if [ -n "$__s" ]; then
          # Singular unit had content.
          printf "${__times[$__i]} $__s"
        else
          # Lop the 's' off of unit plural for singular.
          printf "${__times[$__i]} $(cut -d':' -f1 <<< "${__modules[$__i]}" | sed 's/s$//')"
        fi
      else
        # Standard plural.
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
    fi

    local __i=$(($__i-1))
  done
}

timer(){
  local _s="$(date +%s)"
  while (( 1 )); do
    printf "\33[2K\r%s elapsed" "$(__translate_seconds "$(($(date +%s)-${_s}))" 1)"
    local _c=$((${_c:-0}+1))
    sleep 0.5
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
# Snip trailing spaces
alias ssed='sed -r "s/\s+$//g"'

# Xargs Aliases
alias xargs-0="xargs -0"

if __is_unix; then

    # The below two aliases will not work under Windows via MobaXterm.
    alias xargs-n="xargs -d '\n'"
    alias xargs-i="xargs -I{}"

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

countdown-to(){
  local _t="${1}"
  if [ -z "${_t}" ]; then
    error "No time specified."
    return 1
  fi
  local _ds="$(date +%s)"
  local _ts="$(date -d "${_t}" +%s)"

  # If output is empty, then date raised a stink in stderr to provide context.
  [ -n "${_ts}" ] || return 1

  local _th="$(date -d "${_t}")"

  if [ "${_ds}" -gt "${_ts}" ]; then
    error "$(printf "Requested date is ${Colour_Bold}%s${Colour_Off} in the past: ${Colour_Bold}%s${Colour_Off}" "$(__translate_seconds "$((${_ds}-${_ts}))")" "$(date -d "${_t}")")"
    return 1
  fi
  notice "$(printf "Counting down to time: ${Colour_Bold}%s${Colour_Off}" "${_th}")"
  countdown-seconds "$((${_ts}-${_ds}))"
}

countdown-minutes(){
  # Count down minutes remaining.
  countdown-seconds $((60*${1:-0}))
}

countdown-hours(){
  # Count down hours remaining.
  countdown-seconds $((60*60*${1:-0}))
}

countdown-days(){
  # Count down days remaining.
  countdown-seconds $((24*60*60*${1:-0}))
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
