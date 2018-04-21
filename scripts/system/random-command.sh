#!/bin/bash

# A silly script to print out random command names. Might help to inspire ideas.

prep(){
    rawTempFile=$(mktemp)
    filteredTempFile=$(mktemp)
}

close(){
    rm -f "$rawTempFile"
    rm -f "$filteredTempFile"
}

# Handle arguments
for opt in $(getopt ":s" $@); do
    case "$opt" in
    "-s")
        # Enable stream mode
        stream=1
    esac
done

prep

# Gather commands.
for path in $(echo $PATH | sed 's/\:/\ /g'); do
    # Note: Using redirection of ls is much faster than BASH wildcards was.
    for command in $(ls $path 2> /dev/null); do
        echo $command >> $rawTempFile
    done
done

cat $rawTempFile | uniq | sort > $filteredTempFile
rm $rawTempFile 2> /dev/null
if (( "$stream" )); then

    trap close INT

    cat $filteredTempFile | shuf -n1
    while sleep 4; do
        cat $filteredTempFile | shuf -n1
    done
else
    cat $filteredTempFile | shuf -n1
fi

close
