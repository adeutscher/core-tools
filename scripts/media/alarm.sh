#!/bin/bash

check(){
    if ! type mpg123 2> /dev/null >&2; then
        printf "mpg123 command not installed...\n"
        exit 1
    fi
}

opts(){
    while [ -n "$1" ]; do
        local opt="$1"
        case "$opt" in
        "-c")
            if grep -Pq '^\d{1,}$' <<< "$2"; then
                RUN_COUNT=$2
            fi
            shift
        ;;

        esac
        shift
    done
}

play(){


    local dir=$HOME/Music

    local musicFile="$(find -L "$dir" -iname "*mp3" | shuf -n 1)"
    if [ -z "$musicFile" ]; then
        printf "No music files found at all.\n"
        return 1
    else
        echo "Playing $musicFile"
        mpg123 "$musicFile"
    fi
}

run(){
    if [ -n "$RUN_COUNT" ]; then
        local count=0
        while [ "${RUN_COUNT}" -eq 0 ] || [ "$count" -lt "$RUN_COUNT" ]; do
            play
            local count=$(($count+1))
        done
    else
        play
    fi
}

check
opts $@
run
