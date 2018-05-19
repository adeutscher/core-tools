
# IPv4 Address Handling Functions
##

ip2dec(){
  local a b c d ip="${@}"
  IFS=. read -r a b c d <<< "${ip}"
  printf '%d\n' "$((a * 256 ** 3 + b * 256 ** 2 + c * 256 + d))"
}

dec2ip(){
  local ip dec="${@}"
  for e in {3..0}; do
    ((octet = dec / (256 ** e) ))
    ((dec -= octet * 256 ** e))
    ip+="${delim}${octet}"
    local delim=.
  done
  unset e octet dec
  printf '%s\n' "${ip}"
}

cidr_low(){
  printf $(dec2ip $(cidr_low_dec "$1"))
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

  printf $(($(ip2dec "${network}")+${plus}))
}

cidr_high(){
  printf $(dec2ip $(cidr_high_dec "$1"))
}

cidr_high_dec(){
  # Print the highest usable address in a CIDR range.
  # Assumes valid input in one of the the following two formats:
  #   - 10.11.12.13/24
  #   - 10.11.12.13/255.255.255.0
  # Calculating netmask manually because ipcalc does not support
  #   calculating the minimum/maximum addresses in all distributions.

  local network="$(cut -d'/' -f1 <<< "$1")"
  local netmask="$(cut -d'/' -f2 <<< "$1")"

  if ! grep -qP "^\d{1,}$" <<< "${netmask}"; then
    # Netmask was not in CIDR format.
    local netmask=$(printf %.$2f $(awk '{ print 32-log(4294967295-'"$(ip2dec "${netmask}")"')/log(2)}' <<< ""))
  fi

  # Subtract 2 for network id and broadcast addresss
  #   (unless we have a /32 address)
  local subtract=2
  if [ "${netmask}" -eq "32" ]; then
    # /32 networks are single-host networks,
    #   wherein the network ID is the only usable address.
    local subtract=0
  fi

  printf $(($(ip2dec "${network}")+(2 ** (32-netmask))-${subtract}))
}

is_in_cidr(){
  local addr="${1}"
  local cidr="${2}"
  # Do not bother checking with insufficient arguments.
  [ -n "${2}" ] || return 1

  local addr_dec="$(ip2dec "${addr}")"
  [ "${addr_dec}" -ge "$(cidr_low_dec "${cidr}")" ] && [ "${addr_dec}" -le "$(cidr_high_dec "${cidr}")" ]
}
