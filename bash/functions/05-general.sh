########################
 ######################
 # General Settings ##
 ######################
########################
# General functions and variables.

# PATH Variable Additions

__add_to_path "$toolsDir/bin" 1
__add_to_path "$toolsDir/bin/hosts/$HOSTNAME"
__add_to_path "$HOME/.local/bin" # TODO: This may be redundant. Double-check on more distributions.

# Environment Variables
###


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

# Lazy alias to eliminate buffer
alias antibuf="stdbuf -oL"

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

  # Units with a value of zero are left out (e.g. "1 hour and 5 seconds").
  # A duration of zero is displayed as "0 seconds" ("0s" in mode 2).
  # A year is treated as 365 days.

  local __num="${1}"
  local __mode="${2:-0}"
  local __units __unit __name __rest __size __singular __count __i
  local __parts=()

  # Only accept non-negative integers.
  [[ "${__num}" =~ ^[0-9]+$ ]] || return 1
  __num=$((10#${__num}))

  if [ "${__mode}" = 2 ]; then
    # Each unit should be its abbreviation and its length in seconds, from largest to smallest.
    __units=(c:3153600000 y:31536000 w:604800 d:86400 h:3600 m:60 s:1)
  else
    # Each unit should be a pairing of a name (in plural form),
    #  its length in seconds (from largest to smallest),
    #  and (optionally) the phrasing of a single unit (in case lopping an 's' off of the end won't cut it)
    __units=(centuries:3153600000:century years:31536000 weeks:604800 days:86400 hours:3600 minutes:60 seconds:1)
  fi

  for __unit in "${__units[@]}"; do
    __name="${__unit%%:*}"
    __rest="${__unit#*:}"
    __size="${__rest%%:*}"

    __count=$((__num / __size))
    __num=$((__num % __size))

    # Skip units with nothing in them, unless the whole duration is zero.
    if (( ! __count )) && { (( __size > 1 )) || (( ${#__parts[@]} )); }; then
      continue
    fi

    if [ "${__mode}" = 2 ]; then
      # Short, compressed, and space-efficient version.
      __parts+=("${__count}${__name}")
    elif [ "${__count}" -eq 1 ]; then
      # Attempt special singular unit, otherwise lop the 's' off of unit plural for singular.
      __singular=""
      [[ "${__rest}" == *:* ]] && __singular="${__rest#*:}"
      __parts+=("${__count} ${__singular:-${__name%s}}")
    else
      # Standard plural.
      __parts+=("${__count} ${__name}")
    fi
  done

  for (( __i = 0; __i < ${#__parts[@]}; __i++ )); do
    if (( __i )); then
      # Prepare for the next unit.
      if [ "${__mode}" = 2 ]; then
        printf " "
      elif [ "${__mode}" = 0 ] && (( __i == ${#__parts[@]} - 1 )); then
        # If you aren't a fan of the Oxford comma, then take out this line.
        (( ${#__parts[@]} > 2 )) && printf ","
        printf " and "
      else
        printf ", "
      fi
    fi
    printf "%s" "${__parts[__i]}"
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
alias csed='sed -r -e "s/\x1B\[(([0-9]{1,2})?(;)?([0-9]{1,2})?)??[mKHfJ]//"'
# Snip trailing spaces
alias ssed='sed -r -e "s/\s+$//g"'

# Xargs Aliases
alias xargs-0="xargs -0"

if __is_unix; then

    # The below two aliases will not work under Windows via MobaXterm.
    alias xargs-n="xargs -d '\n'"
    alias xargs-i="xargs -I{}"

    # Download music from YouTube via youtube-dl
    if qtype yt-dlp; then

        alias youtube-dl='yt-dlp --no-mtime'

        if qtype ffmpeg; then
            # If ffmpeg is not available,
            #     then assume that we aren't able to convert our downloaded file(s) to mp3.
            alias youtube-dl-mp3='yt-dlp --audio-quality 0 --audio-format mp3 -x --prefer-ffmpeg'
        fi
    fi

    # Conky
    # Off the top of my head, most of our functions would
    #     absolutely crash and burn under Windows via MobaXterm,
    #     so this is definitely a Linux-only thing.
    if qtype conky; then
       alias conky-command="\"$toolsDir/bash/conky/start.sh\""
       alias conky-restart="conky-command -r 2> /dev/null >&2"
       alias conky-start="conky-command 2> /dev/null >&2"
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
