
if [ -r /dev/video0 ]; then
    # Note: Ignoring the possibility of multiple webcams for the moment...
    webcam-photo(){

        if [ -n "$1" ]; then
            local target_path="$1"
        else
            
            if [ -d "$HOME/Pictures/" ]; then
                # Default path (depending on desktop environment using a lazy check)
                local target_path="$HOME/Pictures/webcam-photos/$(date +"%Y-%m-%d-%H-%M-%S").jpg"
            else
                # Strange headless system with a webcam attached to it. Oh well, lets roll with it...
                local target_path="$HOME/webcam/webcam-photos/$(date +"%Y-%m-%d-%H-%M-%S").jpg"
            fi
            
            notice "$(printf "No path provided as first argument. Using default: ${Colour_FilePath}%s${Colour_Off}" "$target_path")"
        fi
        
        if [ -a "$target_path" ] && ! [ -f "$target_path" ]; then
            error "$(printf "${Colour_FilePath}%s${Colour_Off} already exists, and is not a file. Aborting..." "$target_path")"
        fi
        
        if ! [ -d "$(dirname "$target_path")" ] && ! mkdir -p "$(dirname "$target_path")"; then
            error "$(printf "Failed to confirm that the ${Colour_FilePath}%s${Colour_Off} directory exists." "$(dirname "$target_path")")"
            return 1
        fi
        
        # Arguable a space saver, if only by cutting down on the number of printf's that I have to write...
        for command in avconv fswebcam; do
            if qtype "$command"; then
                notice "$(printf "Using ${Colour_Command}%s${Colour_Off} to take a webcam photo. Saving to ${Colour_FilePath}%s${Colour_Off}." "$command" "$target_path")"
                case "$command" in
                "avconv")
                    if ! avconv -f video4linux2 -s 640x480 -i /dev/video0 -ss 0:0:2 -frames 1 "$target_path"; then
                        local val=$?
                        warning "$(printf "${Colour_Command}%s${Colour_Off} failed (exit code ${Colour_Bold}%d${Colour_Off}. This is likely because it does not play nice with PNGs, so this may be why it failed. Consider trying with a different format." "$command" "$val")"
                    else
                        local __done=1
                    fi
                    ;;
                "fswebcam")
                    shopt -s nocasematch 2> /dev/null
                    if [[ "$target_path" =~ \.png$ ]]; then
                        local other_args="--png 0"
                    fi
                    shopt -u nocasematch 2> /dev/null
                    if ! fswebcam -r 640x480 -d /dev/video0 $other_args "$target_path"; then
                        local val=$?
                        error "$(printf "${Colour_Command}%s${Colour_Off} failed (exit code ${Colour_Bold}%d${Colour_Off})." "$command" "$val")"
                    else 
                        local __done=1
                    fi
                    ;;
                esac
                if [ -n "$__done" ]; then
                    break
                fi
            fi
        done
        unset command

        # Did not get a success marker from any of the commands.
        if [ -z "$__done" ]; then
            error "No webcam programs found on this system..."
        fi
    }
fi
