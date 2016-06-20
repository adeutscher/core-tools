#!/bin/bash

if [ -n "$DBUS_SESSION_BUS_ADDRESS" ] && type amixer 2> /dev/null >&2; then
    volume=$(amixer get Master | grep -o '[0-9]*%' | head -n1 | sed 's/%//')

    # Is the system muted?
    if amixer get Master | grep -q '\[off\]'; then
        extraMessage="(Muted) "
    fi 

    if [ -n "$volume" ]; then
        printf "\${color grey}Volume:\$color $volume%% $extraMessage\${execbar echo $volume}"
    fi
fi

