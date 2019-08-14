#!/bin/sh

# This script was made to solve two use cases:
#   - My locally-running DNS server on old-laptop would sometimes not bind to the bridge interface that my KVM guests live on due to differences in execution order.
#   - Making sure that my DNS is set up correctly before connecting to a VPN (home or otherwise) so that I can resolve addresses on the VPN domain while still being able to resolve any addresses specific to my location (e.g. resolve work domain names at work.
#       - The downside of this approach is that I need to manually add every custom LAN domain, and need to add hosts entries for any exceptions (if the LAN domain is the same as the public domain). Since I've only had to do this for a small number of domains so far, this is acceptable.

# Colors
BLUE='\033[1;94m'
GREEN='\033[1;92m'
RED='\033[1;91m'
NC='\033[0m' # No Color

# Crude OS detection.
if [ -f "/etc/named.conf" ]; then
    service=named
elif [ -d "/etc/bind9" ]; then
    service=bind9
fi

if [ -z "$service" ]; then
  echo -e "${BLUE}Notice${NC}: This machine does have a DNS server installed on it. No DNS to fix."
  exit 0
fi

if [ "$EUID" -gt 0 ]; then
  echo -e "${BLUE}Notice${NC}: Must be root to restart DNS server and write to ${GREEN}/etc/resolv.conf${NC}"
  sudo sh $0
  exit $?
fi

service $service restart
if [ "$?" -gt 0 ]; then
  echo -e "${RED}Error${NC}: There was an error restarting the $service DNS server."
  exit 1
fi

cp -f /etc/resolv.conf /etc/resolv.conf.bak
echo 'nameserver 127.0.0.1' > /etc/resolv.conf

