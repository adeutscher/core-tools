#!/bin/bash

# Common message functions.

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  C_FILEPATH='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi

error(){
  printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

success(){
  printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
  __warning_count=$((${__warning_count:-0}+1))
}

# Other SSH Commands

ssh_compile_config(){

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
    error "$(printf "Existing config file ${C_FILEPATH}%s${NC} cannot be read for markers. Aborting..." "$(sed "s|^$HOME|~|" <<< "$sshConfig")")"
    return 1
  fi

  # Double-check that the parent directory exists
  if ! mkdir -p "$(dirname $sshConfig)" 2> /dev/null; then
    error "$(printf "Unable to create ${C_FILEPATH}%s${NC} directory." "$(dirname $sshConfig)")"
    return 1
  fi

  # Double-check that we can write to the file and parent directory.
  if ( [ -f "$sshConfig" ] && [ ! -w "$sshConfig" ] ) || [ ! -w "$(dirname "$sshConfig")" ]; then
    error "$(printf "Config file ${C_FILEPATH}%s${NC} cannot be written to." "$(sed "s|^$HOME|~|" <<< "$sshConfig")")"
    notice "We will still check all modules for potential updates, though..."
    local noWrite=1
  fi

  totalModuleCount=0
  updatedConfigCount=0
  totalConfigCount=0

  for toolDir in $(sort -t ':' -k 1n,2 <<< "$toolDirVariables" | cut -d':' -f2-); do

    totalModuleCount=$(($totalModuleCount+1))
    moduleDir="$(eval echo \${$toolDir})"
    moduleParent="$(readlink -f "${moduleDir}/..")"
    moduleSSHDir="${moduleDir}/ssh"
    moduleSSHConfig="$moduleSSHDir/config"
    # Replace $HOME with ~ for display purposes
    moduleSSHDirDisplay="$(sed "s|^$HOME|~|" <<< "$moduleSSHDir")"
    if [ -f "$moduleSSHConfig" ]; then

      totalConfigCount=$(($totalConfigCount+1))

      local moduleSSHMarker="$toolDir-marker"
      # Get a checksum from all loaded files.
      checksum="$(checksum "${moduleSSHConfig}" "${moduleSSHDir}/config.d/" "${moduleSSHDir}/fluid" "${moduleSSHDir}/fluid.d/" "${moduleSSHDir}/hosts/config-${HOSTNAME%-*}")"

      if [ -f "$sshConfig" ]; then
        # SSH Configuration exist, probe for existing versions.
        sectionStart=$(grep -wnm1 "$moduleSSHMarker" "$sshConfig" | cut -d':' -f1)
        sectionEnd=$(grep -wnm1 "$moduleSSHMarker-end" "$sshConfig" | cut -d':' -f1)
        sectionChecksum=$(grep -wm1 "$moduleSSHMarker" "$sshConfig" | grep -o "checksum:[^ ]*" | cut -d':' -f2)
      fi

      local updatedConfigCount=$(($updatedConfigCount+1))

      if [ -z "$sectionEnd" ]; then
        # This module does not exist in our SSH config. Just append it onto the existing config.

        if [ -n "$noWrite" ]; then
          if [ -z "$sectionStart" ]; then
            warning "$(printf "SSH config from ${C_FILEPATH}%s${NC} could not be inserted." "$moduleSSHDirDisplay/")"
          else
            warning "$(printf "SSH config from ${C_FILEPATH}%s${NC} was corrupted. Data could not be inserted." "$moduleSSHDirDisplay/")"
          fi
          continue
        fi

        if [ -n "$sectionStart" ]; then
          # If this executes (start is set, but end is not), then some joker deleted the end marker.
          # If we cannot determine the proper end, delete everything below then add in.
          sed -i "${sectionStart},${sectionStart}d;q" "$sshConfig"
        fi

        # Write header and general configs.
        (printf "# $moduleSSHMarker checksum:${checksum}\n\n"; cat "${moduleSSHConfig}" 2> /dev/null; printf "\n") >> "${sshConfig}";

        append_fluid "${sshConfig}"

        append_config_d "${sshConfig}"

        append_fluid_d "${sshConfig}"

        append_host_config "${sshConfig}"

        # Write tail.
        printf "\n# $moduleSSHMarker-end \n\n" >> "$sshConfig"

        # Perform substitutions
        sed -i "s|TOOLS_DIR|${moduleDir}|g" "${sshConfig}"
        sed -i "s|TOOLS_PARENT|${moduleParent}|g" "${sshConfig}"
        sed -i "s|SSH_DIR|${moduleSSHDir}|g" "${sshConfig}"

        if [ -z "$sectionStart" ]; then
          success "$(printf "${GREEN}Inserted${NC} SSH config from ${C_FILEPATH}%s${NC}" "$moduleSSHDirDisplay/")"
        else
          warning "$(printf "SSH config from ${C_FILEPATH}%s${NC} was corrupted. Someone removed the end marker..." "$moduleSSHDirDisplay/")"
        fi

      elif [[ "$checksum" != "$sectionChecksum" ]]; then
        # This section needs to be separate, as it involves inserting a config block into our existing config instead of just appending.

        if [ -n "$noWrite" ]; then
          warning "$(printf "SSH configuration updates from ${C_FILEPATH}%s${NC} could not be written." "$moduleSSHDirDisplay/")"
          continue
        fi

        local configLines=$(wc -l < "${sshConfig}")

        # Write previous content, header, and general configs.
        (head -n "$(($sectionStart-1))" "$sshConfig"; printf "# ${moduleSSHMarker} checksum:${checksum}\n\n"; cat "${moduleSSHConfig}" 2> /dev/null; printf "\n") > "${sshConfig}.new"

        append_fluid "${sshConfig}.new"

        append_config_d "${sshConfig}.new"

        append_fluid_d "${sshConfig}.new"

        append_host_config "${sshConfig}.new"

        (printf "\n# $moduleSSHMarker-end \n\n"; tail -n "-$(($configLines-$sectionEnd-1))" "$sshConfig") >> "$sshConfig.new"
        mv "$sshConfig.new" "$sshConfig"

        # Perform substitutions
        sed -i "s|TOOLS_DIR|${moduleDir}|g" "${sshConfig}"
        sed -i "s|TOOLS_PARENT|${moduleParent}|g" "${sshConfig}"
        sed -i "s|SSH_DIR|${moduleSSHDir}|g" "${sshConfig}"

        success "$(printf "${BLUE}Updated${NC} SSH configuration from ${C_FILEPATH}%s${NC}" "$moduleSSHDirDisplay/")"

      else
        local updatedConfigCount=$(($updatedConfigCount-1))
        notice "$(printf "No changes to SSH config from ${C_FILEPATH}%s${NC}" "$moduleSSHDirDisplay/")"
      fi

    else
      # Only making the lack of a configuration give notice (as opposed to a warning or error). I think that this message is more likely to be a silly FYI than a serious error.
      if [ -d "$(sed -r "s/(\/[^\/]+){2}$//g" <<< "${moduleSSHConfig}")" ]; then
        notice "$(printf "No SSH configuration located at ${GREEN}%s${NC}" "$(sed "s|^$HOME|~|" <<< "$moduleSSHConfig")")"
      else
        error "$(printf "Module directory not found: ${GREEN}%s${NC}" "$(sed "s|^$HOME|~|" <<< "$(sed -r "s/(\/[^\/]+){2}$//g" <<< "${moduleSSHConfig}")")")"
      fi
    fi # End the else of the check for configuration file existing.
  done # End config loop.

  if [ "$updatedConfigCount" -eq 0 ]; then

    notice "$(printf "No updates to write to ${C_FILEPATH}%s${NC} config (${BOLD}%d${NC}/${BOLD}%d${NC} modules had SSH configurations to be checked)." "$(sed "s|^$HOME|~|" <<< "$sshConfig")" "$totalConfigCount" "$totalModuleCount")"

  elif [ -n "$noWrite" ]; then
    # No-write message
    error "$(printf "Wanted to update ${C_FILEPATH}%s${NC} config with ${BOLD}%d${NC} of ${BOLD}%d${NC} modules with SSH configurations, but the file was not writable..." "$(sed "s|^$HOME|~|" <<< "$sshConfig")" "$updatedConfigCount" "$totalConfigCount")"
  else
    # Standard message.
    notice "$(printf "Updated ${C_FILEPATH}%s${NC} config with ${BOLD}%d${NC} of ${BOLD}%d${NC} modules with SSH configurations." "$(sed "s|^$HOME|~|" <<< "$sshConfig")" "$updatedConfigCount" "$totalConfigCount")"
  fi

  # Correct permissions
  ssh-fix-permissions

  unset toolDir
}

append_config_d(){
  local target="${1}"

  # Print divided configurations
  while read subConfigFile; do
    [ -z "${subConfigFile}" ] && continue

    printf "\n###\n# Sub-config \"%s\" for %s\n###\n\n" "${subConfigFile##*/}" "${moduleSSHDir}"
    cat "$subConfigFile" 2> /dev/null;
  done <<< "$(get_files "${moduleSSHDir}/config.d")" >> "${target}"
}

append_fluid(){
  local target="${1}"

  if [ -f "${moduleSSHDir}/fluid" ]; then
    (printf "\n###\n# Non-versioned subconfig: ${moduleSSHDir}/fluid\n\n"; cat "${moduleSSHDir}/fluid")
  fi >> "${target}"
}

append_fluid_d(){
  local target="${1}"

  # Print divided unversioned configurations
  while read subConfigFile; do
    [ -z "${subConfigFile}" ] && continue

    printf "###\n# Non-versioned sub-config \"%s\" for %s\n###\n\n" "${subConfigFile##*/}" "$moduleSSHDir"
    cat "$subConfigFile" 2> /dev/null;
  done <<< "$(get_files "${moduleSSHDir}/fluid.d")" >> "${target}"
}

append_host_config(){
  local target="${1}"

  # Print a special flag for host-specific config. Helps to reduce confusion.
  if [ -f "$moduleSSHDir/hosts/config-${HOSTNAME%-*}" ]; then
    if [[ "$HOSTNAME" != "${HOSTNAME%-*}" ]]; then
      # Enumerated hostname
      printf "###\n# Host-specific config for $HOSTNAME (generated for ${HOSTNAME%-*})\n###\n\n"
    else
      printf "###\n# Host-specific config for $HOSTNAME\n###\n\n"
    fi
    cat "$moduleSSHDir/hosts/config-${HOSTNAME%-*}" 2> /dev/null;
  fi >> "${target}"
}

checksum(){
  while [ -n "${1}" ]; do
    local i="${1}"
    shift

    [ -z "${i}" ] && continue

    if [ -d "${i}" ]; then
      while read f; do
        [ -z "${f}" ] && continue

        cat "${f}" 2> /dev/null
      done <<< "$(get_files "${i}")"
    elif [ -f "${i}" ]; then
      cat "${i}"
    fi
  done | md5sum | cut -d' ' -f1
}

get_files(){
  while read _possible_file; do
    [ -z "${_possible_file}" ] && continue

    if grep -qi "README" <<< "${_possible_file##*/}"; then
      # Silently skip any file with "README" anywhere in its name.
      continue
    fi

    if ! file --mime-type "${_possible_file}" | grep -q "text/plain$"; then
      # Silently skip any non-ASCII files (e.g. vim swap files).
      continue
    fi

    echo "${_possible_file}"
  done <<< "$(find "${1}" -type f 2> /dev/null)"
}

ssh_compile_config $@
