
######################
 ####################
 # Colour Functions #
 ####################
######################
# Define prompt colours here.

colour-on(){

    # Colours courtesy of ArchWiki
    #    https://wiki.archlinux.org/index.php/Color_Bash_Prompt#List_of_colors_for_prompt_and_Bash
    # Reset
    Colour_Off='\033[0m'       # Text Reset

    # Bold/Underline/etc are of course not colours, but it keeps the naming scheme consistent.
    Colour_Bold='\033[1m'
    Colour_Reverse='\033[7m'
    Colour_Underline='\033[4m'

    # Regular Colors
    Colour_Black='\033[0;30m'        # Black
    Colour_Red='\033[0;31m'          # Red
    Colour_Green='\033[0;32m'        # Green
    Colour_Yellow='\033[0;33m'       # Yellow
    Colour_Blue='\033[0;34m'         # Blue
    Colour_Purple='\033[0;35m'       # Purple
    Colour_Cyan='\033[0;36m'         # Cyan
    Colour_White='\033[0;37m'        # White

    # Bold
    Colour_BBlack='\033[1;30m'       # Black
    Colour_BRed='\033[1;31m'         # Red
    Colour_BGreen='\033[1;32m'       # Green
    Colour_BYellow='\033[1;33m'      # Yellow
    Colour_BBlue='\033[1;34m'        # Blue
    Colour_BPurple='\033[1;35m'      # Purple
    Colour_BCyan='\033[1;36m'        # Cyan
    Colour_BWhite='\033[1;37m'       # White

    # Underline
    Colour_UBlack='\033[4;30m'       # Black
    Colour_URed='\033[4;31m'         # Red
    Colour_UGreen='\033[4;32m'       # Green
    Colour_UYellow='\033[4;33m'      # Yellow
    Colour_UBlue='\033[4;34m'        # Blue
    Colour_UPurple='\033[4;35m'      # Purple
    Colour_UCyan='\033[4;36m'        # Cyan
    Colour_UWhite='\033[4;37m'       # White

    # Background
    Colour_On_Black='\033[40m'       # Black
    Colour_On_Red='\033[41m'         # Red
    Colour_On_Green='\033[42m'       # Green
    Colour_On_Yellow='\033[43m'      # Yellow
    Colour_On_Blue='\033[44m'        # Blue
    Colour_On_Purple='\033[45m'      # Purple
    Colour_On_Cyan='\033[46m'        # Cyan
    Colour_On_White='\033[47m'       # White

    # High Intensity
    Colour_IBlack='\033[0;90m'       # Black
    Colour_IRed='\033[0;91m'         # Red
    Colour_IGreen='\033[0;92m'       # Green
    Colour_IYellow='\033[0;93m'      # Yellow
    Colour_IBlue='\033[0;94m'        # Blue
    Colour_IPurple='\033[0;95m'      # Purple
    Colour_ICyan='\033[0;96m'        # Cyan
    Colour_IWhite='\033[0;97m'       # White

    # Bold High Intensity
    Colour_BIBlack='\033[1;90m'      # Black
    Colour_BIRed='\033[1;91m'        # Red
    Colour_BIGreen='\033[1;92m'      # Green
    Colour_BIYellow='\033[1;93m'     # Yellow
    Colour_BIBlue='\033[1;94m'       # Blue
    Colour_BIPurple='\033[1;95m'     # Purple
    Colour_BICyan='\033[1;96m'       # Cyan
    Colour_BIWhite='\033[1;97m'      # White

    # High Intensity backgrounds
    Colour_On_IBlack='\033[0;100m'   # Black
    Colour_On_IRed='\033[0;101m'     # Red
    Colour_On_IGreen='\033[0;102m'   # Green
    Colour_On_IYellow='\033[0;103m'  # Yellow
    Colour_On_IBlue='\033[0;104m'    # Blue
    Colour_On_IPurple='\033[0;105m'  # Purple
    Colour_On_ICyan='\033[0;106m'    # Cyan
    Colour_On_IWhite='\033[0;107m'   # White

    # A few aliases for colours in order to make possibly changing them in the future easier.
    Colour_NetworkAddress=$Colour_BIGreen
    Colour_FilePath=$Colour_BIGreen
    Colour_Command=$Colour_BIBlue

}

colour-off(){

# Separate unset calls are only for organization

    # Special "colours"
    unset Colour_Off Colour_Bold Colour_Reverse Colour_Underline
    # Regular colours
    unset Colour_Black Colour_Red Colour_Green Colour_Yellow Colour_Blue Colour_Purple Colour_Cyan Colour_White
    # Bold
    unset Colour_BBlack Colour_BRed Colour_BGreen Colour_BYellow Colour_BBlue Colour_BPurple Colour_BCyan Colour_BWhite
    # Underline
    unset Colour_UBlack Colour_URed Colour_UGreen Colour_UYellow Colour_UBlue Colour_UPurple Colour_UCyan Colour_UWhite
    # Background
    unset Colour_On_Black Colour_On_Red Colour_On_Green Colour_On_Yellow Colour_On_Blue Colour_On_Purple Colour_On_Cyan Colour_On_White
    # High Intensity
    unset Colour_IBlack Colour_IRed Colour_IGreen Colour_IYellow Colour_IBlue Colour_IPurple Colour_ICyan Colour_IWhite
    # Bold High Intensity
    unset Colour_BIBlack Colour_BIRed Colour_BIGreen Colour_BIYellow Colour_BIBlue Colour_BIPurple Colour_BICyan Colour_BIWhite
    # Bold High Intensity
    unset Colour_On_IBlack Colour_On_IRed Colour_On_IGreen Colour_On_IYellow Colour_On_IBlue Colour_On_IPurple Colour_On_ICyan Colour_On_IWhite

    # Role-specific aliases.
    unset Colour_NetworkAddress Colour_FilePath Colour_Command

}

colour-test(){
    echo "Starting colour test."
    for i in {0..255} ; do
        printf "\x1b[38;5;${i}mcolour${i}\n"
    done
    unset i
    echo "Finished colour test."
}

# Colours are enabled by default if we are working with a terminal.
if [ -t 1 ]; then
    colour-on
fi
