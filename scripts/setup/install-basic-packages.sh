#!/bin/bash

# Simple script to install some of my favourite packages.

#####################
# Message Functions #
#####################

# Define colours
BLUE='\033[1;34m'
GREEN='\033[1;32m'
RED='\033[0;31m'
YELLOW='\e[0;93m'
BOLD='\e[1m'
NC='\033[0m' # No Color

error(){
    printf "$RED"'Error'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

notice(){
    printf "$BLUE"'Notice'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

success(){
    printf "$GREEN"'Success'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

warning(){
    printf "$YELLOW"'Warning'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

# Lazy script to install some of our favourite repositories and packages on a new system.

get-os(){
    # Using the WINDIR environment variable as a lazy litmus test for
    #   whether or not we're in a Windows machine using MobaXterm.

    if [ -n "$WINDIR" ]; then
        # Windows via MobaXterm
        os="windows"
    elif [ -f /etc/lsb-release ]; then
        # Ubuntu
        os=$(lsb_release -s -d)
    elif [ -f /etc/debian_version ]; then
        # Debian
        os="Debian $(cat /etc/debian_version)"
    elif [ -f /etc/redhat-release ]; then
        
        os=`cat /etc/redhat-release`
    else
        os="$(uname -s) $(uname -r)"
    fi

    echo "${os:-unknown}"
}

setup(){

    local os="$(get-os)"

    case "${os}" in
    "windows")
        notice "Trying to install packages for Windows via MobaXterm..."
        apt-get install perl tmux openssl curl
        ;;
    "Ubuntu"*)
        notice "Trying to install packages for Ubuntu..."
        sudo apt-get install tmux nmap subversion git vim openvpn
        ;;
    "Fedora release 22"*)
        notice "Trying to install repositories for Fedora 22..."
        sudo dnf install http://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-22.noarch.rpm 
        sudo dnf install http://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-22.noarch.rpm
        
        notice "Trying to install packages for Fedora 22..."
        sudo dnf install tmux nmap subversion git openvpn tigervnc vlc conky
        ;;
    "Fedora release 23"*)
        notice "Trying to install repositories for Fedora 23..."
        sudo dnf install http://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-23.noarch.rpm 
        sudo dnf install http://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-23.noarch.rpm
        
        notice "Trying to install packages for Fedora 23..."
        sudo dnf install tmux nmap subversion git openvpn tigervnc vlc conky
        ;;
    *)
        error "$(printf "Unsupported OS: ${BOLD}%s${NC}" "$os")"
        ;;
    esac

}
setup
