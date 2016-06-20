#!/bin/bash

# Colours
BLUE='\033[1;94m'
RED='\033[1;91m'
NC='\033[0m' # No Color

# Detect PID.
pid=$(pgrep '(gnome|mate)-session' | head -n1)
if [ -n "$pid" ]; then
    printf "${BLUE}"'Notice'"${NC}"': Attaching to the D-Bus session of '"${BLUE}"'%s'"${NC}"' (PID %d)\n' "$(ps -p $pid -o command= | cut -d' ' -f 1)" "$pid"
    export $(</proc/$pid/environ tr \\0 \\n | grep -E '^DBUS_SESSION_BUS_ADDRESS=')
    export $(</proc/$pid/environ tr \\0 \\n | grep -E '^DISPLAY=')
    exit $?
else
    echo -e "${RED}Error${NC}: Unable to detect a desktop session to attach to."
    exit 1
fi
