
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

    # Incoming connections.
    connections-in(){
        # Display incoming connections (not including localhost)
        connections-in-all | grep --colour=never -v '127\.0\.0\.1'
    }

    connections-in-all(){
        # Function for listing incoming connections from the command line.
        # Making this an alias is a nightmare that I didn't want to have to deal with.
        netstat -tun | grep ESTABLISHED  | awk '{ split($4,l,":"); split($5,r,":"); if(l[2] < '$(cat /proc/sys/net/ipv4/ip_local_port_range | awk '{ print $1 }')'){ print $1 " " l[2] " " r[1] "->" l[1] " ("$1"/"l[2]")" }; }' | sort -k1,1 -k2,2n | cut -d' ' -f 3-
    }

    connections-in-lan(){
        # Display incoming connections from LAN addresses.
        connections-in-all | egrep --colour=none '(10\.[0-9]{1,3}|172\.(1[6-9]|2[1-90]|3[1-2])|\.192\.168)(\.[0-9]{1,3}){2}\->'
    }

    connections-in-local(){
        # Display incoming connections that involve localhost.
        connections-in-all | grep --colour=never '127\.0\.0\.1'
    }

    connections-in-remote(){
        # Display incoming connections from non-LAN addresses.
        connections-in-all | grep -v '127\.0\.0\.1' | egrep -v '(10\.[0-9]{1,3}|172\.(1[6-9]|2[1-90]|3[1-2])|\.192\.168)(\.[0-9]{1,3}){2}\->'
    }

    # Outgoing connections
    connections-out(){
        # Display outgoing connections (not including localhost)
        connections-out-all | grep --colour=never -v '127\.0\.0\.1'
    }

    connections-out-all(){
        # Function for listing outgoing connections from the command line.
        # Making this an alias is a nightmare that I didn't want to have to deal with.
        netstat -tun | grep ESTABLISHED  | awk '{ split($4,l,":"); split($5,r,":"); if(l[2] > '$(cat /proc/sys/net/ipv4/ip_local_port_range | awk '{ print $1 }')' && ($1 == "tcp" || r[2] < '$(cat /proc/sys/net/ipv4/ip_local_port_range | awk '{ print $1 }')')){ print $1 " " r[2] " " l[1] "->" r[1] " ("$1"/"r[2]")" }; }' | sort -k1,1 -k2,2n | cut -d' ' -f 3-
    }

    connections-out-lan(){
        # Display outgoing connections that go to local area network addresses.
        connections-out-all | egrep --colour=none '\->(10\.[0-9]{1,3}|172\.(1[6-9]|2[1-90]|3[1-2])|\.192\.168)(\.[0-9]{1,3}){2}'
    }
    # Alias for connections-out-lan
    alias connections-lan='connections-out-lan'

    connections-out-local(){
        # Display outgoing connections that involve localhost.
        connections-out-all | grep --colour=never '127\.0\.0\.1'
    }

    connections-out-remote(){
        # Display outgoing connections, excluding localhost and LAN connections.
        connections-out-all | grep --colour=never -v '127\.0\.0\.1' | egrep -v '\->(10\.[0-9]{1,3}|172\.(1[6-9]|2[1-90]|3[1-2])|\.192\.168)(\.[0-9]{1,3}){2}'
    }

fi
