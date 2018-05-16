
###############################
# Network Connection Tracking #
###############################
# Functions for listing incoming and outgoing network connections.
# Became sizable (in function count, not code volume) to make me want
#     to make a new section away from the other networking functions.

# These connection functions only work for Unix systems.
if __is_unix; then
  # lsock: to display open sockets (the -P option to lsof disables port names)
  # TODO: Refine to be more an alias for tracking running daemons.
  alias lsock='sudo /usr/sbin/lsof -i -n -P'

  # IPv4 Listing

  # Incoming connections.
  connections-in(){
    # Display incoming connections (not including localhost)
    connections
  }

  connections-in-all(){
    connections -a
  }

  connections-in-lan(){
    # Display incoming connections from LAN addresses.
    connections -L
  }

  connections-in-local(){
    # Display incoming connections that involve localhost.
    connections -l
  }

  connections-in-remote(){
    # Display incoming connections from non-LAN addresses.
    connections -L
  }

  # Outgoing connections
  connections-out(){
    # Display outgoing connections (not including localhost)
    connections -o
  }

  connections-out-all(){
    connections -o -a
  }

  connections-out-lan(){
    # Display outgoing connections that go to local area network addresses.
    connections -o -L
  }

  # Alias for connections-out-lan
  alias connections-lan='connections-out-lan'

  connections-out-local(){
    # Display outgoing connections that involve localhost.
    connections -o
  }

  connections-out-remote(){
    # Display outgoing connections, excluding localhost and LAN connections.
    connections -o -R
  }

  # IPv6 Listing
  ##

  connections-in-ipv6(){
    # Function for listing incoming IPv6 connections from the command line.
    # Making this an alias is a nightmare that I didn't want to have to deal with.

    # For the moment, I do not have a BASH method of distinguishing IPv6 subnets, so
    #   this function will cover ALL incoming IPv6 connections for now.
    netstat -tun6 | grep ESTABLISHED  | awk 'function join(array, len, sep){ result = array[1]; for (i = 2; i <= len; i++){ result = result sep array[i]; }; return result } { lenl=split($4,l,":"); lenr=split($5,r,":"); portl=l[lenl]; portr=r[lenr]; addrl=join(l, lenl-1, ":"); addrr=join(r, lenr-1, ":"); if(portl < '$(cat /proc/sys/net/ipv4/ip_local_port_range | awk '{ print $1 }')'){ print $1 " " portl " " addrr " -> " addrl " ("$1"/"portl")" }; }' | sort -k1,1 -k2,2n | cut -d' ' -f 3-
    }

  connections-out-ipv6(){
    # Function for listing outgoing IPv6 connections from the command line.
    # Making this an alias is a nightmare that I didn't want to have to deal with.

    # For the moment, I do not have a BASH method of distinguishing IPv6 subnets, so
    #   this function will cover ALL outgoing IPv6 connections for now.
    netstat -tun6 | grep ESTABLISHED  | awk 'function join(array, len, sep){ result = array[1]; for (i = 2; i <= len; i++){ result = result sep array[i]; }; return result } { lenl=split($4,l,":"); lenr=split($5,r,":"); portl=l[lenl]; portr=r[lenr]; addrl=join(l, lenl-1, ":"); addrr=join(r, lenr-1, ":"); if(portl > '$(cat /proc/sys/net/ipv4/ip_local_port_range | awk '{ print $1 }')' && ($1 == "tcp6" || portr < '$(cat /proc/sys/net/ipv4/ip_local_port_range | awk '{ print $1 }')')){ print $1 " " portr " " addrl " -> " addrr " ("$1"/"portr")" }; }' | sort -k1,1 -k2,2n | cut -d' ' -f 3-
    }
fi
