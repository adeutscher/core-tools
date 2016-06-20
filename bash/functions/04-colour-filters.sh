
# General functions for colouring output from a function.
# Note: You can only use these one at a time, since only the outermost one will be considered to possibly have an interactive terminal.

# Colour network addresses bold and green
__colour_filter_network(){
    trap '' INT
    local __esc=$(printf '\033')
    if [ -t 1 ]; then
        sed -r -e "s/((1?[0-9][0-9]?|2[0-4][0-9]|25[0-5])\.){3}(1?[0-9][0-9]?|2[0-4][0-9]|25[0-5])((\/[0-9]{1,2})|(:[0-9]*)){,1}/${__esc}${Colour_BIGreen:4:6}&${__esc}${Colour_Off:4:3}/g"
    else
        cat
    fi
}

