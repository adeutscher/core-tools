#!/bin/bash

######################
 ####################
 # Prompt Functions #
 ####################
######################

# This file contains functions, variables, and aliases that are used to build a customized command prompt.

#############
# Variables #
#############

SVNP_HUGE_REPO_EXCLUDE_PATH="nufw-svn$|/tags$|/branches$"

#############
# Functions #
#############

PROMPT_COMMAND='__build_prompt'
__build_prompt() {

  # Track the exit value of the last command.
  # This needs to be done before ANYTHING other call in order to capture the exit code properly.
  # Will process it later.
  local __RETURN_VALUE=$?

  # If requested, stick to an instant prompt with zero colours or calculations.
  if [ -n "$BASIC_PROMPT" ]; then
    PS1='[\u@\h][\w]\$ '
    return 0
  fi

  # - If we are in an SSH session ($SSH_CLIENT is set),
  #     print the address that we are connected from.
  # - Placing this task directly in __build_prompt due to color escaping issues.
  # - Checking for variables like TMUX/VNCDESKTOP/etc to be empty. A prompt under tmux/etc will use the SSH_CLIENT
  #     variable from the first session to start the session, and the variable will not be accurate forever.
  # - Note: TERMCAP is set in a screen session.
  if [ -z "$TMUX" ] && [ -n "$SSH_CLIENT" ] && [ -z "$VNCDESKTOP" ] && [ -z "$TERMCAP" ]; then
    local ssh_address=$(cut -d' ' -f 1 <<< $SSH_CLIENT)
    # Note: Extra 5 characters are for " via "
    local ssh_space_count=$((5 + $(__strlen "$ssh_address")))
  fi
  
  # Intentionally not using a local variable in order to only have to do one call to __get_fs
  #   (the other potential one being in __promt_file_system_colour).
  # Probably a bit overly complex.
  __fs="$(__get_fs)"

  # If we are on a Linux system, try to get version control information.
  # Short-term (2016-03-10) fix, as it currently misbehaves in MobaXterm.
  if __is_unix && ! egrep -q '^(cifs|nfs.*)$' <<< "$fs"; then
    local svn_output="$(__svn_stat)"
    if [ -n "$svn_output" ]; then
      local svn_remote_status=$(cut -d',' -f 1 <<< "$svn_output")
      local svn_rev=$(cut -d',' -f 2 <<< "$svn_output")
      local svn_status=$(cut -d',' -f 3 <<< "$svn_output")
      # Square braces in svn_output are accounted for because the output is delimited by an equal number of characters.
      local vc_count=$(__strlen "$svn_output")

    else
      # Try git output.
      # Assuming that a directory will not be valid for two version control checkouts at one time.
      local git_output="$(__parse_git_branch)"
      if [ -n "$git_output" ]; then
        local git_branch=$(cut -d',' -f1 <<< "$git_output")
        local git_flags=$(cut -d',' -f2 <<< "$git_output")

        # Only one square bracket in git output is already accounted for.
        local vc_count=$(($(__strlen "$git_output") + 1))
      fi
    fi # End version control content check
  fi # End file system check for SVN.

  # Experimental: If the first line of the prompt would offer too little typing room, try shorting the prompt.
  # Would mostly come up when navigating deep directories in a small tmux pane.
  # Amongst our methods are such elements as:
  # - Shorter directory path
  # - (slightly) shorter SSH path.
  # - Shorten username to one letter
  local typing_space=$(($(stty size | cut -d' ' -f 2)-$(__strlen "$(pwd | sed "s|^$HOME|H|g")$(hostname -s)$USER")-${ssh_space_count:-0}-${vc_count:-0}-7))
  # Typing space takes into account:
  # - Path length, accounting for a tilde in home directory
  # - Username length
  # - Hostname
  # - SSH address
  # - Formatting characters (static 7 for now)
  # - Version control information
  local box_colour="$(__prompt_box_colour)"

  # Build
  if [ "$typing_space" -ge 20 ]; then
    # Regular expanded prompt
    # Start
    PS1='\['"$box_colour"'\][\[\033[m\]\[$(__prompt_username_colour)\]'"${DISPLAY_USER:-\u}"'\[\033[m\]\['"$Colour_Bold"'\]@\[\033[m\]\[$(__prompt_hostname_colour)\]'"${DISPLAY_HOSTNAME:-\h}"'\[\033[m\]'
    if [ -n "$ssh_address" ]; then
        PS1=$PS1" via \[$Colour_NetworkAddress\]$ssh_address\[$Colour_Off\]"
    fi
    PS1=$PS1"\[$box_colour\]][\[\033[m\]\[$(__prompt_file_system_colour)\]\w\[\033[m\]\[$box_colour\]]\[\033[m\]"
  else
    # Compressed prompt
    # Make a bit more typing space in closed quarters
    # Start
    PS1='\['"$box_colour"'\][\[\033[m\]\[$(__prompt_username_colour)\]'"${USER:0:1}"'\[\033[m\]\['"$Colour_Bold"'\]@\[\033[m\]\[$(__prompt_hostname_colour)\]'${HOSTNAME:0:1}'\[\033[m\]'
    if [ -n "$ssh_address" ]; then
        PS1=$PS1"\[$Colour_Bold\]%\[$Colour_Off\]\[$Colour_NetworkAddress\]$ssh_address\[$Colour_Off\]"
    fi
    PS1=$PS1"\[$box_colour\]][\[\033[m\]\[$(__prompt_file_system_colour)\]\W\[\033[m\]\[$box_colour\]]\[\033[m\]"
  fi
  
  # Always print version control output if present for now
  #   (it can't get much more compressed, anyways)
  if [ -n "$svn_output" ]; then
    PS1=$PS1'\['"$box_colour"'\][\[\033[m\]'

    if [ -n "$svn_remote_status" ]; then
      PS1=$PS1'\['$Colour_BIPurple'\]'"$svn_remote_status"'\['$Colour_Off'\]'
    fi

    if [ -n "$svn_rev" ]; then
      PS1=$PS1"\[$Colour_Bold\]$svn_rev\[$Colour_Off\]"
    fi

    if [ -n "$svn_status" ]; then
      PS1=$PS1'\['$Colour_BIRed'\]'"$svn_status"'\['$Colour_Off'\]'
    fi

    PS1=$PS1'\['"$box_colour"'\]]\[\033[m\]'
  else
    if [ -n "$git_output" ]; then

      PS1=$PS1'\['"$box_colour\][\[\033[m\]\[$Colour_Bold\]$git_branch"
      if [ -n "$git_flags" ]; then
        PS1=$PS1'\['$Colour_BIRed'\]'"$git_flags"'\['$Colour_Off'\]'
      fi

      PS1=$PS1'\['"$box_colour"'\]]\[\033[m\]'

    fi 
  fi
  
  # End
  case "$__RETURN_VALUE" in
  0)
    # Regular exit condition.
    PS1=$PS1"\\$ "
    ;;
  126)
    # Cyan text if we've tried to execute an unexecutable file or a directory.
    PS1=$PS1"\[$Colour_BICyan\]\\$ \[$Colour_Off\]"
    ;;
  127)
    # Yellow text if a command was not found
    PS1=$PS1"\[$Colour_BIYellow\]\\$ \[$Colour_Off\]"
    ;;
  *)
    # Colour the prompt character red if the command gave an exit code above 0 that was not previously matched.
    PS1=$PS1"\[$Colour_BIRed\]\\$ \[$Colour_Off\]"
    ;;
  esac


  # Tidy up variables
  unset __fs
}

__get_fs(){
    if __is_unix; then
        df -TP . 2> /dev/null | awk '{ print $2 }' | tail -n1
    else
        # Default to ext4 to make non-Unix green.
        printf "ext4"
    fi
}

__prompt_box_colour(){
    # Get a colour for the prompt box based on operating system hints.
    case "$(uname)" in
        Linux)
            printf "$Colour_BIBlue"
            ;;
        FreeBSD)
            printf "$Colour_BIRed"
            ;;
        Darwin)
            # Mac OSX
            printf "$Colour_BIYellow"
            ;;
        CYGWIN_NT*)
            # Cygwin (by way of MobaXterm)
            printf "$Colour_BICyan"
            ;;
        *)
            # Default to just "bold"
            printf "$Colour_Bold"
            ;;
    esac


}

# Adjust prompt directory colour based on its file system.
__prompt_file_system_colour(){
    # At the moment, __build_prompt also has a file system check.
    # Use that information if given instead of calculating the same thing twice.

    if [ -z "$__fs" ]; then
        local fs="$(__get_fs)"
    fi

    case "${__fs}" in
        cifs|nfs*)
            # Blue text
            # CIFS is a remote network file system.
            # NFS is also a remote network file system.
            printf "$Colour_BIBlue"
            ;;
        *fat*|ntfs*|udf|fuseblk)
            # Red Text.
            # FAT Filesystem most likely to be removable device.
            #     Lazy pattern assumes that no other family of file system will have 'fat' anywhere in it.
            # NTFS Filesystem on a Windows system are most likely to be removable device.
            # fuseblk filesystems are some variety of removable device.
            #     Late addition. After seeing an NTFS filesystem listed as 'fuseblk',
            #       I'm starting to second-guess if the 'ntfs*' clause is necessary.
            #       More double-checking necessary, eventually.
            # UDF Filesystem is most likely a mounted ISO or similar.
            printf "$Colour_BIRed"
            ;;
        *tmpfs*|sysfs|proc)
            # Purple Text.
            # Any variety of tmpfs should be purple text.
            # Sysfs file systems are a kernel construct.
            # Sysfs file systems are also a kernel construct.
            printf "$Colour_BIPurple"
            ;;
        "ext"*|xfs)
            # Green text.
            # Ext_ file systems most likely to be local drive.
            printf "$Colour_BIGreen"
            ;;
        *)
            # Return to default colour.
            printf "$Colour_Off"
            ;;
    esac
}

__prompt_hostname_colour (){
    # Colour hostname field.
    # REMINDER: Place specific hostnames BEFORE wildcard hostnames.
    case "$HOSTNAME" in
        old-laptop.*|laptop.*|keystone.*)
            # Desktop systems should be in green.
            printf "$Colour_BIGreen"
            ;;
        work-?*.domain.lan|*.work.lan|*.work.lan|*.sandbox.lan)
            # Work/Experimental systems should be in red.
            printf "$Colour_BIRed"
            ;;
        "keystone")
            # Windows systems should be in purple (for now).
            # Note: Windows!keystone's full hostname is just "keystone", unlike its Linux version
            printf "$Colour_BIPurple"
            ;;
        *.domain.lan|*.domain-b.lan)
            # Other local network machines should be in blue.
            printf "$Colour_BIBlue"
            ;;
        *)
            printf "$Colour_Off"
            ;;
    esac
}

__prompt_username_colour (){
    case "$(whoami)" in
        "redacted-username"|"redacted-name")
            printf "$Colour_BIBlue"
            ;;
        "root")
            printf "$Colour_BIRed"
            ;;
        *)
            printf "$Colour_Off"
            ;;
    esac
}

__prompt_ssh_origin (){
    if [ -n "$SSH_CLIENT" ]; then
        printf " from $(printf $SSH_CLIENT | cut -d' ' -f 1)"
    fi
}

# SVN Functions.
# Copyright (C) 2008 Eric Leblond
# 
# Version 0.4
# 
# subversion-prompt : Subversion aware bash prompt.
# To use it, add something like that to your .bashrc:
#    SVNP_HUGE_REPO_EXCLUDE_PATH="nufw-svn$|/tags$|/branches$"
#    . ~/bin/subversion-prompt
#    # set a fancy prompt
#    PS1='\u@\h:\w$(__svn_stat)\$ '
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Changelog :
#  2008-05-09: v0.4
#    Option to check distant status
#    Prefix env var by SVNP 
#  2008-05-08: v0.3, Use environnement variable
#  2008-05-08: v0.2, Add HUGE_REPO options
#  2008-05-08: v0.1, initial release
#

# Set environnement variable CHECK_DISTANT_REPO to 
# display if an updated is needed

# List of path to exclude from recursive status
# Explanation of following regexp:
# Exclude all directories under inl-svn, the nufw-svn directory, and
# all directories ending by /tags par /branches
# You can set it as environnement variable
if [ ! $SVNP_HUGE_REPO_EXCLUDE_PATH ]; then
    SVNP_HUGE_REPO_EXCLUDE_PATH="/tags$|/branches$"
fi

# Set SVNP_HAVE_HUGE_REPO if you have huge repository
# This will disable recursion when searching status
# and speed things a lot (but feature is less interessant).
# You can also look at the HUGE_REPO_EXCLUDE_PATH option

__svn_rev ()
{
    local output=$(LANG='C' svn info 2>/dev/null)
    local rev=$(awk '/Revision:/ {print $2; }' <<< "$output")

    # Re-assurance: Running this on a checkout made from
    #     an outdated SVN version will not yield a false positive.
    if [ -z "$rev" ] && [ -n "$output" ]; then
        # If there is no revision detected but svn did print to stdout,
        #     then the directory was recently added
        #     but has not yet been committed.
        local rev=NEW
    fi
    printf "$rev"
}

__svn_last_changed ()
{
    LANG='C' svn info 2>/dev/null | awk '/Last Changed Rev:/ { print $4;}'
}


__svn_clean ()
{
    if [ $SVNP_HAVE_HUGE_REPO ]; then
        HUGE_REPO=" -N ";
    else
        pwd | egrep -q $SVNP_HUGE_REPO_EXCLUDE_PATH && HUGE_REPO=" -N "
    fi
    STATE=$(LANG='C' svn $HUGE_REPO status -q 2>/dev/null | grep -c "^\s*[MAD]")
    if [ $STATE != 0 ]; then
        printf "$2"
    else
        printf "$1"
    fi

    unset STATE HUGE_REPO
}
__svn_remote_clean ()
{
    if [ $SVNP_HAVE_HUGE_REPO ]; then
        HUGE_REPO=" -N ";
    else
        pwd | egrep -q $SVNP_HUGE_REPO_EXCLUDE_PATH && HUGE_REPO=" -N "
    fi
    STATE=$(LANG='C' svn $HUGE_REPO status -u -q 2>/dev/null | egrep -c " *\*")
    if [ $STATE != 0 ]; then
        printf "$2"
    else
        printf "$1"
    fi

        unset STATE HUGE_REPO
}

__svn_stat (){

    # Ideally, we would consider an SVN checkout to exist by confirming the following:
    #  - At least ONE of the following is true
    #    - An .svn directory exists in the current working directory.
    #    - 'svn info' returns an error code of zero.
    #  - The 'svn' command is available (sort of a given since my functions are backed up to SVN, but just to be sure...)

    ### Be aware, SVN status lookups will significantly slow down working in a remote file system.
    ### This is especially true over a VPN link.

    # I've cut down the steps to just checking for the svn command being available.
    # Solution is experimental, but it seems that calling SVN an unnecessary number of times delayed things noticibly for smaller devices like a Pi.
    if qtype svn; then
        REV=$(__svn_rev)
    fi

        if [ -n "$REV" ]; then
            if [ $SVNP_CHECK_DISTANT_REPO ]; then
                REMOTE_STATUS=$(__svn_remote_clean "" "+")
            fi
            LOCAL_STATUS=$(__svn_clean "" "*")

            # Print output as a comma-separated list, which will be parsed by '__build_prompt' function.
            printf "$REMOTE_STATUS,$REV,$LOCAL_STATUS"
    fi

    unset REMOTE_STATUS REV LOCAL_STATUS
}


## Credit for original git-checking functions goes to http://ezprompt.net/
# get current branch in git repo
function __parse_git_branch() {
  local BRANCH=`git branch 2> /dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/\1/'`
  if [ -n  "${BRANCH}" ]; then
    local STAT=$(__parse_git_dirty)
    printf "${BRANCH},${STAT}\n"
  fi
}

# get current status of git repo
function __parse_git_dirty {
  local status=`git status 2>&1 | tee`
  local dirty=`grep -qm1 "modified:" <<< "${status}"; echo "$?"`
  local untracked=`grep -qm1 "Untracked files:" <<< "${status}"; echo "$?"`
  local ahead=`grep -qm1 "Your branch is ahead of" <<< "${status}"; echo "$?"`
  local newfile=`grep -qm1 "new file:" <<< "${status}"; echo "$?"`
  local renamed=`grep -qm1 "renamed:" &> /dev/null <<< "${status}"; echo "$?"`
  local deleted=`grep -qm1 "deleted:" <<< "${status}"; echo "$?"`

  if [ "${renamed}" == "0" ]; then
    local bits=">${bits}"
  fi
  if [ "${ahead}" == "0" ]; then
    local bits="*${bits}"
  fi
  if [ "${newfile}" == "0" ]; then
    local bits="+${bits}"
  fi
  if [ "${untracked}" == "0" ]; then
    local bits="?${bits}"
  fi
  if [ "${deleted}" == "0" ]; then
    local bits="x${bits}"
  fi
  if [ "${dirty}" == "0" ]; then
    # Dirty means that tracked files have been changed.
    local bits="!${bits}"
  fi
  if [ -n "${bits}" ]; then
    printf "${bits}"
  fi
}

# The flags output by __parse_git_dirty will take some getting used to.
# This function is a lazy way call up a quick reminder for myself.
# Will probably axe it, eventually.
git-prompt-reminder(){
  notice "$(printf "Git prompt flags: [(${Colour_Bold}>${Colour_Off}:renamed-elements)(${Colour_Bold}*${Colour_Off}:ahead)(${Colour_Bold}+${Colour_Off}:new-file)(${Colour_Bold}?${Colour_Off}:untracked-files)(${Colour_Bold}x${Colour_Off}:deleted-files)(${Colour_Bold}!${Colour_Off}:dirty)]")"
}
