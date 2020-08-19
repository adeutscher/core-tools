#!/bin/bash

# A silly script to print out random command names. Might help to inspire ideas.

prep(){
    filteredTempFile=$(mktemp)
}

close(){
    rm -f "$filteredTempFile"
}

# Handle arguments
for opt in $(getopt ":s" "$@"); do
    case "$opt" in
    "-s")
        # Enable stream mode
        stream=1
    esac
done

prep

# Gather commands.
for path in ${PATH//:/ }; do
    for command in "${path}"/*; do
        if [ -x "${command}" ]; then
            echo "${command##*/}"
        fi
    done
done | sort | uniq > "$filteredTempFile"

if (( "$stream" )); then

    trap close INT

    n=0
    while sleep "${n}"; do
        shuf -n1 < "${filteredTempFile}"
        n=4
    done
else
    shuf -n1 < "${filteredTempFile}"
fi

close
