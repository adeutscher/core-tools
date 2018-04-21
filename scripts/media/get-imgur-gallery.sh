
# Common message functions.

# Define colours
if [ -t 1 ]; then
  Colour_BIBlue='\033[1;34m'
  Colour_BIGreen='\033[1;32m'
  Colour_BIRed='\033[1;31m'
  Colour_BIYellow='\033[1;93m'
  Colour_Bold='\033[1m'
  Colour_Off='\033[0m' # No Color

  Colour_NetworkAddress=$Colour_BIGreen
  Colour_FilePath=$Colour_BIGreen
  Colour_Command=$Colour_BIBlue
fi

error(){
  printf "$Colour_BIRed"'Error'"$Colour_Off"'['"$Colour_BIGreen"'%s'"$Colour_Off"']: %s\n' "$(basename $0)" "$@"
}

notice(){
  printf "$Colour_BIBlue"'Notice'"$Colour_Off"'['"$Colour_BIGreen"'%s'"$Colour_Off"']: %s\n' "$(basename $0)" "$@"
}

success(){
  printf "$Colour_BIGreen"'Success'"$Colour_Off"'['"$Colour_BIGreen"'%s'"$Colour_Off"']: %s\n' "$(basename $0)" "$@"
}

warning(){
  printf "$Colour_BIYellow"'Warning'"$Colour_Off"'['"$Colour_BIGreen"'%s'"$Colour_Off"']: %s\n' "$(basename $0)" "$@"
}

# Script functions

check_commands(){
    if ! type curl 2> /dev/null >&2; then
        error "$(printf "$Colour_Command%s$Colour_Off is required for this script." "curl")"
        exit 1
    fi
}

get_imgur_gallery(){

    if [ -d "$HOME/Downloads" ]; then
        local imgurDir="$HOME/Downloads/imgur"
    else
        local imgurDir="$HOME/downloads/imgur"
    fi

    # Tallies
    local iTotal=0
    local iSuccessful=0

    # Track start time
    local start_time="$(date)"

    local gallery_total=$#

    for __path in $@; do

        local galleryName="$(grep -o '[^/]*$' <<< "$__path" | cut -d '#' -f 1)"
        local imgurLink="https://imgur.com/a/$galleryName/layout/grid"
        local galleryDir="$imgurDir/$galleryName"
        local gallery_index=$((${gallery_index:-0}+1))

        if ! mkdir -p "$galleryDir"; then
            error "$(printf "Failed to create destination directory for Imgur gallery: $Colour_NetworkAddress%s$Colour_Off (%d of %d)" "$galleryDir" "$gallery_index" "$gallery_total")"
            continue
        fi

        notice "$(printf "Downloading gallery: $Colour_NetworkAddress%s$Colour_Off (%d of %d)" "$imgurLink" "$gallery_index" "$gallery_total")"

        local __links="$(curl -s "$imgurLink" | grep -m1 "item: " | sed 's/^\s*item:\s*//g' | python -c 'import sys,json; print " ".join(["https://i.imgur.com/%s%s" % (i["hash"],i["ext"]) for i in json.loads(sys.stdin.readline())["album_images"]["images"]])' 2> /dev/null)"

        if [ "$(wc -w <<< "$__links")" -eq 0 ]; then
            error "$(printf "Found no links in ${Colour_NetworkAddress}%s${Colour_Off}" "$imgurLink")"
            continue
        fi

        local link_total=$(wc -w <<< "$__links")
        for __link in $__links; do
            local link_index=$((${link_index:-0}+1))
            local iTotal=$(($iTotal + 1))
            # If a file is to be downloaded, then it will be written to this path.
            local targetFile="$galleryDir/$(printf "%04d-%s" "$link_index" "${__link##*/}")"
            if [ "$(find "$galleryDir" -name "*${__link##*/}" | wc -l)" -gt 0 ]; then
                # Avoiding duplicates, and also cover the poster adding an image in front of the current image between postings (e.g. 001-A.png becoming 002-A.png).
                # Will also cover regular duplicates without even having to bother trying (e.g. 001-A.png in an unchanged gallery).
                # Trusting that imgur will not let a user upload a different image and give it the same unique name (TODO: Confirm this)
                success "$(printf "Image was already downloaded: $Colour_NetworkAddress%s$Colour_Off (%d of %d)" "$__link" "$link_index" "$link_total")"
                # A duplicate still counts as a success.
                local iSuccessful=$(($iSuccessful + 1))
            elif curl -s "$__link" > "$targetFile"; then
                # Note : Non-clobber exits are counted as successes
                success "$(printf "Successfully downloaded image: $Colour_NetworkAddress%s$Colour_Off (%d of %d)" "$__link" "$link_index" "$link_total")"
                local iSuccessful=$(($iSuccessful + 1))
            else
                error "$(printf "Failed to download image: $Colour_NetworkAddress%s$Colour_Off (%d of %d)" "$__link" "$link_index" "$link_total")"
                echo "$__link" >> $imgurDir/failed.txt
            fi
            # Add in a small rest to be kind to imgur servers
            sleep .5
        done
        # Reset gallery image count
        local link_index=0
    done

    if [ "$iTotal" -eq 0 ]; then
        warning "Links had no images to download."
    else
        if [ "$iSuccessful" -eq 0 ]; then
            error "$(printf "Failed to download any of ${Color_Bold}%d${Colour_Off}..." "$iTotal")"
        else
            success "$(printf "Downloaded ${Color_Bold}%d${Colour_Off}/${Color_Bold}%d${Colour_Off} images." "$iSuccessful" "$iTotal")"
            if [ "$iSuccessful" -lt "$iTotal" ]; then
                # Some downloads failed.
                warning "$(printf "Failed to download ${Color_Bold}%d${Colour_Off} images" "$(($iTotal - $iSuccessful))")"
            fi

            # Account for completely differnt arguments to rename between Fedora 23 and Ubuntu 12.04.
            if rename 2>&1 | grep -q perlexpr; then
                # Perl-style rename command.

                # Correct .png extensions
                file "$galleryDir/"*.jpg | grep PNG | cut -d':' -f1 | xargs -I{} rename "s/\.jpg$/\.png/g" "{}"
                # Correct .gif extensions
                file "$galleryDir/"*.jpg | grep GIF | cut -d':' -f1 | xargs -I{} rename "s/\.jpg$/\.gif/g" "{}"

            else
                # 3-argument style rename command.
                # Correct .png extensions
                file "$galleryDir/"*.jpg | grep PNG | cut -d':' -f1 | xargs -I{} rename ".jpg" ".png" "{}"
                # Correct .gif extensions
                file "$galleryDir/"*.jpg | grep GIF | cut -d':' -f1 | xargs -I{} rename ".jpg" ".gif" "{}"

            fi

            notice "$(printf "Start time: ${Colour_Bold}%s${Colour_Off}" "${start_time}")"
            notice "$(printf "End time: ${Colour_Bold}%s${Colour_Off}" "$(date)")"
        fi
    fi

    # Deal with leak of loop variables.
    unset __path __link
}

check_commands
get_imgur_gallery "$@"

