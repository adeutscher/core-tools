#!/bin/bash

# Common message functions.

# Define colours
colours_on(){
  BLUE='\033[1;34m'
  GREEN='\033[1;32m'
  RED='\033[1;31m'
  YELLOW='\033[1;93m'
  PURPLE='\033[1;95m'
  BOLD='\033[1m'
  NC='\033[0m' # No Color
}
[ -t 1 ] && colours_on

error(){
  printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
  __error_count=$((${__error_count:-0}+1))
}

notice(){
  printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
}

record(){
  printf "$GREEN"'Record'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
  __record_count=$((${__record_count:-0}+1))
}

self(){
  printf "$BLUE"'Self'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
}

summary(){
  printf "$PURPLE"'Summary'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
}

unknown(){
  printf "$RED"'Unknown'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
  __unknown_count=$((${__unknown_count:-0}+1))
}

warning(){
  printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename "${0}")" "$@"
  __warning_count=$((${__warning_count:-0}+1))
}

########################
# IP Address Functions #
########################

ip2dec(){
  local a b c d ip
  ip="$*"
  IFS=. read -r a b c d <<< "$ip"
  printf '%d\n' "$((a * 256 ** 3 + b * 256 ** 2 + c * 256 + d))"
}

dec2ip(){
  local ip dec
  dec="$*"
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

is_in_cidr(){
  local addr="${1}"
  local cidr="${2}"

  addr_dec="$(ip2dec "${addr}")"
  [ "${addr_dec}" -ge "$(cidr-low-dec "${cidr}")" ] && [ "${addr_dec}" -le "$(cidr-high-dec "${cidr}")" ]
}
cidr-low(){
  dec2ip "$(cidr-low-dec "$1")"
}

cidr-low-dec(){
  # Print the lowest usable address in a CIDR range.
  # Assumes valid input in one of the the following two formats:
  #   - 10.11.12.13/24
  #   - 10.11.12.13/255.255.255
  # Calculating netmask manually because ipcalc does not support
  #   calculating the minimum/maximum addresses in all distributions.

  local network
  local netmask

  network=$(cut -d'/' -f1 <<< "$1")
  netmask=$(cut -d'/' -f2 <<< "$1")

  local plus
  plus=1
  if grep -qP "255.255.255.255|32" <<< "$netmask"; then
    # /32 networks are single-host networks,
    #   wherein the network ID is the only usable address.
    local plus=0
  fi

  #shellcheck disable=SC2059
  printf $(($(ip2dec "$network")+plus))
}

cidr-high(){
  dec2ip "$(cidr-high-dec "$1")"
}

cidr-high-dec(){
  # Print the highest usable address in a CIDR range.
  # Assumes valid input in one of the the following two formats:
  #   - 10.11.12.13/24
  #   - 10.11.12.13/255.255.255
  # Calculating netmask manually because ipcalc does not support
  #   calculating the minimum/maximum addresses in all distributions.

  local network
  local netmask
  network=$(cut -d'/' -f1 <<< "$1")
  netmask=$(cut -d'/' -f2 <<< "$1")

  if ! grep -qP "^\d{1,}$" <<< "$netmask"; then
    # Netmask was not in CIDR format.
    netmask=$(printf "%.$2f" "$(awk '{ print 32-log(4294967295-'"$(ip2dec "$netmask")"')/log(2)}' <<< "")")
  fi

  # Subtract 2 for network id and broadcast addresss
  #   (unless we have a /32 address)
  local subtract
  subtract=2
  if [ "$netmask" -eq "32" ]; then
    # /32 networks are single-host networks,
    #   wherein the network ID is the only usable address.
    subtract=0
  fi

  #shellcheck disable=SC2059
  printf $(($(ip2dec "${network}")+(2 ** (32-netmask))-subtract))
}

cidr2mask(){
  # Convert short-form CIDR notation to a full-form subnet mask.
  local _mmask
  local _t
  _mmask="$((32-${1}))"

  while [ "${_mmask}" -lt 32 ]; do
    _t="$((${_t:-0}+2**_mmask))"
    _mmask="$((_mmask + 1))"
  done
  dec2ip "${_t}"
}

mask2cidr(){
  # Convert a full-form subnet mask to short-form CIDR notation.
  local _cmask
  local _mmask
  local _rmask

  _cmask=$(ip2dec "${1}")
  _mmask="$(ip2dec 255.255.255.255)"
  _rmask=0

  while [ "${_cmask}" -lt "${_mmask}" ]; do
    _cmask=$((_cmask+2**_rmask))
    _rmask="$((_rmask+1))"
  done
  echo "$((32 - _rmask))"
}

# Environment Checking

if [ -n "$WINDIR" ]; then
  error "This script was only meant to work on a Unix system."
  exit 1
else
  # shellcheck disable=SC2043
  for i in toolsCache; do
    if [ -z "$(eval "echo \"\${$i}\"")" ]; then
      error "$(printf "${BOLD}%s${NC} variable not set. Try running ${BLUE}%s${NC}..." "$i" "reload")"
      exit 1
    fi
  done
fi

cacheFile="${INDEX_NETWORK_CACHE:-$toolsCache/network-index.csv}"
dataFile="${INDEX_NETWORK_DATA}"

vendorCacheFile="${INDEX_VENDOR_CACHE:-$toolsCache/vendor-mac.psv}"
vendorDataFile="${INDEX_VENDOR_DATA}"

if [ -n "${vendorDataFile}" ] && ! [ -f "${vendorDataFile}" ]; then
  # Display an error if no vendor file was found. Not exit-worthy, though.
  error "$(printf "Vendor data file not found: ${GREEN}%s${NC}" "$vendorDataFile")"
fi

if [ -z "${dataFile}" ]; then
  error "No data file defined. Set INDEX_NETWORK_DATA variable, and see help menu for file format."
  exit 1
elif [ ! -f "$dataFile" ]; then
  error "$(printf "Data file not found: ${GREEN}%s${NC}" "$dataFile")"
  exit 1
fi

# Data Scraping Functions

# Look in a data file defined in INDEX_NETWORK_DATA environment variable to try to resolve MAC addresses to a record.
# If the file doesn't exist or there is no entry, print nothing and let above logic handle it.
__get_mac_record(){
  if [ -n "$1" ] && [ -f "$dataFile" ]; then
    grep -Pim1 "^([^,]*,){2}$1," "$cacheFile" 2> /dev/null || grep -Pim1 "^([^,]*,){2}$1," "$dataFile" 2> /dev/null | tee -a "$cacheFile"
  fi
}

__get_mac_description(){
  if [ -n "$1" ]; then
    __get_mac_record "$1" | cut -d',' -f 7
  fi
}

__get_mac_label(){
  if [ -n "$1" ]; then
    __get_mac_record "$1" | cut -d',' -f 4
  fi
}

__get_mac_general_location(){
  if [ -n "$1" ]; then
    __get_mac_record "$1" | cut -d',' -f 5
  fi
}

__get_mac_notes(){
  if [ -n "$1" ]; then
    __get_mac_record "$1" | cut -d',' -f 8
  fi
}

__get_mac_specific_location(){
  if [ -n "$1" ]; then
    __get_mac_record "$1" | cut -d',' -f 6
  fi
}

__get_mac_owner(){
  if [ -n "$1" ]; then
    __get_mac_record "$1" | cut -d',' -f 1
  fi
}

__get_mac_type(){
  if [ -n "$1" ]; then
    __get_mac_record "$1" | cut -d',' -f 2
  fi
}

__get_mac_vendor_inner(){
  if [ -n "$1" ] && [ -f "$vendorDataFile" ]; then
    grep -im1 "^${1:0:8}" "$vendorCacheFile" 2> /dev/null ||  grep -im1 "^${1:0:8}" "$vendorDataFile" | tee -a "$vendorCacheFile" 2> /dev/null
  fi
}

__get_mac_vendor(){
  __get_mac_vendor_inner "$1" | cut -d'|' -f 2
}

__get_mac_from_ip_address(){
  # Search ARP table for an IP address entry.
  # Given its own function since I call on it in multiple places.
  if [ -z "$WINDIR" ]; then
    # Unix system
    arp -an 2> /dev/null | grep -vP "(^Address)|incomplete" | grep -m1 "${1//./\\.})" | cut -d' ' -f 4
  else
    # MobaXterm grep doesn't seem to care about being fed in a string with literal '.' characters.
    # Doesn't treat them as wildcards like Unix. Strange.
    arp -a 2> /dev/null | grep -vP "(^Address)|incomplete" | grep -m1 "[^\.0-9]$1[^\.0-9]" | awk '{print $2}' | sed 's/-/:/g'
  fi
}

# Main Label-Grabbing Functions
#

getlabel(){

  local mac
  local address
  local network
  local networks
  local netmask
  local count

  local statement

  location="${1}"
  if grep -Pq '^(([0-9]){1,3}\.){3}([0-9]{1,3})/((([0-9]){1,3}\.){3}([0-9]{1,3})|\d{1,2})$' <<< "$location"; then
    # CIDR Address

    network=$(cut -d'/' -f1 <<< "$location")
    netmask=$(cut -d'/' -f2 <<< "$location")

    if ! type nmap 2> /dev/null >&2; then
      warning "$(printf "This function leans heavily on ${BLUE}%s${NC} when given a network range!" "nmap")"
      warning "$(printf "${BLUE}%s${NC} is not installed, so we will make due with existing ARP entries." "nmap")"
    fi

    # User gave a network range.
    # Assuming valid input.
    # Input format is either like "10.20.30.0/24" or "10.20.30.0/255.255.255.0".

    local low
    low=$(cidr-low-dec "${location}")
    local high
    high=$(cidr-high-dec "${location}")

    # Determine if the low end is within one of our routes.
    count=0

    local __low_is_in
    local __high_is_in

    __low_is_in=0
    __high_is_in=0

    # Exclude tun networks from consideration.
    for range in $(route -n | grep -v 'tun' | awk '{if ($2 == "0.0.0.0"){ print $1"/"$3 }}'); do
      __current_low=$(cidr-low-dec "$range")
      __current_high=$(cidr-high-dec "$range")

      count=$((count+1))

      if [ "$low" -ge "$__current_low" ] && [ "$low" -le "$__current_high" ]; then
        if [ "$__low_is_in" -eq 0 ]; then
          __low_is_in=$count
        fi
      fi

      if [ "$high" -ge "$__current_low" ] && [ "$high" -le "$__current_high" ]; then
        if [ "$__high_is_in" -eq 0 ]; then
          __high_is_in=$count
        fi
      fi

      if [ "$__low_is_in" -eq "$count" ] || [ "$__high_is_in" -eq "$count" ]; then
        if [ -n "$statement" ]; then
          statement="$statement&&((ipAsDec>=$__current_low)&&(ipAsDec<=$__current_high))"
        else
          statement="((ipAsDec>=$__current_low)&&(ipAsDec<=$__current_high))"
        fi
      fi
    done

    # Axe loop variable.
    unset range

    if [ 0 -eq "$__low_is_in" ] && [ 0 -eq "$__high_is_in" ]; then
      if ! (( "${lazy:-0}" )); then
        error "$(printf "We do not appear to have any local routes that include any part of ${GREEN}%s${NC}." "$location")"
        error "Look-ups are based on MAC addresses, so if we are not on the same collision domain every lookup will crash and burn."
      fi

      # Exit out. One way or the other, not having an address on this network will mess us up:
      #   - If we aren not directly on the local network, MAC lookups in getlabel will flop.
      #   - If our interface is on the home network but with no address, nmap will flop.
      #     This an edge case that we could counter by making our own list (which would make for longer lookups),
      #        but leaving it unanswered for the moment.
      #     On the flip side, no address probably means no ARP entries as well.
      return 3
    elif [ "$__low_is_in" -ne "$__high_is_in" ]; then
      # If we had two subnets right next to each other
      #   (e.g. 10.0.0.0/24 and 10.0.1.0/24), this message would *technically* be useless
      # Detecting this wacky edge case for the sake of a different warning is NOT worth it.
      if ! (( "${lazy:-0}" )); then
        warning "$(printf "The ${GREEN}%s${NC} network is partly outside of any of our local routes." "$location")"
        warning "Continuing with the our lookup for what we can find, but expect delays."
      fi
    fi
    # If __low_is_in == __high_is_in, then no need for any warnings.

    if ! (( "${lazy:-0}" )) && type nmap 2> /dev/null >&2; then
      # Run nmap for entries, then also check arp to see if there were any hosts that did not respond to nmap's ping scan.

      local network_id
      network_id="$(cut -d'/' -f1 <<< "$location")"
      local network_mask
      network_mask="$(cut -d'/' -f2 <<< "$location")"

      if ! grep -qP "^\d+$" <<< "${network_mask}"; then
        # The network size was not specified in CIDR short-form.
        # e.g. 192.168.0.0/255.255.255.0
        network_mask=$(mask2cidr "${network_mask}")
      fi
      notice "$(printf "Scanning ${GREEN}%s${NC} (${BOLD}%d${NC} addresses to try from ${GREEN}%s${NC} to ${GREEN}%s${NC}) for ARP entries..." "${network_id}/${network_mask}" "$((high-low+1))" "$(cidr-low "${location}")" "$(cidr-high "${location}")")"

      local nmap_address_list
      nmap_address_list="$(nmap -n -T5 -sn "${network_id}/${network_mask}" | grep 'Nmap scan report' | cut -d' ' -f 5)"
    elif ! (( "${lazy:-0}" )); then
      notice "$(printf "Looking for ARP entries in ${GREEN}%s${NC} (${BOLD}%d${NC} addresses to try from ${GREEN}%s${NC} to ${GREEN}%s${NC})" "$location" "$((high-low+1))" "$(cidr-low "${location}")" "$(cidr-high "${location}")")"
    fi

    local arp_address_list
    arp_address_list=$(arp -n | grep -vP "(^Address)|incomplete" | awk 'function ip2dec(ip){split(ip,octets,"."); return octets[1] * 256^3 + octets[2] * 256^2 + octets[3] * 256 + octets[4]} {ipAsDec=ip2dec($1); if('"${statement}"'){print $1}}');

    arp -n | grep -vP "(^Address)|incomplete" | awk 'function ip2dec(ip){split(ip,octets,"."); return octets[1] * 256^3 + octets[2] * 256^2 + octets[3] * 256 + octets[4]} {i=ip2dec($1); if('"${statement}"'){print $1}}'
    # Merge our two lists into one. 99% sure that the nmap list would be a subset of the arp list, though...
    local total_address_list
    # shellcheck disable=SC2001
    total_address_list="$(sed 's/ /\n/g' <<< "${nmap_address_list} ${arp_address_list}" | sort -nu -t'.' -k1n,1n -k 2n,2n -k 3n,3n -k 4n,4n)"
    count="$(wc -w <<< "$total_address_list")"

    # Silly branching for plural
    if [ "$count" -gt 1 ]; then
      notice "$(printf "Scan complete (%d records). Searching records..." "$count")"
    elif [ "$count" -eq 0 ]; then
      # Found nothing. Somehow...
      notice "$(printf "No records found by either your scan or your machine's ARP table. How did you manage that?")"
    else
      # 1 record
      notice "$(printf "Scan complete (%d record, and it's probably our own device). Searching record..." "$count")"
    fi

    local current_address
    for current_address in ${total_address_list}; do
      getlabel "${current_address}"
    done

    return

  elif grep -iPq '^[a-f0-9]{2}([:|-][a-f0-9]{2}){2,5}$' <<< "$location"; then
    # Provided location was a MAC address or similar.
    # Treating any MAC address-like sequence with at least three digit groups as a MAC address.

    # Format dashes out in case someone pasted in a Windows-style formatting
    # shellcheck disable=SC2001
    mac="$(sed -e 's/\(.*\)/\L\1/' <<< "${location//-/:/}")"
  else

    # Provided location was not already a MAC address or a network range.
    if ! grep -Pq '^(([0-9]){1,3}\.){3}([0-9]{1,3})$' <<< "$location"; then
      # Provided location not an IP address format,
      #     so start by trying to resolve it as a hostname.
      if ! type host 2> /dev/null >&2; then
        (( "${lazy:-0}" )) || error "$(printf "${BLUE}%s${NC} command not found! Please install bind utilities..." "host")"
        return 2;
      fi

      address="$(host "$location" | grep -m1 "has address" | cut -d' ' -f 4)"

      # Confirm that we were actually able to get an IP address.
      if ! grep -Pq '^(([0-9]){1,3}\.){3}([0-9]{1,3})$' <<< "$address"; then
        error "$(printf "Unable to resolve the hostname ${GREEN}%s${NC}" "$location")"
        return 3
      else
        notice "$(printf "Resolved hostname of ${GREEN}%s${NC} to ${GREEN}%s${NC}." "$location" "$address")"
      fi

    else # IP address format else
      # Provided address already is an IP address.
      address="${location}"
    fi # end IP address format check

    if [ -z "$WINDIR" ]; then
      if ip a s | grep -Pq "inet\s${address//./\\.}\/"; then
        # Unix machine

        # The calls are coming from inside the house!
        self "$(printf "${GREEN}%s${NC} looks like it is held by the machine running this script." "$address")"
        # Not considering this an error at this time, so return code is for all clear.
        return 0
      fi

      networks="$(route -n | sed -r '/(tun|tap)[0-9]{1,}/d' | grep -P "^\d" | awk '{if($2=="0.0.0.0"){print $1"/"$3" "$8}}' | cut -d' ' -f1 | sort | uniq | sed '/^169\.254/d')"
      local present=0
      for network in ${networks}; do
        is_in_cidr "${address}" "${network}" && present=1 && break
      done

      if ! (( "${present}" )); then
        (( "${lazy:-0}" )) || error "$(printf "Address does not appear to be in one of our local network ranges: ${GREEN}%s${NC}" "${address}")"
        return 1
      fi
    else
      # Adapted for MobaXterm
      if ipconfig | grep IPv4 | cut -d':' -f2 | sed 's/\ *//g' | grep -qw "^${address//./\\.}"; then
        # The calls are coming from inside the house!
        self "$(printf "${GREEN}%s${NC} looks like it is held by the machine running this script." "$address")"
        # Not considering this an error at this time, so return code is for all clear.
        return 0
      fi
    fi

    # Attempt to use our existing ARP cache without spending time on arping.
    mac="$(__get_mac_from_ip_address "$address")"

    # If we were not able to get a MAC address, try to add it to our cache the old-fashioned way.
    if [ -z "$mac" ]; then

      # Do not attempt to resolve if being lazy, exit silently.
      (( "${lazy:-0}" )) && return 1

      if [ -z "$WINDIR" ]; then

        notice "$(printf "Attempting to find \"${GREEN}%s${NC}\" with ${BLUE}%s${NC}..." "${address}" "arping")"

        # Cycle through our UP-state interfaces (excluding lo and tun_ interfaces)
        # Run through sort in a lazy attempt to prioritize ethernet interfaces (often starting with 'e') over wireless (often starting with 'w').

        # Add the -f switch to arping on distributions that support it (RHEL-based).
        # Decide outside of interface loop to save a try or two on interface-heavy systems.
        local arping_switch
        if [ -f "/etc/redhat-release" ]; then
          arping_switch="-f"
        fi

        for interface in $(ip a s | grep -e "^[0-9]*:" | grep UP | awk '{ print $2 }' | sed -r 's/(@.*|:)//g' | grep -Pv 'lo|tun[0-9]*' | sort); do

          # If arping was successful, break the loop.
          if arping -I "${interface}" "${arping_switch}" -c 1 -q "${address}"; then
            break
          fi
        done

        # Check if arping generated a valid entry in the ARP table.
        mac="$(__get_mac_from_ip_address "$address")"

      fi # end [ -z "$WINDIR" ] check

      if [ -z "$mac" ]; then # start ping-check block

        # If the MAC address is still empty, we are either on a Windows machine via MobaXterm,
        #     or a UNIX system that failed to arping.

        notice "$(printf "Attempting to find \"${GREEN}%s${NC}\" with ${BLUE}%s${NC}..." "${address}" "ping")"

        # Do a quick ping to try and add/refresh the arp entry.
        # We don't really care if it the actual ICMP echo succeeds or not.
        ping -n 1 -w 1 "$address" 2> /dev/null >&2

      fi # end ping-check block


      # If Unix: After the above 'for' loop, we have either successfully run arping on at least one interface, or unsuccessfully run through all of our interfaces.
      # If Windows: We've tried to ping the remote address.
      # Attempt to get the MAC address for the requested address with 'arp'
      if [ -z "$mac" ]; then
        mac="$(__get_mac_from_ip_address "$address")"
      fi

    fi # end check for $mac being empty

  fi # end else of MAC address format check (IP Address Handling)

  # Finished resolving our MAC address (if necessary, start searching records.
  if [ -z "$mac" ]; then
    error "$(printf "Unable to find a MAC address for ${GREEN}%s${NC}" "$address")"
    return 4
  fi

  local label
  label="$(__get_mac_label "$mac")"

  local box

  local vendor
  vendor="$(__get_mac_vendor "$mac")"

  if [ -n "$label" ]; then
    if [ -n "$address" ]; then
      # User provided an IP address
      record "$(printf "Record for ${GREEN}%s${NC} (${BOLD}%s${NC}): ${BOLD}%s${NC}" "$address" "$mac" "$label")"
    else
      # User only provided a MAC address
      record "$(printf "Record for ${BOLD}%s${NC}: ${BOLD}%s${NC}" "$mac" "$label")"
    fi

    # look for other fields to print if we are in verbose mode.
    if (( "$verbose" )); then
      local description
      description="$(__get_mac_description "$mac")"
      local general_location
      general_location="$(__get_mac_general_location "$mac")"
      local specific_location
      specific_location="$(__get_mac_specific_location "$mac")"
      local owner
      owner="$(__get_mac_owner "$mac")"
      local category
      category="$(__get_mac_type "$mac")"

      # TODO: There has got to be a tidier way to get a count of fields...
      local field_count="$(( $(cut -d' ' -f 1 <<< "$description" | wc -w) + $(cut -d' ' -f 1 <<< "$general_location" | wc -w) + $(cut -d' ' -f 1 <<< "$specific_location" | wc -w) + $(cut -d' ' -f 1 <<< "$owner" | wc -w) + $(cut -d' ' -f 1 <<< "$category" | wc -w) + $(cut -d' ' -f 1 <<< "$vendor" | wc -w) ))"

      count=1

      if [ -n "$owner" ]; then
        if [ "$count" -lt "$field_count" ]; then
          box="┣━"
        else
          box="┗━"
        fi
        count="$((count + 1))"
        printf "\t\t %s${BOLD}Owner:${NC} %s\n" "$box" "$owner"
      fi

      if [ -n "$category" ]; then
        if [ "$count" -lt "$field_count" ]; then
          box="┣━"
        else
          box="┗━"
        fi
        count="$((count + 1))"
        printf "\t\t %s${BOLD}Type:${NC} %s\n" "$box" "$category"
      fi

      if [ -n "$general_location" ]; then
        if [ "$count" -lt $field_count ]; then
          box="┣━"
        else
          box="┗━"
        fi
        count="$((count + 1))"
        printf "\t\t %s${BOLD}General Location:${NC} %s\n" "$box" "$general_location"
      fi

      if [ -n "$specific_location" ]; then
        if [ "$count" -lt $field_count ]; then
          box="┣━"
        else
          box="┗━"
        fi
        count="$((count + 1))"
        printf "\t\t %s${BOLD}Specific Location:${NC} %s\n" "$box" "$specific_location"
      fi

      if [ -n "$description" ]; then
        if [ "$count" -lt $field_count ]; then
          box="┣━"
        else
          box="┗━"
        fi
        count="$((count + 1))"
        printf "\t\t %s${BOLD}Description:${NC} %s\n" "$box" "$description"
      fi

      if [ -n "$vendor" ]; then
        if [ "$count" -lt $field_count ]; then
          box="┣━"
        else
          box="┗━"
        fi

        count="$((count + 1))"
        printf "\t\t %s${BOLD}NIC Vendor:${NC} %s\n" "$box" "$vendor"
      fi
    fi # end verbose flag check
  elif [ -n "${vendor}" ]; then
    # Unable to find a specific label in our network index.
    # As a fallback, attempt to determine the vendor of the unknown device.

    if [ -n "${address}" ]; then
      # User provided resolveable domain name or IP address
      if ! (( "${lazy:-0}" )); then
        unknown "$(printf "No record for ${GREEN}%s${NC} (${BOLD}%s${NC}) Vendor: ${BOLD}%s${NC}" "$address" "$mac" "$vendor")"
      fi
    elif ! grep -iPq '^[a-f0-9]{2}([:|-][a-f0-9]{2}){5}$' <<< "${mac}"; then
      # User provided an incomplete MAC address.
      # Assuming that the user did this intentionally in order
      #   to specifically check a vendor.
      record "$(printf "Vendor for ${BOLD}%s${NC}: ${BOLD}%s${NC}" "${mac}" "${vendor}")"
    elif ! (( "${lazy:-0}" )); then
      # User only provided a full-fledged MAC address
      unknown "$(printf "No record for ${BOLD}%s${NC} (Vendor: ${BOLD}%s${NC})..." "$mac" "$vendor")"
    fi
    return 5
  else
    # No vendor was not found either
    if [ -n "$address" ]; then
      # User provided resolveable domain name or IP address
      unknown "$(printf "No records for ${GREEN}%s${NC} (${BOLD}%s${NC})..." "$address" "$mac")"
    else
      # User only provided a MAC address
      unknown "$(printf "No records for ${BOLD}%s${NC}..." "$mac")"
    fi
    return 5
  fi

  # Unsetting interface down here in case we realize we want it later.
  unset interface
}

# This functions are only compatible with Unix for the moment.
# This is because all non-background functions rely on the ip command.

# Look up all records for every network that we are currently sitting on.
# Going out of our way to exclude tun_ connections before we even get to getlabel-net (which does its own filtering of tun_ anyways).
# Work's VPN places me on a TUN for the moment, and I'm not risking a massive earful on account of a accidental !g.
getlabel_all(){
  # Cycle through all of our UP-state interfaces.

  for interface in $(ip a s | grep -e "^[0-9]*:" | grep UP | awk '{ print $2 }' | sed -r 's/(@.*|:)//g' | grep -Pv '^(lo|tun[0-9]*)$' | sort); do
    # Add any interface with an address to our list.
    if ip a s "${interface}" | grep -Pq 'inet\ (([0-9]){1,3}\.){3}([0-9]{1,3})'; then
      local interface_list="$interface_list ${interface}"
    fi
  done

  if [ -n "${interface_list}" ]; then
    local count
    count=$(wc -w <<< "$interface_list")

    # Silly branching for plural.
    if [ "${count}" -gt 1 ]; then
      notice "$(printf "Scanning ${BOLD}%d${NC} networks with IP addresses." "${count}")"
    else
      notice "$(printf "Scanning our one ${BOLD}%d${NC} interface with an IP address." "${count}")"
    fi

    for current_interface in $interface_list; do
      getlabel_if "${current_interface}"
    done

  else
    # Do not scan anything, but I don't really consider this to be an error.
    notice "We do not appear to currently have an address on any networks."
  fi

  # Unset loop variables.
  unset interface current_network
}

# Lazy wrapper of getlabel-net that scans the address held by a specific interface.
getlabel_if(){
  if [ -z "$1" ]; then
    error "Usage: getlabel-if interface"
  fi

  local interface="$1"

  # Check to see that the interface exists.
  ip_output="$(ip a s "${interface}" 2> /dev/null)"
  if [ -z "${ip_output}" ]; then
    error "$(printf "Interface ${BOLD}%s${NC} not found..." "${interface}")"
    return 2
  fi

  # Manually deny tun/tap interfaces.
  if grep -qP "^(tun|tap)" <<< "${interface}"; then
    error "$(printf "Interface ${BOLD}%s${NC} is a TUN/TAP interface..." "${interface}")"
    return 2
  fi

  local networks
  networks="$(route -n | sed -r '/(tun|tap)[0-9]{1,}/d' | grep -P "^\d" | awk '{if($2=="0.0.0.0"){print $1"/"$3" "$8}}' | grep -w "${interface}" | cut -d' ' -f1 | sort | uniq | sed '/^169\.254/d')"

  local network_count
  network_count=$(wc -w <<< "$networks")

  if [ "$network_count" -gt 0 ]; then
    notice "$(printf "Looking for devices on the same network as our ${BOLD}%s${NC} interface (%d subnets)." "${interface}" "$network_count")"
    for network in $networks; do
      getlabel "$(cut -d'/' -f 1 <<< "${network}")/$(mask2cidr "$(cut -d'/' -f2 <<< "${network}")")"
    done
    unset network # Axe loop variable
  else
    # Interface is not attached to any networks.
    # Check to see if it isn't a bridge member.
    local bridge
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
      notice "$(printf "${BOLD}%s${NC} has no networks, but is a member of the ${BOLD}%s${NC} bridge." "${interface}" "${bridge}")"
      getlabel_if "${bridge}"
    else
      error "$(printf "${BOLD}%s${NC} is not attached to any networks." "${interface}")"
    fi
  fi
}

hexit(){
  cat << EOF
Attempt to resolve MAC addresses to readable labels. This script is useful for identifying your own devices from a host if you do not know/remember your IP assignments.

Usage: ./getlabel [-chlv] subject [more-subjects]

A subject can be one of the following:

  * A MAC Address
  * An IPv4 address
  * An IPv4 CIDR range.

  IPv4 addresses and ranges must be at least partly within your local routes.

Switches:

  -c: Force terminal colours. Useful if output is being stored temporarily before a confirmed terminal.
  -h: Show this help menu.
  -l: "Lazy" mode. Silence many errors and do not attempt to resolve MAC addresses that are not immediately in our ARP table.
  -v: "Verbose" mode. Print additional information on target device.

This script reads off of a CSV file for its main data. The file is specified in the INDEX_NETWORK_DATA environment variable, and should be of the following format:

    category,type,mac-address,title,location,sublocation,description,notes
    My Devices,Desktop,aa:bb:cc:dd:ee:ff,My Desktop Machine,Home,A Desk,This is a Computer,

As a fallback to a label (or in verbose mode), the script draws off vendor information out of a pipe-delimited file. The file is specified in the INDEX_VENDOR_DATA environment variable, and should be of the following format:

    prefix  |vendor
    00:00:00|XEROX CORPORATION

I use the following to generate my vendor index using the IEEE website:

    curl -L "http://standards-oui.ieee.org/oui.txt" > oui.txt
    cat oui.txt | grep \(hex\) | awk -F"\t" '{print $1"|"$3 }' | sed 's/   (hex)//g' | sed -r 's/^([A-Z1-90]{2})-([A-Z1-90]{2})-([A-Z1-90]{2})/\L\1:\2:\3/' | sed 's/\r//g' | sort > vendor-mac.txt
EOF

  exit "${1:-0}"
}

while [ -n "${1}" ]; do
  while getopts ":chlv" OPT "$@"; do
    case "$OPT" in
      "c")
        colours_on
        ;;
      "h")
        hexit 0
        ;;
      "l")
        lazy=1
        ;;
      "v")
        verbose=1
        ;;
      *)
        error "$(printf "Unhandled argument type: %s" "${OPT}")"
    esac
  done

  # Set $1 to first operand, $2 to second operands, etc.
  shift $((OPTIND - 1))
  [ -n "${1}" ] || break

  while [ -n "${1}" ]; do
    # Break if an option.
    grep -q "^\-" <<< "${1}" && break

    if [[ "${1}" == "all" ]]; then
      do_all=1
    else
      targets="${targets} ${1}"
    fi

    shift
  done
done

if (( "${do_all:-0}" )); then
  if [ -z "$WINDIR" ]; then
    getlabel_all
  else
    error "Cannot cycle through all interfaces in a Windows-y environment."
  fi
else
  for _a in ${targets}; do
    if ip a s "$_a" 2> /dev/null >&2; then
      # Specific interface
      getlabel_if "$_a"
    else
      # Network address or address range.
      getlabel "$_a"
    fi
  done
fi

if ! (( "${lazy:-0}" )); then
  (( "${__record_count:-0}" )) && summary "$(printf "Records retrieved: ${BOLD}%s${NC}" "${__record_count}")"
  (( "${__unknown_count:-0}" )) && summary "$(printf "Unknown entries: ${BOLD}%s${NC}" "${__unknown_count}")"
fi

if ! (( "${do_all:-0}" )) && [ -z "${targets}" ]; then
  error "No targets defined."
fi

(( "${__error_count:-0}" )) && ret=1

exit "${ret:-0}"
