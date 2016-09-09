#################
# SSH Functions #
#################

# Restrict in the super-duper-off-chance that we're on a machine with no SSH client.
if qtype ssh; then

  # We do not want a GUI prompt for credentials when doing something like pushing with git.
  unset GIT_ASKPASS SSH_ASKPASS

  # Standard switches for SSH via alias:
  alias ssh='ssh -2 -4'
  # SSH with X forwarding.
  if [ -n "$DISPLAY" ]; then
      #   Should only happen if the current machine
      #   also has a display to forward through.
      alias sshx='\ssh -2 -4 -Y'
  fi

  # Standard switches for SSH via alias:
  alias ssh6='ssh -2 -6'
  # SSH with X forwarding.
  if [ -n "$DISPLAY" ]; then
      #   Should only happen if the current machine
      #   also has a display to forward through.
      alias ssh6x='\ssh -2 -6 -Y'
  fi

  # Other SSH Commands

  ssh-compile-config(){

    # Set the destination SSH config in a variable.
    # Useful in the event of debugging without stepping on your actual config.
    local sshConfig=${1:-$HOME/.ssh/config}

    # This function looks through each of your tools modules for
    #     an ./ssh/config file and loads it into ~/.ssh/config

    local initialToolDirVariables=$((set -o posix; set) | grep -i toolsDir= | cut -d'=' -f1)

    # Do a loop to extablish ordering
    for toolDir in $initialToolDirVariables; do

      local moduleSSHDir="$(eval echo \${$toolDir})/ssh"
      local moduleSSHConfig="$moduleSSHDir/config"

      # Check for a recorded priority.
      local priority=$(grep -Pom1 "priority:\d{1,}" "$moduleSSHConfig" 2> /dev/null | cut -d':' -f 2)
      # Note: Priority will currently not be able to insert a newly-added 5-priority in between a 1-priority and a 10 priority.
      #       It was mostly made as a way to make sure that modules with lots of wildcard configs got placed above other modules.

      local toolDirVariables=$(printf "$toolDirVariables\n%d:%s" "${priority:-10}" "$toolDir")
      unset priority
    done

    # If the configuration file exists but cannot be read for for markers,
    #   then assume that it also cannot be written to.
    if [ -f "$sshConfig" ] && [ ! -r "$sshConfig" ]; then
      error "$(printf "Existing config file ${Colour_FilePath}%s${Colour_Off} cannot be read for markers. Aborting..." "$(sed "s|^$HOME|~|" <<< "$sshConfig")")"
      return 1
    fi

    # Double-check that the parent directory exists
    if ! mkdir -p "$(dirname $sshConfig)" 2> /dev/null; then
      error "$(printf "Unable to create ${Colour_FilePath}%s${Colour_Off} directory." "$(dirname $sshConfig)")"
      return 1
    fi
    
    # Double-check that we can write to the file and parent directory.
    if ( [ -f "$sshConfig" ] && [ ! -w "$sshConfig" ] ) || [ ! -w "$(dirname "$sshConfig")" ]; then
      error "$(printf "Config file ${Colour_FilePath}%s${Colour_Off} cannot be written to." "$(sed "s|^$HOME|~|" <<< "$sshConfig")")"
      notice "We will still check all modules for potential updates, though..."
      local noWrite=1
    fi

    local updatedConfigCount=0
    local totalConfigCount=0

    for toolDir in $(sort -t ':' -k 1n,2 <<< "$toolDirVariables" | cut -d':' -f2-); do
      
      local moduleSSHDir="$(eval echo \${$toolDir})/ssh"
      local moduleSSHConfig="$moduleSSHDir/config"
      # Replace $HOME with ~ for display purposes
      local moduleSSHDirDisplay="$(sed "s|^$HOME|~|" <<< "$moduleSSHDir")"
      if [ -f "$moduleSSHConfig" ]; then

        local totalConfigCount=$(($totalConfigCount+1))

        local moduleSSHMarker="$toolDir-marker"
        # Get a checksum from all loaded files.
        # README files in config.d/ are actually skipped by this function,
        #   but skipping them AND not putting in a required file extension would be a pain.
        local checksum=$(md5sum "$moduleSSHConfig" "$moduleSSHDir/config.d/"* "$moduleSSHDir/hosts/config-$HOSTNAME" 2> /dev/null | md5sum | cut -d' ' -f1)

        if [ -f "$sshConfig" ]; then
          # SSH Configuration exist, probe for existing versions.
          local sectionStart=$(grep -wnm1 "$moduleSSHMarker" < "$sshConfig" | cut -d':' -f1)
          local sectionEnd=$(grep -wnm1 "$moduleSSHMarker-end" < "$sshConfig" | cut -d':' -f1)
          local sectionChecksum=$(grep -wm1 "$moduleSSHMarker" < "$sshConfig" | grep -o "checksum:[^ ]*" | cut -d':' -f2)
        fi

        local updatedConfigCount=$(($updatedConfigCount+1))

        if [ -z "$sectionEnd" ]; then
          # This module does not exist in our SSH config. Just append it onto the existing config.

          if [ -n "$noWrite" ]; then
            if [ -z "$sectionStart" ]; then
              warning "$(printf "SSH config from ${Colour_FilePath}%s${Colour_Off} could not be inserted." "$moduleSSHDirDisplay/")"
            else
              warning "$(printf "SSH config from ${Colour_FilePath}%s${Colour_Off} was corrupted. Data could not be inserted." "$moduleSSHDirDisplay/")"
            fi
            continue
          fi

          if [ -n "$sectionStart" ]; then
            # If this executes (start is set, but end is not), then some joker deleted the end marker.
            # If we cannot determine the proper end, delete everything below then add in.
            sed -i "${sectionStart},${sectionStart}d;q" "$sshConfig"
          fi

          # Write header and general configs.
          (printf "# $moduleSSHMarker checksum:$checksum\n\n"; cat "$moduleSSHConfig" 2> /dev/null) >> $sshConfig;

          # Print divided configurations
          for subConfigFile in "$moduleSSHDir/config.d/"*; do

            if grep -qi "README" <<< "${subConfigFile##*/}"; then
                # Silently skip any file with "README" anywhere in its name.
                continue
            fi

            if [ -f "$subConfigFile" ]; then
              printf "###\n# Sub-config \"%s\" for %s\n###\n\n" "${subConfigFile##*/}"  "$moduleSSHDir" >> "$sshConfig"
              cat "$subConfigFile" 2> /dev/null >> "$sshConfig";
            fi
          done

          # Print a special flag for host-specific config. Helps to reduce confusion.
          if [ -f "$moduleSSHDir/hosts/config-$HOSTNAME" ]; then
            printf "###\n# Host-specific config for $HOSTNAME\n###\n\n" >> "$sshConfig"
            cat "$moduleSSHDir/hosts/config-$HOSTNAME" 2> /dev/null >> "$sshConfig";
          fi
          # Write tail.
          printf "\n# $moduleSSHMarker-end \n\n" >> "$sshConfig"

          # Replace SSH_DIR with module dir.
          sed -i "s|SSH_DIR|$moduleSSHDir|g" "$sshConfig"
          if [ -z "$sectionStart" ]; then
            success "$(printf "Inserted SSH config from ${Colour_FilePath}%s${Colour_Off}" "$moduleSSHDirDisplay/")"
          else
            warning "$(printf "SSH config from ${Colour_FilePath}%s${Colour_Off} was corrupted. Someone removed the end marker..." "$moduleSSHDirDisplay/")"
          fi
          
        elif [[ "$checksum" != "$sectionChecksum" ]]; then
          # This section needs to be separate, as it involves inserting a config block into our existing config instead of just appending.

          if [ -n "$noWrite" ]; then
            warning "$(printf "SSH configuration updates from ${Colour_FilePath}%s${Colour_Off} could not be written." "$moduleSSHDirDisplay/")"
            continue
          fi

          local configLines=$(wc -l < "$sshConfig")

          # Write previous content, header, and general configs.
          (head -n "$(($sectionStart-1))" "$sshConfig"; printf "# $moduleSSHMarker checksum:$checksum\n\n"; cat "$moduleSSHConfig" 2> /dev/null) > "$sshConfig.new"

          # Print divided configurations
          for subConfigFile in "$moduleSSHDir/config.d/"*; do

            if grep -qi "README" <<< "${subConfigFile##*/}"; then
                # Silently skip any file with "README" anywhere in its name.
                continue
            fi

            if [ -f "$subConfigFile" ]; then
              printf "###\n# Sub-config \"%s\" for $moduleSSHDir\n###\n\n" "${subConfigFile##*/}" >> "$sshConfig.new"
              cat "$subConfigFile" 2> /dev/null >> "$sshConfig.new";
            fi
          done

          # Print a special flag for host-specific config. Helps to reduce confusion.
          if [ -f "$moduleSSHDir/hosts/config-$HOSTNAME" ]; then
            printf "###\n# Host-specific config for $HOSTNAME\n###\n\n" >> "$sshConfig.new"
            cat "$moduleSSHDir/hosts/config-$HOSTNAME" 2> /dev/null >> "$sshConfig.new";
          fi
          (printf "\n# $moduleSSHMarker-end \n\n"; tail -n "-$(($configLines-$sectionEnd-1))" "$sshConfig") >> "$sshConfig.new"
          mv "$sshConfig.new" "$sshConfig"

          sed -i "s|SSH_DIR|$moduleSSHDir|g" "$sshConfig"
          success "$(printf "Updated SSH configuration from ${Colour_FilePath}%s${Colour_Off}" "$moduleSSHDirDisplay/")"

        else
          local updatedConfigCount=$(($updatedConfigCount-1))
          notice "$(printf "No changes to SSH config from ${Colour_FilePath}%s${Colour_Off}" "$moduleSSHDirDisplay/")"
        fi 

      else
        # Only making the lack of a configuration give notice (as opposed to a warning or error). I think that this message is more likely to be a silly FYI than a serious error.
        notice "$(printf "No SSH configuration located at ${Colour_BIGreen}%s${Colour_Off}" "$(sed "s|^$HOME|~|" <<< "$moduleSSHConfig")")"
      fi # End the else of the check for configuration file existing. 
    done # End config loop.

    if [ "$updatedConfigCount" -eq 0 ]; then

      notice "$(printf "No updates to write to ${Colour_FilePath}%s${Colour_Off} config (${Colour_Bold}%d${Colour_Off} modules with SSH configurations checked)." "$(sed "s|^$HOME|~|" <<< "$sshConfig")" "$updatedConfigCount")"

    elif [ -n "$noWrite" ]; then
      # No-write message
      error "$(printf "Wanted to update ${Colour_FilePath}%s${Colour_Off} config with ${Colour_Bold}%d${Colour_Off} of ${Colour_Bold}%d${Colour_Off} modules with SSH configurations, but the file was not writable..." "$(sed "s|^$HOME|~|" <<< "$sshConfig")" "$updatedConfigCount" "$totalConfigCount")"
    else
      # Standard message.
      notice "$(printf "Updated ${Colour_FilePath}%s${Colour_Off} config with ${Colour_Bold}%d${Colour_Off} of ${Colour_Bold}%d${Colour_Off} modules with SSH configurations." "$(sed "s|^$HOME|~|" <<< "$sshConfig")" "$updatedConfigCount" "$totalConfigCount")"
    fi

    # Correct permissions
    ssh-fix-permissions

    unset toolDir
  }

  ssh-fix-permissions(){
        local tools="$(compgen -A function ssh-fix-permissions-)"

        if [ -z "$tools" ]; then
            # No fixer functions detected.
            return 1
        fi

        for permissionFunction in $tools; do
            "$permissionFunction"
        done
        unset permissionFunction

  }

  ssh-fix-permissions-core(){
    # Confirm permissions out of ~/.ssh/
    # Assuming that the source files from individual modules are properly secured by their appropriate update functions.
    local sshConfigDir=$HOME/.ssh
    if [ -n "${sshConfigDir}" ] && [ -d "${sshConfigDir}" ]; then
        chmod 700 "$sshConfigDir" "$sshConfigDir/keys" 2> /dev/null
        chmod 600 "$sshConfigDir/config" "$sshConfigDir/keys/"* "$sshConfigDir/authorized_keys" 2> /dev/null

        # Make sure that file ownership is right.
        # Added after problems with ownership and TortoiseSVN on Windows via MobaXterm.
        if ! __is_unix; then
            chown $USERNAME -R ${sshConfigDir}/* 2> /dev/null
        fi
    fi
  }

fi # end SSH client check
