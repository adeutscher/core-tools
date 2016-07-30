#!/bin/bash

# Scribbles for adding a volume indicator.
# Used too much CPU when I was testing with it, though maybe if I could stand a longer interval between runs.
# Alternately, is there an alternate way to detect volume that I'm missing?

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

