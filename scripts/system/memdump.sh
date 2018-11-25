#!/bin/bash

# Dump a processes' memory.
# This script is validation wrapped around a concept introduced to me by A. Nilsson of ServerFault,
#   who in turn borrowed it from James Lawrie (Dolda2000 of LinuxForums.org).
# Source A: https://serverfault.com/questions/173999/dump-a-linux-processs-memory-to-file
# Source B: http://www.linuxforums.org/forum/programming-scripting/52375-reading-memory-other-processes.html#post287195

# Common message functions.

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

# Script content

if [ -z "$@" ]; then
  error "No PIDs specified in arguments."
  exit 1
elif ! type gdb 2> /dev/null >&2; then
  error "$(printf "Unable to find GNU Debugger (${BLUE}%s${NC})" "gdb")"
  exit 1
fi

for pid in $@; do

  map="/proc/${pid}/maps"

  if ! grep -Pq "^\d+$" <<< "${pid}"; then
    error "$(printf "Invalid PID: ${BOLD}%s${NC}" "${pid}")"
    continue
  elif [ ! -f "${map}" ]; then
    error "$(printf "Unable to find map file for process ${BOLD}%s${NC}: ${GREEN}%s${NC}" "${pid}" "${map}")"
    continue
  elif [ "$(stat -c "%u" "${map}")" -ne "${UID}" ] && (( "${EUID}" )); then
    # Because procfs is freaky, a BASH read check is not a reliable way of determining whether or not we can read a file.
    error "$(printf "Cannot read process ${BOLD}%d${NC}. It is owned by ${BOLD}%s${NC} (UID: ${BOLD}%d${NC}), and we are not ${RED}%s${NC}." "${pid}" "$(stat -c "%U" "${map}")" "$(stat -c "%u" "${map}")" "root")"
    continue
  fi

  dir="memdump-${pid}"
  mkdir "${dir}" || continue

  notice "$(printf "Dumping contents of process ${BOLD}%d${NC} to ${GREEN}%s${NC}." "${pid}" "${dir}")"

  while read start stop; do
    [ -z "$start" ] && continue
    gdb --batch --pid "${pid}" -ex "dump memory ${dir}/process-${pid}-$start-$stop-memory.dump 0x$start 0x$stop";
  done <<< "$(grep rw-p "${map}" | sed -n 's/^\([0-9a-f]*\)-\([0-9a-f]*\) .*$/\1 \2/p')"

  notice "$(printf "Finished dumping contents of process ${BOLD}%d${NC} to ${GREEN}%s${NC}." "${pid}" "${dir}")"
done

(( ${__error_count:-0} )) && exit 1 # Exit with error if at least one
exit 0
