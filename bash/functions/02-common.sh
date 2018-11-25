########################
 ######################
 ## Common Functions ##
 ######################
########################

# Functions that may be used by other functions.

################
# OS Functions #
################

__is_unix(){
    # Using the WINDIR environment variable as a lazy litmus test for
    #   whether or not we're in a Windows machine using MobaXterm.

    if [ -n "$WINDIR" ]; then
        return 1
    else
        return 0
    fi
}

__is_mac(){
    uname | grep -q "^Darwin$"
    return $?
}

__is_debian(){
    [ -f "/etc/debian_version" ] && return 0
    return 1
}

__is_rhel(){
    [ -f "/etc/redhat-release" ] && return 0
    return 1
}

# OS-specific aliases

if ! __is_unix; then
    # Timeout on MobaXterm requires a -t switch.
    # This alias will make it more like a Linux distro.
    alias timeout="timeout -t"
fi

###########################
# Function Name Functions #
###########################

# Some silly functions for getting function names.
# They are all just an offset of the FUNCNAME variable,
#   so they are all just for my convenience when reading my function code.

# Hierarchy reminder:
#    [0] __function_parent (or equivalent)
#    [1] The function that seeks its parent.
#    [2] Parent of the function that called __function_parent
#    [3] Parent of parent
#    [4] Grand-parent of parent

__function_parent(){
    echo "${FUNCNAME[2]}"
}

__function_grandparent(){
    echo "${FUNCNAME[3]}"
}

__function_greatgrandparent(){
    echo "${FUNCNAME[4]}"
}

#####################
# Message Functions #
#####################

__message_get_location(){
    if [ -n "$0" ] && grep -Pqv '^\-?bash$' <<< "$0"; then
        printf '['"$Colour_BIGreen"'%s'"$Colour_Off"']' ${0##*/}
    elif [ -n "$(__function_grandparent)" ]; then
        printf '['"$Colour_BIBlue"'%s'"$Colour_Off"']' "$(__function_grandparent)"
    fi
}

error(){
    printf "$Colour_BIRed"'Error'"$Colour_Off"'%s: %s\n' "$(__message_get_location)" "$@"
}

notice(){
    printf "$Colour_BIBlue"'Notice'"$Colour_Off"'%s: %s\n' "$(__message_get_location)" "$@"
}

success(){
    printf "$Colour_BIGreen"'Success'"$Colour_Off"'%s: %s\n' "$(__message_get_location)" "$@"
}

warning(){
    printf "$Colour_BIYellow"'Warning'"$Colour_Off"'%s: %s\n' "$(__message_get_location)" "$@"
}


#####################
# Program Functions #
#####################

qtype(){
   # The help text on the type command's 'silent' switch has some wording that throws me for a loop, so making this instead.
   # Super-lazy.
   if [ -n "$1" ]; then
       type $@ 2> /dev/null >&2
       return $?
   fi
   return 1
}

# Internal function to add a directory to the path
# Assume that the directory exists and is valid.
# The purpose of this function is to cut down on redundant clutter to the PATH variable,
#     but there is still no penalty for having a a non-existant directory.
# Add anything to second argument to make the function for
__add_to_path(){
  [ -z "${1}" ] && return
  if grep -qP -m1 "(^|:)$1($|:)" <<< "$PATH"; then
    [ -z "${2}" ] && return 0
    # If a second argument was given, strip before prepending.
    # Not done by default because it significantly adds to reload time
    #   (.+0.1s on a machine with a fair number of modules).
    export PATH="$(sed -r -e "s|^${1}:||g" -e "s|:${1}$||g" -e "s|:${1}:|:|g" <<< "${PATH}")"
  fi
  export PATH=$1:${PATH}
}

__add_to_path_if_dir(){
    if [ -n "$1" ] && [ -d "$1" ]; then
        __add_to_path "$1" "${2}"
        return 0
    fi
    return 1
}

# Library path version of __add_to_path.

__add_to_lib(){
  [ -z "${1}" ] && return
  if grep -qP -m1 "(^|:)$1($|:)" <<< "$LD_LIBRARY_PATH"; then
    [ -z "${2}" ] && return 0
    # If a second argument was given, strip before prepending.
    # Not done by default because it significantly adds to reload time
    #   (.+0.1s on a machine with a fair number of modules).
    export LD_LIBRARY_PATH="$(sed -r -e "s|^${1}:||g" -e "s|:${1}$||g" -e "s|:${1}:|:|g" <<< "${PATH}")"
  fi
  export LD_LIBRARY_PATH=$1:${LD_LIBRARY_PATH}
}

__add_to_lib_if_dir(){
    if [ -n "$1" ] && [ -d "$1" ]; then
        __add_to_lib "$1" "${2}"
        return 0
    fi
    return 1
}

__strlen(){
    if __is_mac; then
        awk '{ print length }' <<< "$1"
    else
        expr length "$1"
    fi
}

####################
#  Tmux Functions  #
####################

# Load session-specific variables if we are within a TMUX instance.
# See comments in mux function for the reasoning behind this.
# If for some reason TMUX_PANE is set but tmux is not installed
#  (recently uninstalled?), then the info grab will fall flat
#  on its face without fanfare.
if [ -n "${TMUX_PANE}" ]; then
  export TMUX_SESSION="$(tmux list-panes -a -F "#{pane_id} #{session_name}" 2> /dev/null | grep -wm1 "^${TMUX_PANE}" | cut -d' ' -f2)"
  if [ -f "/tmp/${USER}/tmux/env.${TMUX_SESSION}" ]; then
    . "/tmp/${USER}/tmux/env.${TMUX_SESSION}"
  fi
fi
