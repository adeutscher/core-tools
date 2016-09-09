
# The chain in the NAT table that will be read from and written to
SNAT_CHAIN=POSTROUTING

# Label for the benefit of anyone manually looking through the chain.
SNAT_LABEL=iptables

# You may wish to add other qualifiers on what gets SNAT applied to it and what does not.
OTHER_FILTERS='-s 10.11.12.0/24'

# NetworkManager command
IPTABLES='/usr/sbin/iptables -t nat'
 
function clean_snat_references(){
  CLEAN_IF=$1

  if [ -z "$CLEAN_IF" ]; then
    # Need one argument. If this isn't set, abort and do nothing.
    return 0
  fi

  # Make sure that this chain exists.
  $IPTABLES -N $SNAT_TABLE 2> /dev/null

  for line in $($IPTABLES -nvL "$SNAT_CHAIN" --line-numbers | grep "snat-$CLEAN_IF\." | grep '^[0-9]*' | cut -d' ' -f 1 | tac); do
    if [ ! -z "$line" ]; then
      # Axe the previous rule if it exists.
      $IPTABLES -D $SNAT_CHAIN $line
    fi
  done
}
 
function fix_snat(){
  SNAT_IF=$1
  SNAT_IP=$2

  clean_snat_references "$SNAT_IF"
 
  if [ -z "$SNAT_IP" ]; then
    # Need two parameters to write a new SNAT rule..
    # If these aren't set, abort having confirmed that the old SNAT entry has been removed.
    return 0
  fi

  # If IPv4 forwarding is enabled, then write in the new rule.
  # If not, then do not bother.
  if grep -q '^1$' < /proc/sys/net/ipv4/ip_forward 2> /dev/null; then 
    $IPTABLES -I $SNAT_CHAIN -o $SNAT_IF $OTHER_FILTERS -m comment --comment "$SNAT_LABEL-snat-$SNAT_IF." -j SNAT --to-source $SNAT_IP
  fi
}
 
function fix_interface_snat(){
    # Automatically detect an interface's IP address, then continue on to fix_snat function.

    TARGET_IF=$1
 
    if [ -z "$TARGET_IF" ]; then
        # Need one argument. If this isn't set, abort and do nothing.
        return 0
    fi
 
    TARGET_IP=$(ip addr show "$TARGET_IF"  | grep inet[^6] | cut -d ' ' -f 6 | cut -d '/' -f 1 | head -n 1)
 
    fix_snat "$TARGET_IF" "$TARGET_IP"
}
