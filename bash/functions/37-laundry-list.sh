
################
# Laundry List #
################

# The laundry list is an experiment in making a grocery list of things to wget.
# The idea is to tally up the list during the day, then download the items either 
#     at night or when I have a better connection.
__clean_laundry_list(){
    local filepath="$(__get_laundry_list_path)"
    if [ -n "$filepath" ]; then
        sed '/^\(https\?\|ftp\):\/\//!d' -i "$filepath"
    fi
}

__get_laundry_list_path(){
    local tempDir="$HOME/temp"
    local filename="download-queue.txt"
    if [ -d "$tempDir" ] || [ -L "$tempDir" ]; then
        echo "$tempDir/$filename"
    else
        echo "$HOME/$filename"
    fi
}

laundry-list(){
    local filepath="$(__get_laundry_list_path)"

    if [ -z "$filepath" ]; then
        echo "Error: Was not able to get file path."
        return 1
    fi

    if [ -f "$filepath" ]; then
        printf 'Laundry list contents (\033[0;92m%s\033[0m):\n' "$filepath"
        cat "$filepath"
        __clean_laundry_list
    else
        echo "Laundry list is currently empty"
    fi


}

laundry-list-add(){
    local filepath="$(__get_laundry_list_path)"

    if [ -z "$filepath" ]; then
        echo "Error: Was not able to get file path."
        return 1
    fi 

    if [ -z "$1" ]; then
        echo "No URL provided..."
        return 2
    fi

    ret=0

    for path in $@; do

        if ! egrep -q '(https?|ftp)://' <<< "$path"; then
            echo "Error: \"$path\" is an invalid URL path."
        else
            (echo "$1" >> "$filepath" && echo "Added \"$1\" to the laundry list.") || echo "Error adding \"$1\" to list."
        fi
    done
    unset path

    __clean_laundry_list

}

laundry-list-get(){
    local filepath="$(__get_laundry_list_path)"

    if [ -z "$filepath" ]; then
        echo "Error: Was not able to get file path."
        return 1
    fi
    # Clean the download list once more for good measure.
    __clean_laundry_list

    if [ -d "$HOME/Downloads" ]; then
        local dest_dir="$HOME/Downloads"
    else
        local dest_dir="$HOME/downloads"
        mkdir -p "$dest_dir"
    fi

    if wget --directory-prefix "$dest_dir" --no-check-certificate -nc -i "$filepath"; then
        echo "Successfully downloaded laundry list. Removing list..."
        rm "$filepath"
    fi
}
