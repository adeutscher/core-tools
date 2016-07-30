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

# OS-specific aliases

if ! __is_unix; then
    # Timeout on MobaXterm requires a -t switch.
    # This alias will make it more like a Linux distro.
    alias timeout="timeout -t"
fi

if __is_mac; then
    alias __pgrep="grep -qE"
else
    alias __pgrep="grep -qP"
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
__add_to_path(){
    if !  __pgrep -m1 "(^|:)$1($|:)" <<< "$PATH"; then
        PATH=$1:$PATH
        return 0
    fi
    return 1
}

__add_to_path_if_dir(){
    if [ -n "$1" ] && [ -d "$1" ]; then
        __add_to_path "$1"
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
