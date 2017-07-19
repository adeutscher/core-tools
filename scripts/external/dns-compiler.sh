#!/bin/bash

# This script is assumed to be running as root.

# Confirm that /sbin and /usr/local/sbin are in our PATH (required for named-checkconf)
PATH="/sbin:/usr/sbin:$PATH"

#############
# Variables #
#############

# Directory that temporary configuration should be written to.
DNS_COMPILER_DATA=/tmp/dns-compiler.csv
# Configuration will be written here
# NOTE: You must separately adjust your BIND9 installation to load in this file.
DNS_COMPILER_TARGET=/etc/named/dns-compiler.conf
#DNS_COMPILER_TARGET=/tmp/dns-compiler.conf

###############
## Functions ##
###############

TYPE_CISCO="cisco"
TYPE_OPENVPN="openvpn"
TYPE_NETWORK_MANAGER="network-manager"
TYPE_UNKNOWN="unknown"

__is_ip(){
  # (only checking for octets, assuming that it isn't something
  #     impossible like 555.555.555.555 for the moment.
  # TODO: Apply a more sophisticated check.
  if [[ $1 =~ [0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3} ]]; then
    return 0
  fi
  return 1
}

__is_domain(){
  # Domains (at the moment) are assumed to contain only numbers,
  #  letters (uppercase and lowercase, depending on how the option was entered into configuration),
  #  periods, and dashes.
  # Other conditions:
  # - The candidate domain cannot begin or end with something that is not a number or letter.
  # - The candidate domain cannot have two consecutive characters that are not numbers or letters
  if grep -P '^[^\-\.][a-zA-Z\-\.]*[^\-\.]$' <<< "$1" | grep -vP '[\.\-]{2,}'; then
    return 0
  fi
  return 1
}

############################################
# Get information depending on environment #
############################################

__get_connection_type(){
  if [ -n "$CISCO_SPLIT_DNS" ]; then
    printf "$TYPE_CISCO"
  elif [ -n "$script_type" ]; then
    printf "$TYPE_OPENVPN"
  elif [ -n "$DEVICE_IP_IFACE" ]; then
    printf "$TYPE_NETWORK_MANAGER"
  else
    printf "$TYPE_UNKNOWN"
  fi
}

__get_connection_reason(){
  case "$(__get_connection_type)" in
  "$TYPE_CISCO")
    printf "$reason"
    ;;
  "$TYPE_NETWORK_MANAGER")
    if [ -n "$IP4_ADDRESS_0" ]; then
      printf "connect"
    else
      printf "disconnect"
    fi
    ;;
  "$TYPE_OPENVPN")
    if [[ "$script_type" =~ ^up$ ]]; then
      printf "connect"
    elif [[ "$script_type" =~ ^(down|disconnect)$ ]]; then
      printf "disconnect"
    else
      printf "unknown"
    fi
    ;;
  esac
}

__get_connection_nameserver(){

  # For the moment, we only care about the first nameserver given to us.
  # If we decide to use all of them in the future,
  #   then it would be ideal if this function spat out a semicolon-delimited list.
  # This will save us the trouble of doing it later for BIND9.

  # Make sure that we're woking with a blank slate
  unset nameservers

  # Collect all domains, though for the moment we will be only printing out the first valid one.
  case "$(__get_connection_type)" in
  "$TYPE_CISCO")
    # If multiple nameservers are sent, they will be space-delimited.
    # Source: openconnect 7.0.6 source code (script.c, script_setenv function)
    local nameservers="$INTERNAL_IP4_DNS"
    ;;
  "$TYPE_NETWORK_MANAGER")
    # Space-delimited (Source: NetworkConnect man page)
    local nameservers="$IP4_NAMESERVERS"
    ;;
  "$TYPE_OPENVPN")
    # Cycle through opts for push "DNS" options
    # With thanks to gronke of GitHub.
    for opt in ${!foreign_option_*}
    do
      eval "candidate=\${$opt#dhcp-option DNS }"
      if __is_ip "$candidate"; then
        local nameservers="$nameservers $candidate"
      fi
    done
    ;;
  esac

  for nameserver in $nameservers; do
    # Nameserver must be an IP address
    if __is_ip "$nameserver"; then
      # Abort after our first valid nameserver
      printf "%s\n" "$nameserver"
      break
    fi
  done
  # Axe loop variable
  unset nameserver
}

__get_connection_domains(){
  # Get connection domains and print them out as a space-delimited listing
  case "$(__get_connection_type)" in
  "$TYPE_CISCO")
    # anyconnect gives domains in comma-delimited format
    # convert commas to spaces
    local domains="$(sed 's/,/ /g' <<< "$CISCO_SPLIT_DNS")"
    ;;
  "$TYPE_NETWORK_MANAGER")
    # IP4_DOMAINS is already space-delimited (see: NetworkManager man page)
    local domains="$IP4_DOMAINS"
    ;;
  "$TYPE_OPENVPN")
    # Cycle through opts for push "DNS" options
    # With thanks to gronke of GitHub.
    for opt in ${!foreign_option_*}
    do
	  eval "candidate=\${$opt#dhcp-option DOMAIN }"
      if __is_domain "$candidate"; then
        domains="$domains $candidate"
      fi
    done
    ;;
  esac

  # Validate our domains after we've collected them from the appropriate method.
  for domain in $domains; do
    if __is_domain "$domain"; then
      printf "%s\n" "$domain"
    fi
  done
  unset domain
}

__get_connection_interface(){
  case "$(__get_connection_type)" in
  "$TYPE_CISCO")
    printf "$TUNDEV"
    ;;
  "$TYPE_NETWORK_MANAGER")
    printf "$DEVICE_IFACE"
    ;;
  "$TYPE_OPENVPN")
    printf "$dev"
    ;;
  esac
}

##########################
# DNS Compiler Functions #
##########################

__confirm_structure(){
  [ -n "$DNS_COMPILER_DATA" ] && touch "$DNS_COMPILER_DATA" && \
  [ -n "$DNS_COMPILER_TARGET" ] && touch "$DNS_COMPILER_TARGET" && \
    return 0
  return 1
}

__apply_interface(){

  __confirm_structure || exit 0

  local interface="$(__get_connection_interface)"
  local domains=$(__get_connection_domains | sort | uniq)
  local nameserver=$(__get_connection_nameserver)

  # Do not bother continuing if we did not get a necessary field.
  # - Interface is not technically required for BIND9, but it is required for purging.
  # - Domains are the entire point of this script
  # - A nameserver is necessary to make the domain worth anything.
  if [ -z "$interface" ] || [ -z "$domains" ] || [ -z "$nameserver" ]; then
    return 0
  fi

  # Get a count of new domains. This will be our return value.
  local count=$(wc -w <<< "$domains")

  # When bringing an interface up, do not purge until we are sure that we have new domains to work with.
  # This is to avoid a conflict between NetworkManager and OpenVPN/anyconnect.
  # The NetworkManager script will always run, but it does not have the necessary information to get domain information.
  # Without running __purge_interface after the variable check,
  #   then odds are the NetworkManager will run second and wipe out all of the work that the first script has done.
  __purge_interface "$interface"

  # If you want to make customizations to a given connection,
  #     then this would be a good place to do it.
  # For example, my work VPN does not give me every domain that I need,
  #     so until the configuration can be changed I must add it to my domain list manually.

  for domain in $domains; do
    printf "%s,%s,%s\n" "$interface" "$domain" "$nameserver" >> "$DNS_COMPILER_DATA"
  done

  return $count
}

__get_data(){
  local interface=$1

  if [ -n "$interface" ]; then
    # Filter for a specific interface if one is given.
    grep --color=never "^$interface," "$DNS_COMPILER_DATA" | sort | uniq
  else
    cat "$DNS_COMPILER_DATA" | sort | uniq
  fi
}

__get_checksum(){
  md5sum "$DNS_COMPILER_TARGET" 2> /dev/null
}

# TODO: If dynamic adding through rndc were working,
#         then we would also remove each domain in our CSV from BIND9
#         before removing them from the CSV
#       We would also not care at all about the number removed.
__purge_interface(){
  # Remove references to an interface from source files
  if [ -n "$1" ] && [ -f "$DNS_COMPILER_DATA" ] && [ -r "$DNS_COMPILER_DATA" ]; then
    local old_count=$(wc -l < "$DNS_COMPILER_DATA" 2> /dev/null)
    sed -i "/^$1,/d" "$DNS_COMPILER_DATA" 2> /dev/null
    local new_count=$(wc -l < "$DNS_COMPILER_DATA" 2> /dev/null)
    if [ "${old_count-0}" -ne "${new_count-0}" ]; then
      return $((${old_count-0}-${new_count-0}))
    fi
  fi
}

__has_dns_server(){
    grep -q "nameserver\ *127\.0\.0\.1" /etc/resolv.conf
    return $?
}

__compile(){
  __confirm_structure || exit 0

  domain_data="$(__get_data)"

  # Record checksum of data as a global variable before re-compiling.
  OLD_DATA_CHECKSUM=$(__get_checksum)
  # Truncate target file for good measure
  > "$DNS_COMPILER_TARGET"

    # The extra loop is necessary to make sure that domains from different interfaces do not interfere with each other.
  for domain in $(cut -d',' -f 2 <<< "$domain_data" | sort | uniq); do
    # Re-acquire the line for this domain.
    local domain_entry="$(grep -m1 ",$(sed 's/\./\\./g' <<< "$domain")," <<< "$domain_data" | head -n1)"
    # Might be a side-effect of late-night coding, but I cannot see why head is required here in the case of dupes...
    local interface="$(cut -d',' -f1 <<< "$domain_entry" | head -n1)"
    local nameserver="$(cut -d',' -f3 <<< "$domain_entry" | head -n1)"

    # TODO: If zone addition through rndc were working, we would instead be removing the domain (for good measure) and adding it here.
    printf 'zone "%s" { type forward; forwarders { %s; }; forward only; }; // Interface: %s\n' "$domain" "$nameserver" "$interface"
  done | sort | uniq > "$DNS_COMPILER_TARGET"
  
}

__do_connect(){
  __apply_interface
  local new_domains=$?
  if (( $new_domains )); then
    __compile
    __reload
  else
    # No new domains, abort.
    return 0
  fi
}

__do_disconnect(){
  __purge_interface "$(__get_connection_interface)"
  local removed_domains=$?
  if (( $removed_domains )); then
    __compile
    __reload
  else
    # No removed domains, abort.
    return 0
  fi
}

# Reload BIND9.
# TODO: If dynamic adding through rndc were working, this function would be entirely unavailable
__reload(){
  if [[ "$OLD_DATA_CHECKSUM" != "$(__get_checksum)" ]] && named-checkconf 2> /dev/null >&2; then
    systemctl restart named >&2 2> /dev/null &
  fi
}

__run_dns_compiler(){

  if ! __has_dns_server; then
    # Return 0 so that OpenVPN does not error out from the non-zero.
    return 0
  fi
  #__get_connection_type | tee -a /tmp/dns-debug
  case "$(__get_connection_reason 2> /dev/null)" in
    "connect")
    __do_connect
    ;;
  "disconnect")
    __do_disconnect
    ;;
  esac
}

__run_dns_compiler
