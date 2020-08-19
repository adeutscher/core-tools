#!/bin/bash

# Define colours
if [ -t 1 ]; then
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
fi

error(){
  printf "${RED}"'Error'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

network(){
  printf "${BLUE}"'Network'"${NC}"'['"${GREEN}"'%s'"${NC}"']: %s\n' "$(basename "${0}")" "${@}"
  __error_count=$((${__error_count:-0}+1))
}

# Script Functions

list_networks(){
  local iface
  iface=$1
  [ -z "${iface}" ] && return 1

  if (( "${EUID:-1}" )); then
    local _s="sudo"
  fi

  ${_s} iw dev "$iface" scan | tac | awk '
    BEGIN {
      defaultSecurity="OPEN";
      security=defaultSecurity;
      has_security=0;
      channel="??"
    }
    {
      if($1 == "BSS" && $2 != "Load:"){
        if(has_security && security == defaultSecurity){
          security="WEP"
        };
        print substr($2,0,17) " (" security ", channel " channel "): " ssid;

        bssid="";
        ssid="";
        channel="??";
        security=defaultSecurity;
        has_security=0;
      } else if ($1 == "SSID:" ){
        for(i = 2; i <= NF; i++){
          if(ssid){
            ssid=ssid " " $i
          } else {
            ssid=$i
          }
        }
      };

      if($1 == "capability:" && match($0,"Privacy")){
        has_security=1;
      };

      if($2 == "Authentication" && $5 == "802.1X" ){
        security=$5
      }

      if($1 == "RSN:"){
        if(security == "WPA1"){
          security=security " WPA2"
        } else if(security != defaultSecurity){
          security="WPA2 " security
        } else {
          security="WPA2"
        }
      } else if($1 == "WPA:"){
        security="WPA1"
      } else if ($2 == "primary" && $3 == "channel:"){
        channel=$4
      } else if($1" "$2" "$3" "$4 == "DS Parameter set: channel"){
        channel=$5
      }
    }' | sort -k2,2 -k1,1
}

wifi_list_raw(){

  # I made this function to cover the fact that scanning through nmcli doesn't print an access point's BSSID.
  # In addition, nmcli requires the NetworkManager service to be running in the first place in order to work.
  # It is a terrible awk one-liner, but it works for the moment.
  # NOTE: The output of scanning with `iw` is not considered to be stable by the developers maintaining it.
  #       This function may break over time.
  if [ -z "$1" ]; then
    error "Usage: wifi-list-raw interface [-vv]"
      return 1
  fi
  local iface=$1

  if ! iwconfig "$iface" 2> /dev/null | grep -q "IEEE"; then
    error "$(printf "Interface ${BOLD}%s${NC} not found or not a wireless interface..." "${iface}")"
    return 2
  fi

  if (( "${VERBOSE}" )); then
    list_networks "${iface}" | while read -r line; do
      [ -z "${line}" ] && continue

      network "${line}"

      local mac
      mac="$(cut -d' ' -f1 <<< "${line}")"
      getlabel "-l${VERBOSE_SWITCH}" "${mac}"
    done


  else
    list_networks "${iface}"
  fi
}

# Handle arguments
VERBOSE=0

while [ -n "${1}" ]; do
  while getopts ":v" OPT "$@"; do
    # Handle switches up until we encounter a non-switch option.
    case "$OPT" in
      v)
        VERBOSE="$((${VERBOSE:-0}+1))"
        unset VERBOSE_SWITCH
        if [ "${VERBOSE}" -gt 1 ]; then
          echo "A"
          # Add verbose switch onto getlabel.
          VERBOSE_SWITCH="v"
        fi
        ;;
      *)
        printf "Unhandled option: %s" "${OPT}"
        ;;
    esac
  done # getopts loop

  # Set ${1} to first operand, ${2} to second operands, etc.
  shift $((OPTIND - 1))
  while [ -n "${1}" ]; do
    # Break if the option began with a '-', going back to getopts phase.
    grep -q "^\-[^$]" <<< "${1}" && break

    # Do script-specific operand stuff here.
    [ -z "${INTERFACE}" ] && INTERFACE="${1}"

    shift # Shift to next variable.
  done # Operand ${1} loop.
done # Outer ${1} loop.

(( "${__error_count:-0}" )) && exit 1

wifi_list_raw "${INTERFACE}"
