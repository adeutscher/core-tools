
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

        local __links="$(curl "$imgurLink" | grep unloaded\ thumb-title-embed | cut -d'"' -f 10 | sed 's/^\/\//https:\/\//g' | sed 's/s\./\./g' | grep http)"

        if [ "$(wc -w <<< "$__links")" -eq 0 ]; then
            error "$(printf "Found no links in ${Colour_NetworkAddress}%s${Colour_Off}" "$imgurLink")"
            continue
        fi

        local link_total=$(wc -w <<< "$__links")
        for __link in $__links; do
            local link_index=$((${link_index:-0}+1))
            local iTotal=$(($iTotal + 1))
            if [ "$(find "$galleryDir" -name "*${__link##*/}" | wc -l)" -gt 0 ]; then
                # Avoiding duplicates, and also cover the poster adding an image in front of the current image between postings (e.g. 001-A.png becoming 002-A.png).
                # Will also cover regular duplicates without even having to bother wget (e.g. 001-A.png in an unchanged gallery).
                # Trusting that imgur will not let a user upload a different image and give it the same unique name (TODO: Confirm this)
                success "$(printf "Image was already downloaded: $Colour_NetworkAddress%s$Colour_Off (%d of %d)" "$__link" "$link_index" "$link_total")"
                # A duplicate still counts as a success.
                local iSuccessful=$(($iSuccessful + 1))
            elif wget -nc -O "$galleryDir/$(printf "%04d-%s" "$link_index" "${__link##*/}")" "$__link"; then
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
