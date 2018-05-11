
# Common message functions.

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  PURPLE='\033[1;95m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi

error(){
  printf "${RED}"'Error'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "${BLUE}"'Notice'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
}

success(){
  printf "${GREEN}"'Success'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __warning_count=$((${__warning:-0}+1))
}

# Need to get at an updater script in scripts/system/
DOTFILE_SCRIPT="$(readlink -f "$(dirname "$(readlink -f "${0}")")/../system/update-dotfile.sh")"

if ! (( ${IGNORE_DOTFILES:-0} )) && ! ( [ -f "${DOTFILE_SCRIPT}" ] && ( [ -n "${WINDIR}" ] || [ -x "${DOTFILE_SCRIPT}" ] ) ); then
  echo "${DOTFILE_SCRIPT}"
  error "$(printf "Dotfile update script not found or not runnable: ${GREEN}%s${NC}" "$(sed "s|^${HOME}|~|" <<< "${DOTFILE_SCRIPT}")")"
  exit 1
fi

# Get the path to the tools directory.
# Script is currently stored in 'scripts/setup/', relative to the root of the tools directory.
# No need to resolve the path with readlink.
toolsDir="$(readlink -f "$(dirname $0)/../..")"
