#!/bin/bash

# ssh-compile-config
#
# Compile SSH configuration from tool modules into a single SSH config file (~/.ssh/config by default).
#
# ssh-compile-config allows ~/.ssh/config to be contributed to by multiple repositories.
#   Any loaded tool module (a shell variable ending in "toolsDir") can contribute configuration
#   from its own ssh/ directory. Each module's content is kept in its own section, bounded by
#   marker comments, and only that section is replaced when the module's configuration changes.
#   Content outside of the marked sections is left alone.
#
# Because the file is shared between multiple repositories, it is expected to be a regular file.
#   A symlink into a single repository is not supported, and will be replaced by a regular file on update.
#
# Sections left behind by modules that are no longer loaded are reported with a warning.
#   Run with --clean to remove them instead.
#
# Usage: ssh-compile-config [--clean] [target-file]
#
# See ssh/README.md for module layout, priorities, and token substitution.

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

# Set to 1 when anything goes wrong. Used as the exit status.
hadErrors=0

error(){
  printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
  hadErrors=1
}

notice(){
  printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
}

success(){
  printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
}

substitute_home(){
  # Need to use sed in order to make use of regex
  # shellcheck disable=SC2001
  sed "s|^${HOME}|~|" <<< "${1}"
}

sed_escape_replacement(){
  # Escape characters that are special in the replacement side of a 's|||' expression.
  # shellcheck disable=SC2001
  sed 's/[\\|&]/\\&/g' <<< "${1}"
}

usage(){
  printf "Usage: %s [--clean] [target-file]\n\n" "$(basename "${0}")"
  printf "Compile SSH configuration from loaded tool modules into target-file (default: ~/.ssh/config).\n\n"
  printf "Arguments:\n"
  printf "  target-file  Path of the SSH config file to write. Give it as the only non-option argument,\n"
  printf "               before or after any options. If it is omitted, ~/.ssh/config is used.\n"
  printf "               A different path is useful for testing without changing your real config, e.g.:\n"
  printf "                 %s /tmp/ssh-config-test\n" "$(basename "${0}")"
  printf "               Backup (.bak), failed (.failed), and lock (.lock) files are kept next to target-file.\n\n"
  printf "Options:\n"
  printf "  --clean      Remove sections left behind by modules that are no longer loaded.\n"
  printf "  -h, --help   Show this help message.\n"
}

cleanup(){
  rm -f "${stagingFile}" "${workFile}" "${spliceFile}" "${newFile}" "${scriptOutputFile}"
}

# Other SSH Commands

get_files(){
  while read -r _possible_file; do
    [ -z "${_possible_file}" ] && continue

    if grep -qi "README" <<< "${_possible_file##*/}"; then
      # Silently skip any file with "README" anywhere in its name.
      continue
    fi

    if grep -qi "\.swp$" <<< "${_possible_file##*/}"; then
      # Silently skip any file ending in a swp extension, likely a vim swap file.
      continue
    fi

    if type file 2> /dev/null >&2 && ! file --mime-type "${_possible_file}" | grep -Pq "text/(plain|x-(python|shellscript))$"; then
      # If the `file` command is available (this is not the case in MobaXterm),
      #   then silently skip any non-ASCII files (e.g. vim swap files).
      continue
    fi

    echo "${_possible_file}"
  done <<< "$(find "${1}" -type f 2> /dev/null | sort)"
}

get_module_priority(){
  # Print the priority of a module. Modules with lower numbers are written first.
  # Messages go to file descriptor 3 (the original stdout), since this function's output is captured.

  local sshDir
  sshDir="${1}"
  local priorityFile
  priorityFile="${sshDir}/priority"
  local priority

  if [ -f "${priorityFile}" ]; then
    # Dedicated priority config: a single integer. Blank lines and '#' comments are ignored.
    priority="$(grep -vE '^\s*(#|$)' "${priorityFile}" | head -n 1 | tr -d '[:space:]')"
    if ! grep -qE '^[0-9]+$' <<< "${priority}"; then
      warning "$(printf "Invalid priority in ${C_FILEPATH}%s${NC}, using the default of ${BOLD}10${NC}." "$(substitute_home "${priorityFile}")")" >&3
      priority=
    fi
  else
    # Legacy priority tag, which must be on its own comment line in ssh/config.
    priority="$(grep -Pom1 '^#\s*priority:\K\d+' "${sshDir}/config" 2> /dev/null)"
    if [ -n "${priority}" ]; then
      notice "$(printf "Legacy priority tag found in ${C_FILEPATH}%s${NC}. Consider moving it to ${C_FILEPATH}%s${NC}." "$(substitute_home "${sshDir}/config")" "$(substitute_home "${priorityFile}")")" >&3
    fi
  fi

  # Force base 10, so that a leading zero (e.g. "08") is not read as octal.
  echo "$((10#${priority:-10}))"
}

get_module_variables_ordered(){

  local moduleVariable

  while read -r moduleVariable; do
    [ -z "${moduleVariable}" ] && continue
    # Note: Priority will currently not be able to insert a newly-added 5-priority in between a 1-priority and a 10 priority.
    #       It was mostly made as a way to make sure that modules with lots of wildcard configs got placed above other modules.

    printf "%d:%s\n" "$(get_module_priority "${!moduleVariable}/ssh")" "${moduleVariable}"

  done <<< "$(compgen -v | grep -i 'toolsDir$')" | sort -t ':' -k 1n,2 | cut -d':' -f2-

}

print_module_config_to_file(){
  # Print compiled configuration for a module
  # The reason that I am redirecting a block within the function
  #   rather than redirecting the whole module's output is that
  #   I have plans for autogenerated configuration in the near future

  local sshDir
  sshDir="${1}"
  local targetFile
  targetFile="${2}"

  # For '__.d' directories
  local subFile

  {
    # Main config file
    cat "${sshDir}/config"

    # Fluid single-file
    local fluidFile
    fluidFile="${sshDir}/fluid"
    if [ -f "${fluidFile}" ]; then
      printf "\n###\n# Non-versioned subconfig: %s\n\n" "${fluidFile}"
      cat "${fluidFile}"
    fi

    # Print divided configurations
    process_divided_files "Sub-config" "${sshDir}/config.d"
    process_divided_files "Non-versioned sub-config" "${sshDir}/fluid.d"

    # Host-specific config
    local hostConfig
    hostConfig="$sshDir/hosts/config-${HOSTNAME}"
    if [ -f "${hostConfig}" ]; then
      printf "\n###\n# Host-specific config for %s\n###\n\n" "${HOSTNAME}"
      cat "${hostConfig}";
    else
      # Be a bit flexible about what hostnames we accept
      # The cause of this was a config for a computer lab with hostnames like 'labpc-01'.
      # I didn't want to write a config for every single one for them.
      hostConfig="$sshDir/hosts/config-${HOSTNAME%-*}"
      if [[ "$HOSTNAME" != "${HOSTNAME%-*}" ]] && [ -f "${hostConfig}" ]; then
        # Enumerated hostname
        printf "\n###\n# Host-specific config for %s (generated for %s)\n###\n\n" "${HOSTNAME}" "${HOSTNAME%-*}"
        cat "${hostConfig}";
      fi
    fi
  } > "${targetFile}"
}

process_divided_files(){

  local label
  label="${1}"
  local directory
  directory="${2}"

  while read -r subFile; do
    [ -z "${subFile}" ] && continue

    if grep -iqP "\.(py|sh)$" <<< "${subFile}" && [ -x "${subFile}" ]; then

      # Executable script. Save to a temporary location.
      local scriptStatus
      scriptOutputFile="$(mktemp)"
      "${subFile}" > "${scriptOutputFile}"
      scriptStatus=$?

      # Output
      printf "\n###\n# %s script \"%s\" for %s\n###\n\n" "${label}" "${subFile##*/}" "${sshDir}"
      if (( scriptStatus )); then
        # Keep the module, but announce the failure both on the terminal and in the compiled config.
        # Output from a failed script is left out entirely.
        #   It is preferred that script output be missing rather than potentially invalid.
        # The warning goes to file descriptor 3 (the original stdout), since stdout is redirected to the staging file here.
        warning "$(printf "%s script ${C_FILEPATH}%s${NC} exited with status ${BOLD}%d${NC}. Its output was left out." "${label}" "$(substitute_home "${subFile}")" "${scriptStatus}")" >&3
        hadErrors=1
        printf "# WARNING: Script \"%s\" exited with status %d. Its output was left out.\n" "${subFile##*/}" "${scriptStatus}"
      else
        cat "${scriptOutputFile}"
      fi

      rm -f "${scriptOutputFile}"
    else
      # Directly print contents
      printf "\n###\n# %s \"%s\" for %s\n###\n\n" "${label}" "${subFile##*/}" "${sshDir}"
      cat "${subFile}";
    fi

  done <<< "$(get_files "${directory}")"
}

process_leftover_sections(){
  # Warn about sections in the working copy whose module variable is no longer loaded.
  # With --clean, remove those sections instead.
  # A module whose variable is still set but whose directory or ssh/config is missing still counts as loaded.

  local name
  local marker
  local start
  local end

  while read -r name; do
    [ -z "${name}" ] && continue
    grep -qxF "${name}" <<< "${moduleVariables}" && continue

    marker="${name}-marker"

    if (( ! cleanLeftovers )); then
      warning "$(printf "Leftover section ${BOLD}%s${NC} in ${C_FILEPATH}%s${NC} has no loaded module. Run with ${BOLD}--clean${NC} to remove it." "${marker}" "$(substitute_home "${targetFile}")")"
      continue
    fi

    if [ -n "${noWrite}" ]; then
      warning "$(printf "Leftover section ${BOLD}%s${NC} could not be removed." "${marker}")"
      continue
    fi

    start=$(grep -nm1 "^# ${marker} checksum:" "${workFile}" | cut -d':' -f1)
    end=$(grep -nxm1 "# ${marker}-end" "${workFile}" | cut -d':' -f1)
    if [ -z "${end}" ] || (( end < start )); then
      # Without a usable end marker, there is no safe way to tell where the section stops.
      warning "$(printf "Leftover section ${BOLD}%s${NC} has no end marker, so it was not removed. It must be removed by hand." "${marker}")"
      continue
    fi

    {
      head -n "$((start-1))" "${workFile}"
      # Everything after the end marker, minus the single blank line that was written after it.
      tail -n "+$((end+1))" "${workFile}" | sed '1{/^$/d}'
    } > "${spliceFile}"
    # Copy contents rather than moving, so that the working copy keeps its private permissions.
    cat "${spliceFile}" > "${workFile}"

    countRemoved=$((countRemoved+1))
    success "$(printf "${GREEN}Removed${NC} leftover section ${BOLD}%s${NC}" "${marker}")"
  done <<< "$(grep -oP '^# \K[A-Za-z_][A-Za-z0-9_]*(?=-marker checksum:)' "${workFile}" | sort -u)"
}

validate_config(){
  # Check that a compiled config file can be parsed by ssh.
  # Any complaints from ssh are printed with the file path replaced by the display path given as the second argument.

  local file
  file="${1}"
  local displayPath
  displayPath="${2}"
  local output
  local line

  if ! type ssh 2> /dev/null >&2; then
    warning "The ssh command was not found. Skipping validation of the compiled config."
    return 0
  fi

  if output="$(ssh -G -F "${file}" localhost 2>&1 < /dev/null > /dev/null)"; then
    return 0
  fi

  while read -r line; do
    [ -z "${line}" ] && continue
    error "${line//"${file}"/${displayPath}}"
  done <<< "${output}"
  return 1
}

ssh_compile_config(){

  # Set the destination SSH config in a variable.
  # Useful in the event of debugging without stepping on your actual config.
  targetFile="${1:-$HOME/.ssh/config}"
  newFile="${targetFile}.new"
  failedFile="${targetFile}.failed"
  backupPath="${targetFile}.bak"
  lockFile="${targetFile}.lock"

  # Keep a handle on the original stdout for messages printed while stdout is redirected or captured.
  exec 3>&1

  trap cleanup EXIT
  if ! stagingFile="$(mktemp)" || ! workFile="$(mktemp)" || ! spliceFile="$(mktemp)"; then
    error "Unable to create temporary files. Aborting..."
    return 1
  fi

  # If the configuration file exists but cannot be read for for markers,
  #   then assume that it also cannot be written to.
  if [ -f "${targetFile}" ] && [ ! -r "${targetFile}" ]; then
    error "$(printf "Existing config file ${C_FILEPATH}%s${NC} cannot be read for markers. Aborting..." "$(substitute_home "$targetFile")")"
    return 1
  fi

  # Double-check that the parent directory exists
  if ! mkdir -p "$(dirname "${targetFile}")" 2> /dev/null; then
    error "$(printf "Unable to create ${C_FILEPATH}%s${NC} directory." "$(dirname "$targetFile")")"
    return 1
  fi

  # Double-check that we can write to the file and parent directory.
  if [ -f "${targetFile}" ] && [ ! -w "${targetFile}" ] || [ ! -w "$(dirname "${targetFile}")" ]; then
    error "$(printf "Config file ${C_FILEPATH}%s${NC} cannot be written to." "$(substitute_home "${targetFile}")")"
    notice "We will still check all modules for potential updates, though..."
    noWrite=1
  fi

  if [ -L "${targetFile}" ]; then
    # Symlinks are not supported, since the file is meant to be shared by multiple repositories.
    warning "$(printf "Config file ${C_FILEPATH}%s${NC} is a symlink to ${C_FILEPATH}%s${NC}. An update will replace it with a regular file." "$(substitute_home "${targetFile}")" "$(substitute_home "$(readlink -f "${targetFile}")")")"
  fi

  if [ -z "${noWrite}" ] && type flock 2> /dev/null >&2; then
    # Prevent simultaneous runs (e.g. two logins at once) from interleaving their updates.
    # The lock is released when the script exits.
    # flock is not available everywhere (e.g. MobaXterm), so locking is skipped where it is missing.
    if ! exec 4> "${lockFile}" || ! flock -w 30 4; then
      error "$(printf "Unable to lock ${C_FILEPATH}%s${NC}. Is another ssh-compile-config still running?" "$(substitute_home "${lockFile}")")"
      return 1
    fi
  fi

  # All changes are made to a working copy, which is validated and then installed in a single step.
  if [ -f "${targetFile}" ]; then
    cat "${targetFile}" > "${workFile}"
  fi

  countModuleTotal=0
  countUpdated=0
  countConfigTotal=0
  countRemoved=0

  # Also used afterwards to find sections left behind by modules that are no longer loaded.
  moduleVariables="$(get_module_variables_ordered)"

  while read -r moduleVariable; do
    [ -z "${moduleVariable}" ] && continue
    countModuleTotal=$((countModuleTotal+1))

    # This marker is used by the header for a section
    marker="${moduleVariable}-marker"

    # Recore sshDir as a base for SSH configuration and for use with SSH_DIR token substitution
    sshDir="${!moduleVariable}/ssh"
    # Replace $HOME with ~ for display purposes
    sshDirDisplay="$(substitute_home "${sshDir}/")"

    if [ ! -f "${sshDir}/config" ]; then
      if [ -d "${!moduleVariable}" ]; then
        # No module directory exists, but no SSH configuration file could be found within it.
        # Only making the lack of a configuration in a module give notice (as opposed to a warning or error).
        #   I think that this message is more likely to be a silly FYI than a serious error.
        notice "$(printf "No SSH configuration located at ${GREEN}%s${NC}" "$(substitute_home "${sshDir}/config")")"
      else
        # A module directory vanishing out from under us IS a cause for concern.
        error "$(printf "Module directory not found: ${GREEN}%s${NC}" "$(substitute_home "${!moduleVariable}")")"
      fi
      continue
    fi

    countConfigTotal=$((countConfigTotal+1))

    print_module_config_to_file "${sshDir}" "${stagingFile}"
    # Perform substitutions on staging file.
    sed -i \
      -e "s|\bTOOLS_DIR\b|$(sed_escape_replacement "${!moduleVariable}")|g" \
      -e "s|\bTOOLS_PARENT\b|$(sed_escape_replacement "$(readlink -f "${!moduleVariable}/..")")|g" \
      -e "s|\bSSH_DIR\b|$(sed_escape_replacement "${sshDir}")|g" \
      "${stagingFile}"
    # Get a checksum from our staging file.
    checksum="$(md5sum "${stagingFile}" | cut -d' ' -f1)"

    # Probe for an existing version of this section.
    sectionStart=$(grep -wnm1 "${marker}" "${workFile}" | cut -d':' -f1)
    sectionEnd=$(grep -wnm1 "${marker}-end" "${workFile}" | cut -d':' -f1)
    sectionChecksum=$(grep -wm1 "${marker}" "${workFile}" | grep -o "checksum:[^ ]*" | cut -d':' -f2)

    local countUpdated=$((countUpdated+1))

    if [ -z "$sectionEnd" ]; then
      # An end-marker does not exist in our SSH config. Just append it onto the existing config.

      if [ -n "$noWrite" ]; then
        # Could not write to location. Print our warnings now and continue to the next loop.
        if [ -z "$sectionStart" ]; then
          warning "$(printf "SSH config from ${C_FILEPATH}%s${NC} could not be inserted." "${sshDirDisplay}")"
        else
          warning "$(printf "SSH config from ${C_FILEPATH}%s${NC} was corrupted. Data could not be inserted." "${sshDirDisplay}")"
        fi
        continue
      fi

      if [ -n "${sectionStart}" ]; then
        # If this executes (start is set, but end is not), then some joker deleted the end marker.
        # If we cannot determine the proper end, delete everything below then add in.
        sed -i "${sectionStart},\$d" "${workFile}"

        warning "$(printf "SSH config from ${C_FILEPATH}%s${NC} was corrupted. Someone removed the end marker..." "${sshDirDisplay}")"
        warning "$(printf "Clearing out all content below the ${BOLD}%s${NC} section." "${marker}")"
      fi

      # Write header and general configs.
      {
        printf "# %s checksum:%s\n\n" "${marker}" "${checksum}";
        cat "${stagingFile}"
        # Write tail.
        printf "\n\n# %s-end\n\n" "${marker}"
      } >> "${workFile}"

      if [ -z "$sectionStart" ]; then
        success "$(printf "${GREEN}Inserted${NC} SSH config from ${C_FILEPATH}%s${NC}" "${sshDirDisplay}")"
      fi

    elif [[ "$checksum" != "$sectionChecksum" ]]; then
      # This section needs to be separate, as it involves inserting a config block into our existing config instead of just appending.

      if [ -n "$noWrite" ]; then
        warning "$(printf "SSH configuration updates from ${C_FILEPATH}%s${NC} could not be written." "${sshDirDisplay}")"
        continue
      fi

      # Write previous content, header, and general configs.
      {
        head -n "$((sectionStart-1))" "${workFile}"
        printf "# %s checksum:%s\n\n" "${marker}" "${checksum}"
        cat "${stagingFile}"
        # Write footer and tail
        printf "\n\n# %s-end\n\n" "${marker}"
        # Everything after the end marker, minus the single blank line that we wrote after it last time.
        tail -n "+$((sectionEnd+1))" "${workFile}" | sed '1{/^$/d}'
      } > "${spliceFile}"
      # Copy contents rather than moving, so that the working copy keeps its private permissions.
      cat "${spliceFile}" > "${workFile}"

      success "$(printf "${BLUE}Updated${NC} SSH configuration from ${C_FILEPATH}%s${NC}" "${sshDirDisplay}")"

    else
      countUpdated=$((countUpdated-1))
      notice "$(printf "No changes to SSH config from ${C_FILEPATH}%s${NC}" "${sshDirDisplay}")"
    fi
  done <<< "${moduleVariables}" # End config loop.

  process_leftover_sections

  if [ "${countUpdated}" -ne 1 ]; then
    pluralSection="s"
  fi
  countsPhrasing="$(printf "(${BOLD}%d${NC} SSH section${pluralSection} updated, ${BOLD}%d${NC} sections, ${BOLD}%d${NC} modules)" "${countUpdated}" "${countConfigTotal}" "${countModuleTotal}")"
  if (( cleanLeftovers )); then
    countsPhrasing="${countsPhrasing%)}$(printf ", ${BOLD}%d${NC} leftover removed)" "${countRemoved}")"
  fi
  if (( countUpdated + countRemoved == 0 )); then
    # The installed config already matches the modules, so a failed config from an earlier run is no longer relevant.
    [ -z "${noWrite}" ] && rm -f "${failedFile}"
    notice "$(printf "No updates to ${C_FILEPATH}%s${NC} %s" "$(substitute_home "$targetFile")" "${countsPhrasing}")"
  elif [ -n "${noWrite}" ]; then
    # No-write message
    error "$(printf "Could not update ${C_FILEPATH}%s${NC}, file was not writable... %s" "$(substitute_home "$targetFile")" "${countsPhrasing}")"
  elif ! validate_config "${workFile}" "$(substitute_home "${failedFile}")"; then
    # Keep the failed file for review. Line numbers in the errors above refer to it.
    ( umask 077; cat "${workFile}" > "${failedFile}" )
    error "$(printf "Compiled config failed validation, so ${C_FILEPATH}%s${NC} was not changed. The failed config was kept at ${C_FILEPATH}%s${NC} for review." "$(substitute_home "$targetFile")" "$(substitute_home "${failedFile}")")"
  else
    # Back up the existing file, then swap in the new one in a single step.
    if [ -f "${targetFile}" ]; then
      if cp "${targetFile}" "${backupPath}"; then
        notice "$(printf "Backed up ${C_FILEPATH}%s${NC} to ${C_FILEPATH}%s${NC}" "$(substitute_home "${targetFile}")" "$(substitute_home "${backupPath}")")"
      else
        error "$(printf "Failed to back up ${C_FILEPATH}%s${NC} to ${C_FILEPATH}%s${NC}. No changes were made." "$(substitute_home "${targetFile}")" "$(substitute_home "${backupPath}")")"
        return 1
      fi
    fi

    if ( umask 077; cat "${workFile}" > "${newFile}" ) && mv "${newFile}" "${targetFile}"; then
      # A failed config from an earlier run is no longer relevant.
      rm -f "${failedFile}"
      notice "$(printf "Updated ${C_FILEPATH}%s${NC} %s" "$(substitute_home "$targetFile")" "${countsPhrasing}")"
    else
      error "$(printf "Failed to install the compiled config to ${C_FILEPATH}%s${NC}. No changes were made." "$(substitute_home "${targetFile}")")"
    fi
  fi

  # Correct permissions
  ssh-fix-permissions

  return "${hadErrors}"
}

cleanLeftovers=0
targetArg=
while [ "$#" -gt 0 ]; do
  case "${1}" in
    --clean)
      cleanLeftovers=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      error "$(printf "Unknown option: ${BOLD}%s${NC}" "${1}")"
      usage
      exit 1
      ;;
    *)
      if [ -n "${targetArg}" ]; then
        error "Only one target file can be given."
        usage
        exit 1
      fi
      targetArg="${1}"
      ;;
  esac
  shift
done

ssh_compile_config "${targetArg}"
