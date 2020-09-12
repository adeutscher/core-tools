#!/bin/bash

# Common message functions.

set_colours(){
  # Define colours
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
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
  local a b c d ip
  ip="${1}"
  IFS=. read -r a b c d <<< "${ip}"
  printf '%d\n' "$((a * 256 ** 3 + b * 256 ** 2 + c * 256 + d))"
}

dec2ip(){
  local ip dec
  dec="${1}"
  for e in {3..0}
  do
    ((octet = dec / (256 ** e) ))
    ((dec -= octet * 256 ** e))
    ip+="${delim}${octet}"
    local delim=.
  done
  unset e octet dec
  printf '%s\n' "${ip}"
}

cidr_low(){
  # shellcheck disable=SC2059
  printf "$(dec2ip "$(cidr_low_dec "$1")")"
}

cidr_low_dec(){
  # Print the lowest usable address in a CIDR range.
  # Assumes valid input in one of the the following two formats:
  #   - 10.11.12.13/24
  #   - 10.11.12.13/255.255.255.0
  # Calculating netmask manually because ipcalc does not support
  #   calculating the minimum/maximum addresses in all distributions.

  local network
  network=$(cut -d'/' -f1 <<< "$1")
  local netmask
  netmask=$(cut -d'/' -f2 <<< "$1")

  local plus=1
  if grep -qP "255.255.255.255|32" <<< "$netmask"; then
    # /32 networks are single-host networks,
    #   wherein the network ID is the only usable address.
    local plus=0
  fi

  # shellcheck disable=SC2059
  printf "$(($(ip2dec "${network}")+plus))"
}

cidr_high(){
  # shellcheck disable=SC2059
  printf "$(dec2ip "$(cidr_high_dec "$1")")"
}

cidr_high_dec(){
  # Print the highest usable address in a CIDR range.
  # Assumes valid input in one of the the following two formats:
  #   - 10.11.12.13/24
  #   - 10.11.12.13/255.255.255.0
  # Calculating netmask manually because ipcalc does not support
  #   calculating the minimum/maximum addresses in all distributions.

  local network
  network="$(cut -d'/' -f1 <<< "$1")"
  local netmask
  netmask="$(cut -d'/' -f2 <<< "$1")"

  if ! grep -qP "^\d{1,}$" <<< "${netmask}"; then
    # Netmask was not in CIDR format.
    netmask=$(printf "%.$2f" "$(awk '{ print 32-log(4294967295-'"$(ip2dec "${netmask}")"')/log(2)}' <<< "")")
  fi

  # Subtract 2 for network id and broadcast addresss
  #   (unless we have a /32 address)
  local subtract
  subtract=2
  if [ "${netmask}" -eq "32" ]; then
    # /32 networks are single-host networks,
    #   wherein the network ID is the only usable address.
    subtract=0
  fi

  # shellcheck disable=2059
  printf $(($(ip2dec "${network}")+(2 ** (32-netmask))-subtract))
}

# Script Functions
##

get_data(){
  # Get data from different sources into a common format.
  # Example content of a BASIC line: 'tcp 192.168.0.1 192.168.0.2 12345 22 ESTABLISHED'
  if (( "${NETSTAT:-0}" )); then
    # Netstat

    BASIC="$(
    if (( "${STDIN:-0}" )); then
      cat -
    else
      netstat -tn 2> /dev/null
    fi | grep -P "^tcp6?\s" | grep -P '(([0-9]){1,3}\.){3}([0-9]{1,3})' | sed -e 's/:/ /g' -e 's/^tcp6/tcp/g' | awk '{print $1" "$4" "$6" "$5" "$7" "$8 }'
    )"
  else
    # Conntrack
    BASIC="$(
    if (( "${STDIN:-0}" )); then
      cat -
    else
      conntrack -L 2> /dev/null
    fi | grep -P "^tcp\s" | awk -F ' ' '{ print $1" "$5" "$6" "$7" "$8" "$4}' | sed -r -e 's/\s+[^=]+=/ /g')"
    LOCAL_ADDRESSES="$(ip a s | grep -Pwo "inet [^\/]+" | cut -d' ' -f2 | tr '\n' ' ' | sed -e 's/ $//')"
  fi

  awk -F' ' '
  BEGIN {
    using_netstat='"${NETSTAT:-0}"'
    display_incoming='"${INCOMING:-0}"'
    display_all='"${SHOW_ALL:-0}"'
    summarize='"${SUMMARIZE:-0}"'
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

    if(summarize)
      $4="0" # "From" port not used when summarizing.

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
    | sort -t' ' -k1,1n -k2,2n -k3,3n -k4,4n -k5,5n -k6,6n -k7,7n -k8,8n -k13,13n -k12,12n \
    | cut -d' ' -f9- | uniq -c | sed -r 's/^\s+//g'
}

get_interface_info(){
  # Get networks for interfaces
  local interface="${1}"
  local index="${2}"
  local networks
  if (( "${INTERFACE_RANGES:-0}" )); then
    networks="$(route -n | grep -P "^\d" | awk '{if($2=="0.0.0.0"){print $1"/"$3" "$8}}' | grep -w "${interface}" | cut -d' ' -f1 | sort | uniq | sed '/^169\.254/d')"
  else
    networks="$(ip a s "${interface}" | grep -Pwo "inet [^\/]+" | cut -d' ' -f2 | tr '\n' ' ' | sed -e 's/ $//')"
  fi
  local network_count
  network_count="$(wc -w <<< "$networks")"

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
  * Destination port number (e.g. 22).

Switches:
  -a: All-mode. When using conntrack, do not restrict to just our device's addresses. Address checks will look at both ends of connection for a match.
  -c: Conntrack-mode. Use conntrack instead of netstat to detect connections. Must be root to use.
  -C: Force colours, even if output is not a terminal.
  -D: Debug mode. Explicitply print out malformed output lines.
  -h: Help. Print this help menu and exit.
  -l: Show loopback connections, which are ignored by default. Will only work with netstat.
  -L: LAN-only mode. Only show incoming connections from LAN addresses (or to LAN addresses for outgoing mode).
  -m: Monitor mode. Constantly re-poll and print out connection information.
  -o: Outgoing mode. Display outgoing connections instead of incoming connections. Address checks will look at destination for a match.
  -p: Parseable mode. Display output in CSV format.
  -q: "Quiet"-ish mode: Print information in barebones format (probably for future parsing).
  -r: Range mode. When specifying interfaces as a filter, use local CIDR ranges instead of just IPv4 addresses.
  -R: Remote-only mode: Only show incoming connections from non-LAN addresses (or to non-LAN addresses for outgoing mode).
  -s: Separate mode. Do not summarize connections, displaying individual ports.
  -S: Standard input. Collect input from stdin, assumed to be valid netstat or conntrack output
  -v: Verbose mode. Reach out to getlabel script to attempt to resolve MAC addresses.
        '-vv' will call getlabel with -v for additional information.
EOF

  exit "${1:-0}"
}

is_in_cidr(){
  local addr="${1}"
  local cidr="${2}"

  addr_dec="$(ip2dec "${addr}")"
  [ "${addr_dec}" -ge "$(cidr_low_dec "${cidr}")" ] && [ "${addr_dec}" -le "$(cidr_high_dec "${cidr}")" ]
}

needs_label(){
  # Determines if a label has been printed for the given address.
  local _addr="${1//./_}"
  if [ -n "${_addr}" ] && ! grep -qw "${_addr}" <<< "${got_labeled}"; then
    got_labeled="${got_labeled} ${_addr}"
    return 0
  fi
  return 1
}

print_line(){
  # This is intended for normal output.
  # Note from development: This cannot be placed in a sub-shell.
  #[ -n "${QUIET}" ] || return 0

  if (( "${DO_CSV:-0}" )); then
    printf "%s,%s,%s,%d,%d\n" "${from}" "${to}" "${proto}" "${to_p}" "${count:-1}"
  elif (( "${SUMMARIZE:-0}" )); then
    message="$(printf "${GREEN}%s${NC} -> ${GREEN}%s${NC} (%s/%d" "${from}" "${to}" "${proto}" "${to_p}")"
    [ "${count:-0}" -gt 1 ] && message="${message}, ${count} connections"
    message="${message})"
    notice "${message}"
  else
    message="$(printf "${GREEN}%s:%d${NC} -> ${GREEN}%s:%d${NC} (${BOLD}%s${NC})" "${from}" "${from_p}" "${to}" "${to_p}" "${proto}")"
    notice "${message}"
  fi

  if (( "${1:-0}" )) && (( "${VERBOSE:-0}" )); then
    # shellcheck disable=SC2154
    getlabel "-${label_switches}l" "${last_from}"
  fi

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
STDIN=0

while [ -n "${1}" ]; do
  while getopts ":acCDhlLmoPqrRsSv" OPT "$@"; do
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
      D)
        DEBUG=1
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
      P)
        DO_CSV=1
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
      S)
        STDIN=1
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
    elif grep -Pq "^\d+$" <<< "${1}"; then
      [ "${1}" -ge 65536 ] && error "$(printf "Invalid port: ${BOLD}%s${NC}" "${1}")"
      IS_PORT[${ITEM_COUNT}]=1
    else
      error "$(printf "Invalid filter subject (not an address, range, interface, or port): ${BOLD}%s${NC}" "${1}")"
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

if (( "${STDIN:-0}" )); then
  (( "${MONITOR:-0}" )) && error "Monitor mode is incompatible with standard input mode."
else
  # stdin input is not enabled.
  if ! (( "${NETSTAT:-0}" )); then
    # Conntrack checking
    type conntrack 2> /dev/null >&2 || error "$(printf "${BLUE}%s${NC} command is not installed (${BOLD}%s${NC} package)." "conntrack" "conntrack-tools")"

    (( EUID )) && error "$(printf "Must be ${RED}%s${NC} to track connections via ${BLUE}%s${NC}." "root" "conntrack")"

  else
    # Netstat checking

    # That I have seen, netstat will only be unavailable by default on minimal CentOS-7 installations.
    type netstat 2> /dev/null >&2 || error "$(printf "${BLUE}%s${NC} command is not installed (${BOLD}%s${NC} package)." "netstat" "net-tools")"
  fi
fi # End STDIN check

if (( "${VERBOSE:-0}" )); then
  type getlabel 2> /dev/null >&2 || error "$(printf "${BLUE}%s${NC} command not found in PATH" "getlabel")"

  (( "${QUIET:-0}" )) && error "Quiet mode and verbose modes cannot be used at the same time."
fi

(( "${LAN_ONLY:-0}" )) && (( "${REMOTE_ONLY:-0}" )) && error "LAN-only and Remote-only modes cannot be used at the same time."

# Strictly speaking, All-Mode CAN be used with outgoing mode,
#   but All-Mode will take priority and maybe cause confusion.
(( "${SHOW_ALL:-0}" )) && ! (( "${INCOMING:-0}" )) && error "All-mode cannot be used with outgoing mode."

# Quit if any errors were output.
(( "${__error_count:-0}" )) && exit 1

if (( "${MONITOR:-0}" )); then
  # One-off monitor headings.

  DIRECTION_WORDING_A="Outgoing"
  DIRECTION_WORDING_B="to"
  if (( "${INCOMING:-0}" )); then
    DIRECTION_WORDING_A="Incoming"
    DIRECTION_WORDING_B="from"
  fi

  HEADER="$(printf "%s connections via ${BLUE}%s${NC} %s the following sources:" "${DIRECTION_WORDING_A}" "${METHOD}" "${DIRECTION_WORDING_B}")"
  (( "${ITEM_COUNT}" )) || HEADER="${HEADER//the following/all}"

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
      elif (( "${IS_PORT[${i}]}" )); then
        HEADER="$(printf "%s\n  - Port: ${BOLD}tcp/%s${NC}" "${HEADER}" "${ITEMS[${i}]}")"
      else
        HEADER="$(printf "%s\n  - ${RED}%s${NC}: ${BOLD}%s${NC}" "${HEADER}" "UNHANDLED" "${ITEMS[${i}]}")"
      fi
    done
  fi
fi

while (( 1 )); do
  # Reminder: If monitor mode is not set, then we will manually break out of the loop at the bottom.

  # Unset key loop variables
  unset count last_id CONTENT last_from illegal_format

  (( "${MONITOR:-0}" )) && CONTENT="$(printf "%s\n" "$(notice "${HEADER}")")"

  # Grab our data,
  # Restrict to "ESTABLISHED"-state connections for the time being.
  CONNECTIONS="$(get_data | grep "ESTABLISHED")"

  if [ -z "${CONNECTIONS}" ]; then
    if ! (( ${QUIET:-0} )) && ! (( "${NETSTAT:-0}" )); then
      # In non-quiet mode, empty netstat output is not note-worthy.
      CONTENT="$(printf "%s\n%s" "${CONTENT}" "$(notice "$(printf "No connections noted. Are you sure that there is a state-tracking rule in ${BLUE}%s${NC}?" "iptables")")")"
    fi
  fi

  while read -r connection; do
    [ -n "${connection}" ] || continue

    # Connection lines generated by get_data are of a standard format.
    # This makes it possible to easily search for illegal data.
    # Expected format of a connection line: proto src dst sport dport state
    # Content example of a connection line: tcp 10.20.30.40 20.30.40.50 43149 443 ESTABLISHED
    # Credit for advanced IPv4 Regex: https://www.regular-expressions.info/ip.html
    if ! grep -qP "\d+ tcp( (25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])){2}( \d+){2} [A-Z_0-9]+$" <<< "${connection}"; then
      illegal_format="$((${illegal_format:-0}+1))"
      if (( "${DEBUG:-0}" )); then
        error "$(printf "Illegally-formatted connection data from ${BLUE}%s${NC}: ${BOLD}%s${NC}" "${METHOD}" "${connection}")"
      fi
      continue
    fi

    count="$(cut -d' ' -f 1 <<< "${connection}")"
    proto="$(cut -d' ' -f 2 <<< "${connection}")"
    from="$(cut -d' ' -f 3 <<< "${connection}")"
    to="$(cut -d' ' -f 4 <<< "${connection}")"
    from_p="$(cut -d' ' -f 5 <<< "${connection}")"
    to_p="$(cut -d' ' -f 6 <<< "${connection}")"
    state="$(cut -d' ' -f 7 <<< "${connection}")"

    if (( "${SHOW_ALL:-0}" )); then
      subjects="${to} ${from}"
    elif (( "${INCOMING:-0}" )); then
      subjects="${from}"
    else
      subjects="${to}"
    fi

    if (( "${REMOTE_ONLY:-0}" )) || (( "${LAN_ONLY:-0}" )); then
    # Need to confirm if this is a LAN or remote connection.
      lan=0
      for subject in ${subjects}; do
        for range in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/24; do
          if is_in_cidr "${subject}" "${range}"; then
            lan="$((${lan:-0}+1))"
            break
          fi
        done
      done
      if ( (( "${REMOTE_ONLY:-0}" )) && ( ( (( "${SHOW_ALL:-0}" )) && [ "${lan}" -eq "2" ] ) || ( ! (( "${SHOW_ALL:-0}" )) && (( "${lan:-0}" )) ) ) ) \
      || ( (( "${LAN_ONLY:-0}" )) && [ "${lan}" -ne "$(wc -w <<< "${subjects}")" ] ); then
        # Non-reserved-range address in LAN-only or reserved-range address in remote-only.
        # In All-Mode, remote mode must include at least one observed address be a remote address
        #  (this script was made under the assumption that the user is managing some private-range hardware).
        # Outside of All-Mode, only one address is being inspected, and it must not be a remote address.
        # For LAN mode (whether in All-Mode or not), assuming a number of LAN addresses equal to the number of subjects.
        #  (i.e. incoming to a LAN address, outgoing to a LAN address, or LAN-LAN)
        # Skip
        continue
      fi
    fi # End Remote-Only/Lan-Only IF statement.

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
    if (( "${ITEM_COUNT:-0}" )); then
      # Process filters
      display=0
      for subject in ${subjects}; do
        item=0
        while [ "${item}" -lt "${ITEM_COUNT}" ] && (( ! display )); do
          item=$((item+1))
          if (( "${IS_ADDRESS[${item}]}" )); then
            # Filter option is an IPv4 address.
            [[ "${ITEMS[${item}]}" == "${subject}" ]] && display=1
          elif (( "${IS_CIDR[${item}]}" )); then
            # Filter option is an IPv4 CIDR address.
            is_in_cidr "${subject}" "${ITEMS[${item}]}" && display=1
          elif (( "${IS_PORT[${item}]}" )); then
            [ "${to_p}" -eq "${ITEMS[${item}]}" ] && display=1
          fi
        done # End inner item cycle for subject
        # Finish subject-for loop if we have already decided to display.
        (( display )) && break
      done # end Subject loop.
    fi

    (( "${display:-0}" )) || continue

    print_verbose=0
    needs_label "${from}" && print_verbose=1
    CONTENT="$(printf "%s\n%s" "${CONTENT}" "$(print_line "${print_verbose}")")"
    destinations="${destinations} ${to}"
    unset count

  done <<< "${CONNECTIONS}" # Reading into connections variable.

  if ! (( "${DO_CSV:-0}" )); then
    if (( "${VERBOSE:-0}" )); then
      # In verbose mode, track remaining unlabeled destinations to see if they can be labeled.
      for dst in ${destinations}; do
        if [ -n "${dst}" ] && needs_label "${dst}"; then
          LABEL_CONTENT="$(getlabel "-${label_switches}l" "${dst}")"
          if [ -n "${LABEL_CONTENT}" ]; then
            trailers="${trailers} ${dst}"
            TRAILER_CONTENT="$(printf "%s\n%s" "${TRAILER_CONTENT}" "${LABEL_CONTENT}")"
          fi
        fi
      done
      trailer_count="$(wc -w <<< "${trailers}")"
      if (( "${trailer_count}" )); then
        CONTENT="$(printf "%s\n%s\n%s" "${CONTENT}" "$(notice "$(printf "Additional labels for destinations: ${BOLD}%d${NC}" "${trailer_count}")")" "${TRAILER_CONTENT}")"
      fi
    fi

    if (( "${illegal_format:-0}" )); then
      CONTENT="$(printf "%s\n%s" "${CONTENT}" "$(error "$(printf "Lines of malformed ${BLUE}%s${NC} data: ${BOLD}%d${NC}" "${METHOD}" "${illegal_format}")")")"
      if (( "${STDIN:-0}" )); then
        # Standard input with bad data is the most likely suspect for bad formatting.
        # If we are using standard input, then give a more specific reminder.
        CONTENT="$(printf "%s\n%s" "${CONTENT}" "$(error "$(printf "Are you certain that the data from standard input is ${BLUE}%s${NC} output?" "${METHOD}")")")"
      fi
    fi
  fi # End DO_CSV check

  # Clear after we have built our output in monitor mode to reduce flicker.
  (( "${MONITOR:-0}" )) && clear

  # Print content, skipping empty lines (assumed to be headerspace in one-off listing).
  sed '/^$/d' <<< "${CONTENT}"

  if (( "${MONITOR:-0}" )); then
    sleep 1
  else
    # Non-monitor mode.
    if ! (( "${QUIET:-0}" )) && [ -n "${CONTENT}" ]; then
      # Print trailing newline.
      printf "\n"
    fi
    break # Break out of infinite monitor loop.
  fi
done # End infinite monitor loop.

# Exit with non-zero error message if illegally-formatted connections were read (implying bad input).
! (( "${illegal_format:-0}" )) || exit 1
