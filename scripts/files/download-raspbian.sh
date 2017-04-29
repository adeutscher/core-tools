#/bin/bash
 
link='http://downloads.raspberrypi.org/raspbian_latest'

#set -x

if [ -t 1 ]; then
    Colour_BIGreen="\033[1;92m"
    Colour_Off="\033[0m"
fi


get_raspbian(){
	download_dir=$(readlink -f "${1:-$HOME}")
	if [ -z "$download_dir" ]; then
            printf "Not a valid directory: $Colour_BIGreen%s/$Colour_Off\n" "$download_dir"
            exit 1
	elif ! [ -d "$download_dir" ]; then
            printf "Not a valid directory: $Colour_BIGreen%s/$Colour_Off\n" "$download_dir"
            exit 1
	fi

        cd "$download_dir"
        printf "Downloading to $Colour_BIGreen%s/$Colour_Off\n" "$download_dir"

        if [ -t 1 ]; then
            local sleepTime=10
            printf "You have %d seconds to abort.\n" "$sleepTime"
            sleep "$sleepTime" || return
        fi
        
        # Download the image.
        # The "raspbian_latest" link goes through two redirects before it gets to the actual image link.
        zip_link=$(curl -s $(curl "$link" -s | grep images\/ | cut -d \" -f 2) 2> /dev/null | grep images\/ | cut -d \" -f 2)
        file_name=$(basename "$zip_link")

        # Check to see if this file already exists. Don't bother re-downloading if it does.
        if [ ! -f "$file_name" ]; then
                # We have not downloaded this ZIP before. Let's fix that.
                printf "Downloading ${Colour_BIGreen}%s${Colour_Off}\n" "$file_name"
                curl -L -o "$file_name" "$zip_link"
        else
                printf "File has already been downloaded: ${Colour_BIGreen}%s${Colour_Off}\n" "$file_name"
        fi
             
        # If you wanted to, you could unzip the archive here.
        # Keep the zipped version around to skip redundant downloads.
        # Personally, I don't think it's worth possibly wasting space for.
}
 
get_raspbian $1

