
get-imgur-gallery(){

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

    for __path in $@; do

        local galleryName="$(grep -o '[^/]*$' <<< "$__path" | cut -d '#' -f 1)"
        local imgurLink="https://imgur.com/a/$galleryName/layout/grid"
        local galleryDir="$imgurDir/$galleryName"

        if ! mkdir -p "$galleryDir"; then
            error "$(printf "Failed to create destination directory for Imgur gallery: $Colour_NetworkAddress%s$Colour_Off" "$galleryDir")"
        fi

        notice "$(printf "Downloading gallery: $Colour_NetworkAddress%s$Colour_Off" "$imgurLink")"

        local __links="$(curl "$imgurLink" | grep unloaded\ thumb-title-embed | cut -d'"' -f 10 | sed 's/^\/\//https:\/\//g' | sed 's/s\./\./g' | grep http)"

        if [ "$(wc -w <<< "$__links")" -eq 0 ]; then
            error "$(printf "Found no links in ${Colour_NetworkAddress}%s${Colour_Off}" "$imgurLink")"
            continue
        fi

        for __link in $__links; do
            echo $__link
            local iTotal=$(($iTotal + 1))
            if wget -nc -P "$galleryDir" "$__link"; then
                # Note : Non-clobber exits are counted as successes
                success "$(printf "Successfully downloaded image: $Colour_NetworkAddress%s$Colour_Off" "$__link")"
                local iSuccessful=$(($iSuccessful + 1))
            else
                error "$(printf "Failed to download image: $Colour_NetworkAddress%s$Colour_Off" "$__link")"
                echo "$__link" >> $imgurDir/failed.txt
            fi
            # Add in a small rest to be kind to imgur servers
            sleep .5
        done
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
                file "$galleryDir/"*.jpg | grep PNG | cut -d':' -f1 | xargs-i rename "s/\.jpg$/\.png/g" "{}"
                # Correct .gif extensions
                file "$galleryDir/"*.jpg | grep GIF | cut -d':' -f1 | xargs-i rename "s/\.jpg$/\.gif/g" "{}"

            else
                # 3-argument style rename command.
                # Correct .png extensions
                file "$galleryDir/"*.jpg | grep PNG | cut -d':' -f1 | xargs-i rename ".jpg" ".png" "{}"
                # Correct .gif extensions
                file "$galleryDir/"*.jpg | grep GIF | cut -d':' -f1 | xargs-i rename ".jpg" ".gif" "{}"

            fi

            notice "$(printf "Start time: ${Colour_Bold}%s${Colour_Off}" "${start_time}")"
            notice "$(printf "End time: ${Colour_Bold}%s${Colour_Off}" "$(date)")"
        fi
    fi

    # Deal with leak of loop variables.
    unset __path __link
}
