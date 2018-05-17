#!/usr/bin/bash

# Common message functions.

set_colours(){
  # Define colours
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  PURPLE='\033[1;95m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
  grep -Pq c <<< "${label_switches}" || label_switches="${label_switches}c"
}
[ -t 1 ] && set_colours

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
  __warning_count=$((${__warning_count:-0}+1))
}

########################
# IP Address Functions #
########################

ip2dec(){
  local a b c d ip=$@
  IFS=. read -r a b c d <<< "$ip"
  printf '%d\n' "$((a * 256 ** 3 + b * 256 ** 2 + c * 256 + d))"
}

dec2ip(){
  local ip dec=$@
  for e in {3..0}
  do
    ((octet = dec / (256 ** e) ))
    ((dec -= octet * 256 ** e))
    ip+=$delim$octet
    local delim=.
  done
  unset e octet dec
  printf '%s\n' "$ip"
}

cidr_low(){
  printf $(dec2ip $(cidr-low-dec "$1"))
}

cidr_low_dec(){
  # Print the lowest usable address in a CIDR range.
  # Assumes valid input in one of the the following two formats:
  #   - 10.11.12.13/24
  #   - 10.11.12.13/255.255.255.0
  # Calculating netmask manually because ipcalc does not support
  #   calculating the minimum/maximum addresses in all distributions.

  local network=$(cut -d'/' -f1 <<< "$1")
  local netmask=$(cut -d'/' -f2 <<< "$1")

  local plus=1
  if grep -qP "255.255.255.255|32" <<< "$netmask"; then
    # /32 networks are single-host networks,
    #   wherein the network ID is the only usable address.
    local plus=0
  fi

  printf $(($(ip2dec "$network")+$plus))
}

cidr_high(){
  printf $(dec2ip $(cidr-high-dec "$1"))
}

cidr_high_dec(){
  # Print the highest usable address in a CIDR range.
  # Assumes valid input in one of the the following two formats:
  #   - 10.11.12.13/24
  #   - 10.11.12.13/255.255.255.0
  # Calculating netmask manually because ipcalc does not support
  #   calculating the minimum/maximum addresses in all distributions.

  local network=$(cut -d'/' -f1 <<< "$1")
  local netmask=$(cut -d'/' -f2 <<< "$1")

  if ! grep -qP "^\d{1,}$" <<< "$netmask"; then
    # Netmask was not in CIDR format.
    local netmask=$(printf %.$2f $(awk '{ print 32-log(4294967295-'"$(ip2dec "$netmask")"')/log(2)}' <<< ""))
  fi

  # Subtract 2 for network id and broadcast addresss
  #   (unless we have a /32 address)
  local subtract=2
  if [ "$netmask" -eq "32" ]; then
    # /32 networks are single-host networks,
    #   wherein the network ID is the only usable address.
    local subtract=0
  fi

  printf $(($(ip2dec "$network")+(2 ** (32-netmask))-$subtract))
}

# Script Functions
##

get_data(){
  # Get data from different sources into a common format.
  # Example content of a BASIC line: 'tcp 192.168.0.1 192.168.0.2 12345 22 ESTABLISHED'
  if (( "${NETSTAT:-0}" )); then
    # Netstat
    BASIC="$(netstat -tn 2> /dev/null | grep -P "^tcp\s" | sed 's/:/ /g' | awk '{print $1" "$4" "$6" "$5" "$7" "$8 }')"
  else
    # Conntrack
    BASIC="$(conntrack -L 2> /dev/null | grep -P "^tcp\s" | awk -F ' ' '{ print $1" "$5" "$6" "$7" "$8" "$4}' | sed -r -e 's/\s[^=]+=/ /g')"
    LOCAL_ADDRESSES="$(ip a s | grep -Pwo "inet [^\/]+" | cut -d' ' -f2 | tr '\n' ' ' | sed -e 's/ $//')"
  fi

  CONNECTIONS="$(awk -F' ' '
  BEGIN {
    using_netstat='"${NETSTAT:-0}"'
    display_incoming='"${INCOMING:-0}"'
    display_all='"${SHOW_ALL:-0}"'
    if(!using_netstat){
      raw_addresses="'"${LOCAL_ADDRESSES}"'"
      split(raw_addresses, addresses, " ")
    }
  }
  {
    # Get connections, arrange to have set source/dest locations, and sort.
    if($4 < $5){
      # "left-hand" side has a lower port, assumed to be server

      if(using_netstat && !(display_incoming || display_all))
        # Do not bother swapping if things will not be displayed.
        next

      # Swap ports
      temp=$4
      $4=$5
      $5=temp
      # Swap addresses
      temp=$2
      $2=$3
      $3=temp

    } else if(using_netstat && !(!display_incoming || display_all))
      next

    if(!(using_netstat || display_all)){
      target=$2
      if(display_incoming)
        target=$3
      contained=0
      if(!display_all){
        for(a in addresses){
          if(addresses[a] == target){
            contained=1
            break
          }
        }
      }
      if(!contained)
        next
    }


    # Place numbers for sorting.
    sourcenums = $2 " " $3;
    while(sub(/\./," ",sourcenums)){}

    print sourcenums " " $0 " " swap

  }' <<< "${BASIC}" \
    | sort -t' ' -k1,1n -k2,2n -k3,3n -k4,4n -k5,5n -k6,6n -k7,7n -k8,8n -k12,12n -k13,13n \
    | cut -d' ' -f9- | uniq
  )"
}

get_interface_info(){
  # Get networks for interfaces
  local interface="${1}"
  local index="${2}"
  if (( "${INTERFACE_RANGES:-0}" )); then
    local networks="$(route -n | grep -P "^\d" | awk '{if($2=="0.0.0.0"){print $1"/"$3" "$8}}' | grep -w "${interface}" | cut -d' ' -f1 | sort | uniq | sed '/^169\.254/d')"
  else
    local networks="$(ip a s "${interface}" | grep -Pwo "inet [^\/]+" | cut -d' ' -f2 | tr '\n' ' ' | sed -e 's/ $//')"
  fi
  local network_count=$(wc -w <<< "$networks")

  if [ "$network_count" -gt 0 ]; then
    for network in $networks; do
      # TODO, consider adjusting format from 192.168.0.0/255.255.255.0-ish (for example) to 192.168.0.0/24-ish.
      ITEM_COUNT="$((${ITEM_COUNT:-0}+1))"
      ITEMS[${ITEM_COUNT}]="${network}"
      if (( "${INTERFACE_RANGES:-0}" )); then
        IS_CIDR[${ITEM_COUNT}]=1
      else
        IS_ADDRESS[${ITEM_COUNT}]=1
      fi
    done
    unset network # Axe loop variable
    NETWORKS[${index}]="${networks}"
  else
    # Interface is not attached to any networks.
    # Check to see if it isn't a bridge member.
    bridge="$(brctl show 2> /dev/null | awk -F' ' '
    BEGIN {
      bridge="";
    }
    {
      if(NF == 4){
        bridge=$1;
        interface=$4;
      } else if(NF == 1){
        interface=$1
      }

      if(interface && interface == "'"${interface}"'"){
        print bridge;
        exit 0; # Interface will not be a member of two bridges.
      }
    }
    ')"

    if [ -n "${bridge}" ]; then
      get_interface_info "${bridge}" "${index}"
    else
      error "$(printf "${BOLD}%s${NC} is not attached to any networks." "${interface}")"
    fi
  fi
}

hexit(){

cat << EOF
Display active connection information.

Usage: ./connections.sh [-acChlLmoqrRsv] [matches]

By default, displays incoming connections. Use -o to display outgoing connections instead.

Specify matches to restrict output. For example, './connections.sh 192.168.0.0/24' would only show incoming connections from '192.168.0.0/24'. Switching to outgoing mode (-o) changes this to only display connections to matching subnets.

Valid matches:

  * Interface: Addresses used by an interface will be used (use -r to take the interfaces' routes).
               If a bridge member is added by accident, then the bridge can be detected.
  * IPv4 address (e.g. 192.168.0.1)
  * IPv4 CIDR range (e.g. 192.168.0.0/24)

Switches:
  -a: All-mode. When using conntrack, do not restrict to just our device's addresses.
  -c: Conntrack-mode. Use conntrack instead of netstat to detect connections. Must be root to use.
  -C: Force colours, even if output is not a terminal.
  -h: Help. Print this help menu and exit.
  -l: Show loopback connections, which are ignored by default. Will only work with netstat.
  -L: LAN-only mode. Only show incoming connections from LAN addresses (or to LAN addresses for outgoing mode).
  -m: Monitor mode. Constantly re-poll and print out connection information.
  -o: Outgoing mode. Display outgoing connections instead of incoming connections.
  -q: "Quiet"-ish mode: Print information in barebones format (probably for future parsing).
  -r: Range mode. When specifying interfaces as a filter, use local CIDR ranges instead of just IPv4 addresses.
  -R: Remote-only mode: Only show incoming connections from non-LAN addresses (or to non-LAN addresses for outgoing mode).
  -s: Separate mode. Do not summarize connections, displaying individual ports.
  -v: Verbose mode. Reach out to getlabel script to attempt to resolve MAC addresses.
EOF

  exit "${1:-0}"
}

is_in_cidr(){
  local addr="${1}"
  local cidr="${2}"

  addr_dec="$(ip2dec "${addr}")"
  [ "${addr_dec}" -ge "$(cidr_low_dec "${cidr}")" ] && [ "${addr_dec}" -le "$(cidr_high_dec "${cidr}")" ]
}

print_line(){
  # This is intended for normal output.
  [ -n "${last_from}${QUIET}" ] || return 0

  if (( "${SUMMARIZE:-0}" )); then
    message="$(printf "${GREEN}%s${NC} -> ${GREEN}%s${NC} (%s/%d" "${last_from}" "${last_to}" "${last_proto}" "${last_to_p}")"
    [ ${count:-0} -gt 1 ] && message="${message}, ${count} connections"
    message="${message})"
    notice "${message}"
  else
    message="$(printf "${GREEN}%s:%d${NC} -> ${GREEN}%s:%d${NC} (${BOLD}%s${NC})" "${last_from}" "${last_from_p}" "${last_to}" "${last_to_p}" "${last_proto}")"
    notice "${message}"
  fi

  (( "${VERBOSE:-0}" )) && getlabel -${label_switches}l "${last_from}"
}

# Script Operations
##

# Basic format regular expressions.
REGEX_IP4='^(([0-9]){1,3}\.){3}([0-9]{1,3})$'
REGEX_IP4_CIDR='^(([0-9]){1,3}\.){3}([0-9]{1,3})/((([0-9]){1,3}\.){3}([0-9]{1,3})|\d{1,2})$'

# Handle arguments
##

# Some default values.
# Most of these were originally implemented/phrased as 'toggle on' switches rather than 'toggle off'.
SUMMARIZE=1
NETSTAT=1
INCOMING=1

while [ -n "${1}" ]; do
  while getopts ":acChlLmoqrRsv" OPT $@; do
    case "${OPT}" in
      a)
        SHOW_ALL=1
        ;;
      c)
        NETSTAT=0
        ;;
      C)
        set_colours
        ;;
      h)
        hexit 0
        ;;
      l)
        LOCALHOST=1
        ;;
      L)
        LAN_ONLY=1
        ;;
      m)
        MONITOR=1
        ;;
      o)
        INCOMING=0
        ;;
      q)
        QUIET=1
        ;;
      r)
        INTERFACE_RANGES=1
        ;;
      R)
        REMOTE_ONLY=1
        ;;
      s)
        SUMMARIZE=0
        ;;
      v)
        VERBOSE="$((${VERBOSE:-0}+1))"
        [ "${VERBOSE:-0}" -eq 2 ] && label_switches="${label_switches}v"
        ;;
      *)
        error "$(printf "Unhandled option: ${BOLD}%s${NC}" "${OPT}")"
        ;;
    esac
  done

  # Set $1 to first operand, $2 to second operands, etc.
  shift $((OPTIND - 1))

  # Validate operands
  while [ -n "${1}" ]; do
    grep -q "^\-" <<< "${1}" && break
    ITEM_COUNT="$((${ITEM_COUNT:-0}+1))"
    FILTER_COUNT="$((${FILTER_COUNT:-0}+1))"

    ITEMS[${ITEM_COUNT}]="${1}"
    if grep -Pq "${REGEX_IP4}" <<< "${1}"; then
      IS_ADDRESS[${ITEM_COUNT}]=1
    elif grep -Pq "${REGEX_IP4_CIDR}" <<< "${1}"; then
      IS_CIDR[${ITEM_COUNT}]=1
    elif ip a s "${1}" 2> /dev/null >&2; then
      IS_INTERFACE[${ITEM_COUNT}]=1
    else
      error "$(printf "Invalid address(es)/interface: ${BOLD}%s${NC}" "${1}")"
    fi
    shift
  done
done

# All interfaces must have at least one network range.
while [ "${i:-0}" -lt "${ITEM_COUNT:-0}" ]; do
  i="$((${i:-0}+1))"
  (( ${IS_INTERFACE[${i}]:-0} )) || continue
  interface="${ITEMS[${i}]}"
  get_interface_info "${interface}" "${i}"
done

# Set method label.
METHOD="netstat"
(( "${NETSTAT:-0}" )) || METHOD="conntrack"

# Handling other argument errors.

if ! (( "${NETSTAT:-0}" )); then
  # Conntrack checking
  type conntrack 2> /dev/null >&2 || error "$(printf "${BLUE}%s${NC} command is not installed (${BOLD}%s${NC} package)." "conntrack" "conntrack-tools")"

  (( ${EUID} )) && error "$(printf "Must be ${RED}%s${NC} to track connections via ${BLUE}%s${NC}." "root" "conntrack")"

  (( "${LOCALHOST:-0}" )) && error "$(printf "Localhost mode (-l) is incompatible with ${BLUE}%s${NC} mode." "${METHOD}")"
fi

if (( "${VERBOSE:-0}" )); then
  type getlabel 2> /dev/null >&2 || error "$(printf "${BLUE}%s${NC} command not found in PATH" "getlabel")"

  (( "${QUIET:-0}" )) && error "Quiet mode and verbose modes cannot be used at the same time."
fi

(( "${LAN_ONLY:-0}" )) && (( "${REMOTE_ONLY:-0}" )) && error "LAN-only and Remote-only modes cannot be used at the same time."

# Quit if any errors were output.
(( "${__error_count:-0}" )) && exit 1

if (( "${MONITOR:-0}" )); then
  # One-off monitor headings.

  DIRECTION_WORDING_A="Outgoing"
  DIRECTION_WORDING_B="from"
  if (( "${INCOMING:-0}" )); then
    DIRECTION_WORDING_A="Incoming"
    DIRECTION_WORDING_B="to"
  fi

  HEADER="$(printf "%s connections via ${BLUE}%s${NC} %s the following sources:" "${DIRECTION_WORDING_A}" "${METHOD}" "${DIRECTION_WORDING_B}")"
  (( "${ITEM_COUNT}" )) || HEADER="$(sed 's/the following/all/' <<< "${HEADER}")"

  if (( "${ITEM_COUNT}" )); then
    i=0;
    while [ "${i}" -lt "${FILTER_COUNT}" ]; do
      i="$((${i:-0}+1))"
      if (( "${IS_CIDR[${i}]}" )); then
        HEADER="$(printf "%s\n  - CIDR Range: ${GREEN}%s${NC}" "${HEADER}" "${ITEMS[${i}]}")"
      elif (( "${IS_ADDRESS[${i}]}" )); then
        HEADER="$(printf "%s\n  - IPv4 Address: ${GREEN}%s${NC}" "${HEADER}" "${ITEMS[${i}]}")"
      elif (( "${IS_INTERFACE[${i}]}" )); then
        HEADER="$(printf "%s\n  - Interface: ${BOLD}%s${NC} (${GREEN}%s${NC})" "${HEADER}" "${ITEMS[${i}]}" "${NETWORKS[${i}]}")"
      else
        HEADER="$(printf "%s\n  - ${RED}%s${NC}: ${BOLD}%s${NC}" "${HEADER}" "UNHANDLED" "${ITEMS[${i}]}")"
      fi
    done
  fi
fi

while (( 1 )); do
  # Reminder: If monitor mode is not set, then we will manually break out of the loop at the bottom.

  # Unset key loop variables
  unset count
  unset last_id

  (( "${MONITOR:-0}" )) && CONTENT="$(printf "%s\n" "$(notice "${HEADER}")")"

  # Grab our data,
  get_data

  TARGET=2 # Default target, match against "from"
  (( "${INCOMING:-0}" )) && TARGET="3" # If -i, match against "to"
  if [ -n "${CONNECTIONS}" ]; then
    while read connection; do
      [ -n "${connection}" ] || continue

      proto="$(cut -d' ' -f 1 <<< "${connection}")"
      from="$(cut -d' ' -f 2 <<< "${connection}")"
      to="$(cut -d' ' -f 3 <<< "${connection}")"
      from_p="$(cut -d' ' -f 4 <<< "${connection}")"
      to_p="$(cut -d' ' -f 5 <<< "${connection}")"
      state="$(cut -d' ' -f 6 <<< "${connection}")"

      # Restrict to "ESTABLISHED"-state connections for the time being.
      [[ "${state}" == "ESTABLISHED" ]] || continue

      if (( "${REMOTE_ONLY:-0}" )) || (( "${LAN_ONLY:-0}" )); then
        # Need to confirm if this is a LAN or remote connection.
        lan=0
        subject="${to}"
        (( "${INCOMING:-0}" )) && subject="${from}"
        for range in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/24; do
           if is_in_cidr "${subject}" "${range}"; then
             lan=1
             break
           fi
        done
        if ( (( "${REMOTE_ONLY:-0}" )) && (( "${lan}" )) ) \
        || ( (( "${LAN_ONLY:-0}" )) && ! (( "${lan}" )) ); then
          # Non-reserved-range address in LAN-only or reserved-range address in remote-only.
          # Skip
          continue
        fi
      fi

      if ! (( "${SHOW_ALL:-0}" )) && is_in_cidr "${from}" "127.0.0.0/8"; then
        # From loopback address. Skip if loopback setting not enabled.
        (( "${LOCALHOST:-0}" )) || continue
      else
        # Non-loopback address. Skip if loopback setting enabled.
        (( "${LOCALHOST:-0}" )) && continue
      fi

      if (( "${QUIET:-0}" )); then
        echo "${connection}"
        continue
      fi

      id="${proto}.${from}>${to}:${to_p}"

      display=1
      item=0
      if (( "${ITEM_COUNT:-0}" )); then
        display=0
        while [ "${item}" -le "${ITEM_COUNT}" ]; do
          item="$((${item}+1))"
          if (( "${IS_ADDRESS[${item}]}" )); then
            # Filter option is an IPv4 address.
            if [[ "${ITEMS[${item}]}" == "$(cut -d' ' -f "${TARGET}" <<< "${connection}")" ]]; then
              display=1
              break
            fi
          elif (( "${IS_CIDR[${item}]}" )); then
            # Filter option is an IPv4 CIDR address.
            subject="$(cut -d' ' -f "${TARGET:-2}" <<< "${connection}")"
            is_in_cidr "${subject}" "${ITEMS[${item}]}" || continue
            display=1
            break
          fi
        done
      fi

      (( "${display:-0}" )) || continue

      if ! (( ${SUMMARIZE:-0} )) || ( [ -n "${last_id}" ] && [[ "${id}" != "${last_id}" ]] ); then
        CONTENT="$(printf "%s\n%s" "${CONTENT}" "$(print_line)")"
        unset count
      fi

      count="$((${count:-0}+1))"
      last_id="${id}"
      last_proto="${proto}"
      last_from="${from}"
      last_to="${to}"
      last_to_p="${to_p}"
      last_from_p="${from_p}"

    done <<<  "${CONNECTIONS}"
    (( ${SUMMARIZE:-0} )) && ! (( "${QUIET:-0}" )) && CONTENT="$(printf "%s\n%s" "${CONTENT}" "$(print_line)")"

    # Clear after we have built our output in monitor mode to reduce flicker.
    (( "${MONITOR:-0}" )) && clear

    # Print content, skipping empty lines (assumed to be headerspace in one-off listing).
    printf "${CONTENT}" | sed '/^$/d'
    unset CONTENT
  elif ! (( ${QUIET:-0} )) && ! (( "${NETSTAT:-0}" )); then
    # In non-quiet mode, empty netstat output is not note-worthy.
    notice "$(printf "No connections noted. Are you sure that there is a state-tracking rule in ${BLUE}%s${NC}?" "iptables")"
  fi

  if (( "${MONITOR:-0}" )); then
    sleep 1
  else
    if ! (( "${QUIET:-0}" )) && [ -n "${CONNECTIONS}" ]; then
      # Print trailing newline.
      printf "\n"
    fi
    break
  fi
done

