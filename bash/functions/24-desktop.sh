#######################################
# Functions for a desktop environment #
#######################################

# Presence of 'mate-panel' command shall be the litmus test for a MATE environment being installed on this machine.
if qtype mate-panel; then
    # Quick and dirty function to get the background from a MATE environment.
    # TODO: Make a more robust version that covers as many desktop environments as possible.
    get-mate-background(){
       dconf read /org/mate/desktop/background/picture-filename 2> /dev/null
    }

    # The CLI command for Dropbox in a MATE desktop environment is 'caja-dropbox'.
    # This alias should keep things more intuitive.
    if qtype caja-dropbox; then
        alias dropbox='caja-dropbox'
    fi
fi


