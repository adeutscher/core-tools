# Define basic colours.
colour_green=33CC33
colour_light_blue=99CCFF
colour_orange=FFA500
colour_red=D00000

# Assign colours to specific roles.
colour_local_path=$colour_green
colour_kvm=$colour_orange
colour_network=$colour_light_blue
colour_network_address=$colour_green
# Default header colour
colour_header=$colour_orange

colour_good=$colour_green
colour_warning=$colour_orange
colour_alert=$colour_red

# The directory specified by $reportRoot contains periodic scripts run by periodic-reports.sh.
# Path is relative to conky directory.
reportRoot=scripts/report-scripts

# Some scripts may need to use temporary files. Place them here.
tempRoot=/tmp/$USER/conky

# Some scripts need to reach outside of conky's directory.
# Defining the relative path to the root of the tools directory from the conky/ directory.

if [[ ! "$(pwd)" =~ ^$HOME ]] && [ -f "$tempRoot/tools-dir" ]; then
    # Script is running out of a tmpfs
    #    (not running out of home, and a temp root exists as probably created by start.sh)
    toolsRoot="$(cat "$tempRoot/tools-dir")"
else
    # Script is running out of normal location in tools.
    toolsRoot=../..
fi

# If we go to 38 characters or higher, conky will start to expand widthwise.
characterWidth=37
# Putting two phrasings in to cover an edge case in networking that I don't fully understand at the moment.
characterWidthLimit=$(($characterWidth+1))

# Also defining functions here in case they need to be used in multiple scripts. #

# Colour network addresses
colour_network_address(){
    # If the argument that we're given begins with a number,
    #   then assume that it is a valid IP address.
    # If not, then assume that it's some sort of expression of a "No Address" message.
    if [[ "${1}" =~ ^[0-9] ]]; then
        # IP Address
        printf "\${color #${colour_network_address}}${1}\$color"
    else
        # "No Address"
        printf "\${color #${colour_warning}}${1}\$color"
    fi
}
# Method for colouring network interfaces.
colour_interface(){
    if [ -n "${1}" ]; then

		if [ -d "/sys/class/net/$1/bridge" ]; then
            # Bridges get to be special.
            iface_colour=$colour_local_path
        else
            case "${1}" in
            tun*|tap*|bnep*|usb*)
                # Temporary interfaces provided by software (e.g. OpenVPN, phone tethering)
                iface_colour=$colour_red
                ;;
            vnet*)
                # KVM guests are also special.
                iface_colour=$colour_kvm
                ;;
            *)
                # Fall back to the generic networking colour for everything else.
                iface_colour=$colour_network
                ;;
            esac
        fi
        printf "\${color #${iface_colour}}${1}\$color\n"
    fi
}

# Method for colouring percentage numbers (Higher being good).
# Originally made for battery display.
colour_percent_desc(){
    # > 31 - Good
    # 30-11 - Warning
    # 10-0 - Alert

    if [ "${1}" -le 10 ]; then
        # Alert
        printf "\${color #${colour_alert}}${1}\$color\n"        
    elif [ "${1}" -le 30 ]; then
        # Warning
        printf "\${color #${colour_warning}}${1}\$color\n"    
    else
        # All Clear
        printf "\${color #${colour_good}}${1}\$color\n"
    fi
}

qtype(){
   # The type command's 'silent' switch has some wording that throws me for a loop, so making this instead.
   # Super-lazy.
   if [ -n "$1" ]; then
       type $@ 2> /dev/null >&2
       return $?
   fi
   return 1
}

shorten_string(){
  # If the first argument is a string that is longer than the threshold, then print a shortened string and an elipsis.

  # Note: The ellipsis character is counted by the expr command as 3 characters (unicode ahoy),
  #     so the option for a custom ellipsis is gone for now.
  local ellipsis=…
  local ellipsisLength=1

  # Arguments
  local threshold=${2:-30}
  local string=$1
  
  # Note: Hard-coded numbers are to account for end-of-string characters in the string variabes.
  if [ "$(expr length "$string")" -le "$threshold" ]; then
    printf "%s" "$string"
  else
    printf "%s%s" "$(sed -r 's/\s+$//' <<< "${string:0:$(($threshold-$ellipsisLength))}")" "$ellipsis"
  fi
}

# If the timeout command is available, then use it. Otherwise, run the command anyways.
if qtype timeout; then
    # This was originally added for df, which has
    #   a run time of near-instant (as all commands in conky scripts should be)
    #   or near-infinity (if it was trying to poll a network file system).
    
    # A .25s timeout should be more than enough for normal operations.
    timeout="timeout .75"
fi
