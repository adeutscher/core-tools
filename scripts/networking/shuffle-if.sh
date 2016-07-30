#!/bin/bash

if=$1

# Check to see if macchanger is installed.
type macchanger 2> /dev/null >&2
if [ "$?" -gt 0 ]; then
    echo "The 'macchanger' command is not installed on this system. Please install it before using this script."
    exit 1
fi

if [ -z "$if" ]; then
    echo "Please provide an interface."
    echo "Usage: $0 iface"
    exit 2
fi

ifconfig $if 2>&1 > /dev/null
if [ "$?" -gt 0 ]; then
    echo "Interface $if not found on system..."
    exit 3
fi

if [ $EUID -ne 0 ]; then
    echo "Not root, re-running script through sudo..."
    sudo $0 "$if"
    exit $?
fi

ifconfig $if down
macchanger -a $if
ifconfig $if up

