#!/bin/bash

# Check to see if tmux is installed before we do anything at all
# Also skip if CONKY_DISABLE_TMUX evaluates to true.
if type tmux 2> /dev/null >&2 && ! (( $CONKY_DISABLE_TMUX )); then

    . functions/common 2> /dev/null

    # Tmux is installed.
    tmux_lines=$(tmux list-sessions 2> /dev/null | cut -d' ' -f 1-3,11-15 | sed 's/\[.*\]\ *//g' |  perl -pe 's/^([^:]*)/ \${color \#'${colour_good}'}\1\$color/g')
    if [ -n "$tmux_lines" ]; then
        printf "\${color #$colour_header}\${font Neuropolitical:size=16:bold}tmux\$font\$color\$hr\n${tmux_lines}\n\n"
    fi
fi
