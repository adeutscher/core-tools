########################
 ######################
 # Generak Settings ##
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

# Tmux
if qtype tmux; then
	alias new='tmux new -s'
	alias list='tmux list-sessions'
	alias resume='tmux attach -t'
	# Lazy function to combine resuming and creating tmux sessions.
	mux (){
	  if [ -z "$1" ]; then
		local sessions="$(tmux list-sessions 2> /dev/null)"
		if [ "$(expr length "$sessions")" -gt 1 ]; then
		    error "No session name provided. The following sessions are available:"
		    printf "%s\n" "$sessions"
		else
		    error "No session name provided. No sessions are currently available."
		fi
		return 1
	  fi

          if [ -n "$TMUX" ]; then
              error "$(printf "sessions should be nested with care, unset ${Colour_BIPurple}\$TMUX${Colour_Off} to force" )"
              return 2
          fi

	  # If a tmux session cannot be created under this name,
	  #   then one must already exist.
	  if [ -f /etc/redhat-release ] && [[ "$(tmux -V)" == "tmux 1.6" ]]; then
        # Tmux 1.6 on CentOS 6 is strange with how it works with redirection to stderr
        # See also: https://bugzilla.redhat.com/show_bug.cgi?id=1102087
        # I would prefer to redirect the duplicate session error from trying a new session to stderr,
        #     but if I do so with this version tmux will hang. Lesser of two evils...
        tmux new -s "$1" || tmux attach -t "$1"
    else
        # Use preferred redirection to stderr
        tmux new -s "$1" 2> /dev/null || tmux attach -t "$1"
    fi
	}
fi

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
    if qtype youtube-dl && qtype avconv; then
        # If avconv is not available,
        #     then assume that we aren't able to convert our downloaded file(s) to mp3.
        alias youtube='youtube-dl --audio-quality 0 --audio-format mp3 -x'
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
