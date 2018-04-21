
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

question(){
  unset __response
  while [ -z "${__response}" ]; do
    printf "$PURPLE"'Question'"$NC"'['"$GREEN"'%s'"$NC"']: %s: ' "$(basename $0)" "${1}"
    [ -n "${2}" ] && local __o="-s"
    read ${__o} -p "" __response
    [ -n "${2}" ] && printf "\n"
    if [ -z "${__response}" ]; then
      error "Empty input."
      # Negate error increment, not a true error
      __error_count=$((${__error_count:-0}-1))
    fi
  done
}

success(){
  printf "${GREEN}"'Success'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __success_count=$((${__success_count:-0}+1))
}

warning(){
  printf "${YELLOW}"'Warning'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __warning_count=$((${__warning:-0}+1))
}
