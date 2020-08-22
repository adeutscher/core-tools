#!/bin/bash

interface="${1}"

# Check to see if macchanger is installed.
if ! type macchanger 2> /dev/null >&2; then
    echo "The 'macchanger' command is not installed on this system. Please install it before using this script."
    exit 1
fi

if [ -z "${interface}" ]; then
    echo "Please provide an interface."
    echo "Usage: ${0} iface"
    exit 2
fi

if ! ifconfig "${interface}" 2> /dev/null >&2; then
    echo "Interface ${interface} not found on system..."
    exit 3
fi

if (( EUID )); then
    echo "Not root, re-running script through sudo..."
    sudo "${0}" "${interface}"
    exit ${?}
fi

ifconfig "${interface}" down
macchanger -a "${interface}"
ifconfig "${interface}" up

