#################
# SSH Functions #
#################

# Restrict in the super-duper-off-chance that we're on a machine with no SSH client.
if qtype ssh; then

  # We do not want a GUI prompt for credentials when doing something like pushing with git.
  unset GIT_ASKPASS SSH_ASKPASS

  # Standard switches for SSH via alias:
  alias ssh='ssh -2'
  # SSH with X forwarding.
  if [ -n "$DISPLAY" ]; then
      #   Should only happen if the current machine
      #   also has a display to forward through.
      alias sshx='\ssh -2 -Y'
  fi

  ssh6-local(){
    # Attempt to connect to a host via SSH over IPv6 by calculating its link-local address from its MAC address.
     local ip6addr=$(ip6linklocal "$1")
    if [ -z "$ip6addr" ]; then
      error "$(printf "Unable to translate MAC address: ${Colour_Bold}%s${Colour_Off}" "$1")"
      return 1
    fi
    shift
    local __if=$1
    shift
    if ! ip a s "$__if" | grep -w inet6 | grep -w link; then
      error "$(printf "Interface not found or no link-local address: ${Colour_Bold}%s${Colour_Off}" "$__if")"
      return 1
    fi
    ssh6 "$ip6addr%$__if" $@
  }

fi # end SSH client check
