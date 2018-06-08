#!/bin/bash

# Common message functions.
#############################

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi

error(){
  printf "${RED}"'Error'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename ${0})" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "${BLUE}"'Notice'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename ${0})" "${@}"
}

success(){
  printf "${GREEN}"'Success'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename ${0})" "${@}"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename ${0})" "${@}"
  __warning_count=$((${__warning_count:-0}+1))
}

# Script Functions
####################

__is_git_repo(){
  # Default, assume not a directory
  local __no=1

  if ! qtype git; then
    [ -n "${2}" ] && error "$(printf "${BLUE}%s${NC} is not installed." "git")"
    return 1
  elif [ -n "${1}" ] && [ -d "${1}/.git" ]; then
    cd "$(readlink -f "${1}")"
    git status 2> /dev/null >&2 && local __no=0
    cd "${OLDPWD}"
  fi

  (( "${__no}" )) && [ -n "${2}" ] && error "$(printf "${GREEN}%s${NC} does not appear to be a readable Git checkout!" "${1}")"
  return ${__no}
}

function __is_svn_repo(){
  if ! qtype svn; then
    [ -n "${2}" ] && error "$(printf "${BLUE}%s${NC} is not installed." "svn")"
    return 1
  elif [ ! -n "${1}" ] || [ ! -d "${1}/.svn" ] || ! svn info "${1}" 2> /dev/null >&2; then
    [ -n "${2}" ] && error "$(printf "${GREEN}%s${NC} does not appear to be a readable SVN checkout!" "${1}")"
    return 1
  fi
}

qtype(){
   # The help text on the type command's 'silent' switch has some wording that throws me for a loop, so making this instead.
   # Super-lazy.
   if [ -n "${1}" ]; then
       type ${@} 2> /dev/null >&2
       return ${?}
   fi
   return 1
}

function update-git-repo(){

  local repoDir="$(readlink -f "${1}")"
  local label="${2}"
  local repoDirDisplay="$(sed "s|^${HOME}|~|" <<< "${repoDir}")"

  cd "${repoDir}" || exit 1

  # Confirm that we have git.
  if ! qtype git; then
    error "Git is not detected on this machine. How exactly did you check this directory out?"
    # For someone to run into this, someone would have had to uninstalled git after loading their BASH session.
    return 1
  fi

  if [ -z "${repoDir}" ]; then
    error "No repository path provided..."
    return 2
  fi

  # Confirm a valid repository
  if ! __is_git_repo "${repoDir}" 1; then
    # Reminder: Error message is printed in __is_git_repo thanks to the extra argument
    return 3
  fi

  # Check to see if the repository directory can be written to by the current user.
  # We have already checked to make sure that the directory exists and is readable
  #  (would have been caught in __is_git_repo).
  if [ ! -w "${repoDir}" ]; then
    error "$(printf "Repository directory unwritable: ${GREEN}%s${NC}" "${repoDirDisplay}")"
    return 4
  fi

  local __num=1

  local remote="$(git branch -vv | grep -m1 "^*" | cut -d '[' -f2 | cut -d'/' -f1)"
  local repoUrl="$(git remote -v | grep -w "^${remote}" | grep -m1 "(fetch)$" | awk -F' ' '{ print $2}')"
  local branch="$(git branch | grep -m1 "^*" | cut -d' ' -f2)"

  if [ -z "${remote}" ] || [ -z "${repoUrl}" ]; then
    error "$(printf "Was unable to determine upstream information: ${GREEN}%s${NC}" "${repoDirDisplay}")"
    return 5
  fi

  # Trimming a little bit of the file URI (for local checkouts) to save a character or two.
  local repoUrlDisplay="$(sed "s|^file://||" <<< "${repoUrl}")"

  # Print our updating notice.
  if [ -n "${label}" ]; then
    notice "$(printf "Updating ${BOLD}%s${NC} repository." "${label}")"
    notice "$(printf "  Local: ${GREEN}%s/${NC}" "${repoDirDisplay}")"
  else
    # No label was given.
    notice "$(printf "  Updating repository at ${GREEN}%s/${NC}" "${repoDirDisplay}")"
  fi
  notice "$(printf "  Remote (${BOLD}%s${NC}): ${GREEN}%s${NC}" "${remote}" "${repoUrlDisplay}")"
  notice "$(printf "  Branch: ${BOLD}%s${NC}" "${branch}")"

  # Get our test domain name to try and resolve it.
  # If the domain name can be resolved, then it is assumed to be reachable.
  if grep -qP "^(https?|git)://" <<< "${repoUrl}"; then
    # HTTP Clone
    local repoDomain=$(cut -d'/' -f 3 <<< "${repoUrl}" | sed 's/^[^@]*@//')
  else
    # SSH Clone
    local repoDomain=$(cut -d':' -f 1 <<< "${repoUrl}" | cut -d'@' -f2)

    # In case checkout was done using an alias, look within SSH config file.
    # Warning: Would not play nicely with the literal word hostname as anything other than a config directive.
    if [ -r "${HOME}/.ssh/config" ]; then
      local startPoint="$(grep -nwm1 "${repoDomain}" "${HOME}/.ssh/config" | grep -iw Host | cut -d':' -f1)"
      if [ -n "${startPoint}" ]; then
        # Hostname was found in config
        local endInterval="$(tail -n +$((${startPoint}+1)) "${HOME}/.ssh/config" | grep -winm1 Host | cut -d':' -f1)"
        if [ -z "${endInterval}" ]; then
          # No end, set end to file line count.
          local endPoint="$(wc -l < "${HOME}/.ssh/config")"
        else
          # Found next host entry, only search for 'hostname' directive in these bounds.
          local endPoint="$((startPoint + ${endInterval} - 1))"
        fi
        local aliasHost="$(sed -n "${startPoint},${endPoint}p" "${HOME}/.ssh/config" | grep -iwP "hostname\s+[^\s]+" | tail -n1 | awk '{print $2}')"
        if [ -n "${aliasHost}" ]; then
          if [[ "${aliasHost}" != "${repoDomain}" ]]; then
            # There's an actual difference between the detected alias and the hostname that we already have.
            notice "$(printf "Verifying host name of SSH alias \"${GREEN}%s${NC}\": ${GREEN}%s${NC}" "${repoDomain}" "${aliasHost}")"
            local repoDomain="${aliasHost}"
          else
            notice "$(printf "SSH alias matches hostname: ${GREEN}%s${NC}" "${aliasHost}")"
          fi
        fi
      fi
    fi
  fi
  if [ -z "${repoDomain}" ]; then
    # If we can't tell the repository domain, then we have nothing to go on.
    error "$(printf "Unable to determine repository domain from workspace: ${GREEN}%s${NC}" "${repoDirDisplay}")"
    return 6
  fi

  # Check to see if we can resolve a domain address address.
  if grep -qP '^(([0-9]){1,3}\.){3}([0-9]{1,3})$' <<< "${repoDomain}"; then

    if [ -z "${aliasHost}" ] || [[ "${aliasHost}" != "${repoDomain}" ]]; then
      # Checked out from an IP address.
      # However, only print this if the repo was specifically defined as an IP.
      notice "Git workspace was checked out from an IP address."
    fi

    if ! ping -c 1 -w0.75 "${repoDomain}" 2> /dev/null >&2; then
      error "$(printf "Unable to ping repo server at ${GREEN}%s${NC}." "${repoDomain}")"
      return 7
    fi
    success "$(printf "Pinged repo server at ${GREEN}${repoDomain}${NC}" "${repoDomain}")"
  elif grep -w "$(sed 's/\./\\./g' <<< "${repoDomain}")" < /etc/hosts | sed -r 's/^\s+//g' | grep -qPm1 "^(([0-9]){1,3}\.){3}([0-9]{1,3})"; then
    local repoIp="$(grep -w "$(sed 's/\./\\./g' <<< "${repoDomain}")" < /etc/hosts | sed -r 's/^\s+//g' | grep -Pm1 "^(([0-9]){1,3}\.){3}([0-9]{1,3})" | awk '{print $1}')"
    notice "$(printf "${GREEN}%s${NC} (${GREEN}%s${NC}) found in ${GREEN}%s${NC}" "${repoDomain}" "${repoIp}" "/etc/hosts")"

    if ! ping -c 1 -w0.75 "${repoIp}" 2> /dev/null >&2; then
      error "$(printf "Unable to ping repository server at ${GREEN}%s${NC} (${GREEN}%s${NC})" "${repoDomain}" "${repoIp}")"
      return 7
    fi
    success "$(printf "Pinged repo server at ${GREEN}%s${NC} (${GREEN}%s${NC})" "${repoDomain}" "${repoIp}")"
  elif ! qtype host; then
    warning "$(printf "The ${BLUE}host${NC} command was not detected on this machine.")"
    warning "Continuing, but unable to verify that we can resolve the domain name for the upstream git repository."
  elif ! timeout 1 host ${repoDomain} 2> /dev/null >&2; then
    # Note: This check will not account for cached entries in the local BIND server (if applicable)
    # Note: Avoiding "for" phrasing in non-comments to appease pluma colouring.
    error "$(printf "${BLUE}%s${NC} was unable to resolve the address of ${GREEN}%s${NC}. Quitting...\n" "host" "${repoDomain}")"
    return 7
  fi # end else block executed after doing "pre-flight" checks for reaching the repository server.

  # Track old and new revisions (at least on our current branch).
  local oldCommit="$(git branch -v | sed -e '/^[^*]/d' | cut -d' ' -f3)"
  local oldCommitCount="$(git log | grep "^commit" | wc -l)"

  if git --version | grep -q "git version 1\."; then
    # Need to add another switch for older git versions
    local oldGitSwitch=-u
  fi

  # Update directory.
  unset cbranch
  [ "$(git --version | grep -Pom1  "\d" | head -n1)" -ge 2 ] && cbranch="${branch}"
  if git pull ${oldGitSwitch} ${remote} ${cbranch}; then
    local newCommit="$(git branch -v | sed -e '/^[^*]/d' | cut -d' ' -f3)"
    local newCommitCount="$(git log | grep "^commit" | wc -l)"

    if [[ "${oldCommit}" != "${newCommit}" ]]; then
      success "$(printf "Repository updated (${BOLD}%s${NC} to ${BOLD}r%s${NC}). New commits: ${BOLD}%d${NC}" "${oldCommit}" "${newCommit}" "$((${newCommitCount} - ${oldCommitCount}))")"
    else
      success "$(printf "Branch \"${BOLD}%s${NC}\" already up to date (or checked out to a specific revision). Revision: ${BOLD}%s${NC}." "${branch}" "${oldCommit}")"
    fi

  else
    error "$(printf "Repository update of ${GREEN}%s${NC} from ${GREEN}%s${NC} failed!" "${repoDirDisplay}"  "${repoUrlDisplay}")"
    return 8
  fi
}

function update-repo(){
  if [ -z "${1}" ]; then
    error "No repository path provided."
    return 1
  elif [ ! -d "${1}" ]; then
    error "$(printf "No such directory: ${GREEN}%s${NC}" "$(readlink -f "${1}" | sed "s|^${HOME}|~|g")")"
  elif __is_svn_repo "${1}"; then
    update-svn-repo "${1}" "${2}"
  elif __is_git_repo "${1}"; then
    update-git-repo "${1}" "${2}"
  else
    error "$(printf "${GREEN}%s${NC} does not appear to be the base of a Git repo or SVN checkout." "$(readlink -f "${1}" | sed "s|^${HOME}|~|g")")"
  fi
}

function update-svn-repo(){

  local repoDir="${1}"
  local label="${2}"
  local repoDirDisplay="$(sed "s|^${HOME}|~|" <<< "${repoDir}")"

  # Double-Check to see if SVN is even installed.
  # MobaXterm has an alias for saying that SVN is not found which throws off qtype,
  #   so we need to use specific flags on the type command
  if ! type -ftptP svn 2> /dev/null >&2; then
    error "Subversion is not detected on this machine. How exactly did you check this directory out?"
    return 1
  fi

  if [ -z "${repoDir}" ]; then
    error "No repository path provided..."
    return 2
  fi

  # Check for SVN-specific errors
  if ! __is_svn_repo "${repoDir}" 1; then
    # Reminder: Error message is printed in __is_svn_repo
    return 3
  elif svn status "${repoDir}" 2> /dev/null | head -n1 | grep -q "\ *L"; then
    # To consider: Is there a better place to put this?
    # Also: Is there a better way to check for locks? Assuming a couple of things that I would rather not:
    #   - That the top dir will always be the repository dir.
    #   - That the lock status flag will never be pre-empted by another flag.
    error "$(printf "SVN workspace at ${GREEN}%s${NC} is locked..." "${repoDir}")"
    return 3
  fi

  # Check to see if the repository directory can be written to by the current user.
  # We have already checked to make sure that the directory exists and is readable
  #  (would have been caught in __is_svn_repo).
  if [ ! -w "${repoDir}" ]; then
    error "$(printf "Repository directory unwritable: ${GREEN}%s${NC}" "${repoDirDisplay}")"
    return 4
  fi

  local repoUrl="$(svn info "${repoDir}" | grep "^URL" | cut -d' ' -f 2-)"
  if [ -z "${repoUrl}" ]; then
    error "$(printf "Was unable to determine repository URL: ${GREEN}%s${NC}" "${repoDirDisplay}")"
    # If we can't tell the repository URL with `svn info`, then the svn command won't be able to tell either.
    return 5
  fi

  # Trimming a little bit of the file URI (for local checkouts) to save a character or two.
  local repoUrlDisplay="$(sed "s|^file://||" <<< "${repoUrl}")"

  # Print our updating notice.
  if [ -n "${label}" ]; then
    notice "$(printf "Updating ${BOLD}%s${NC} repository (${GREEN}%s${NC}<-${GREEN}%s/${NC})" "${label}" "${repoDirDisplay}" "${repoUrlDisplay}")"
  else
    # No label was given.
    notice "$(printf "Updating repository (${GREEN}%s${NC}<-${GREEN}%s/${NC})" "${repoDirDisplay}" "${repoUrlDisplay}")"
  fi

  if grep '^file:///' <<< "${repoUrl}"; then
    if [ -d "${repoUrlDisplay}" ]; then
      if [ -r "${repoUrlDisplay}" ]; then
        notice "SVN workspace is checked out from a local path."
      else
        error "SVN workspace could not be read."
        return 7
      fi
    else
      # Directory does not exist.
      error "$(printf "Repository cannot be found at ${GREEN}%d${NC}..." "$(sed "s|file://||" <<< "${repoUrl}")")"
      return 8
    fi
  else
    # SVN workspace is checked out from a network location.

    # Get our test domain name to try and resolve it.
    # If the domain name can be resolved, then it is assumed to be reachable.
    local repoDomain=$(cut -d'/' -f 3 <<< "${repoUrl}")
    if [ -z "${repoDomain}" ]; then
      # If we can't tell the repository domain with `svn info`, then the svn command won't be able to tell either.
      error "$(printf "Was unable to determine our repository domain from our workspace: ${GREEN}%s${NC}" "${repoDirDisplay}")"
      return 6
    fi

    # Check to see if we can resolve a domain address address.
    if grep -qP '^(([0-9]){1,3}\.){3}([0-9]{1,3})$' <<< "${repoDomain}"; then
      notice "Git workspace was checked out from an IP address."

      if ! ping -c 1 -w0.75 "${repoDomain}" 2> /dev/nul >&2; then
        error "$(printf "Unable to ping repo server at ${GREEN}%s${NC}" "${repoDomain}")"
        return 7
      fi
      success "$(printf "Pinged repo server at ${GREEN}${repoDomain$}{NC}" "${repoDomain}")"
    elif grep -w "$(sed 's/\./\\./g' <<< "${repoDomain}")" < /etc/hosts | sed -r 's/^\s+//g' | grep -qPm1 "^(([0-9]){1,3}\.){3}([0-9]{1,3})"; then
      local repoIp="$(grep -w "$(sed 's/\./\\./g' <<< "${repoDomain}")" < /etc/hosts | sed -r 's/^\s+//g' | grep -Pm1 "^(([0-9]){1,3}\.){3}([0-9]{1,3})" | awk '{print $1}')"
      notice "$(printf "${GREEN}%s${NC} (${GREEN}%s${NC}) found in ${GREEN}%s${NC}" "${repoDomain}" "${repoIp}" "/etc/hosts")"

      if ! ping -c 1 -w0.75 "${repoIp}" 2> /dev/null >&2; then
        error "$(printf "Unable to ping repository server at ${GREEN}%s${NC} (${GREEN}%s${NC})" "${repoDomain}" "${repoIp}")"
        return 7
      fi
      success "$(printf "Pinged repo server at ${GREEN}%s${NC} (${GREEN}%s${NC})" "${repoDomain}" "${repoIp}")"
    elif ! qtype host; then
      warning "$(printf "The ${BLUE}host${NC} command was not detected on this machine.")"
      warning "Continuing, but unable to verify that we can resolve the domain name for our SVN repository."
    elif ! timeout 1 host ${repoDomain} 2> /dev/null >&2; then
      # Note: This check will not account for cached entries in the local BIND server (if applicable)
      # Note: Avoiding "for" phrasing in non-comments to appease pluma colouring.
      error "$(printf "${BLUE}%s${NC} was unable to resolve the address of ${GREEN}%s${NC}. Quitting...\n" "host" "${repoDomain}")"
      return 7
    fi # end else block executed after doing "pre-flight" checks for reaching the repository server.
  fi

  # Track old and new revisions.

  local oldRev="$(svn info "${repoDir}" 2> /dev/null | grep '^Revision' | cut -d' ' -f2)"
  # Update directory.
  if svn up "${repoDir}"; then
    local newRev="$(svn info "${repoDir}" 2> /dev/null | grep '^Revision' | cut -d' ' -f2)"
    if [ "${oldRev}" -lt "${newRev}" ]; then
      success "$(printf "SVN repository updated (${BOLD}r%d${NC} to ${BOLD}r%d${NC})." "${oldRev}" "${newRev}")"
    else
      success "$(printf "SVN repository already up to date (at ${BOLD}r%d${NC})." "${oldRev}")"
    fi

  else
    error "$(printf "Update of SVN repository at ${GREEN}%s${NC} from ${GREEN}%s${NC} failed!" "${repoDirDisplay}"  "${repoUrlDisplay}")"
    return 8
  fi
}

update-repo ${@}
