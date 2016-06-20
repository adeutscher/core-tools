#!/bin/sh
 
# In one instance, my Pi was occasionally losing its address
#     on the wireless network that it was joined to.

# Using this script to periodically check and fix the wireless
#     by bringing the interface down and back up again.
 
#set -x
 
# Monitoring wireless interface.
iface=$1
 
# Exit if no interface given, or not actually a wireless interface
[ -d "/sys/class/net/$iface/wireless/" ] || exit 1
 
# Assumed to be broken until proven otherwise.
# Crude check for the interface being up.
if /sbin/ip a s $iface | /bin/grep -qw inet; then
    if [ "$(id -u)" -ne 0 ]; then
        # If not running as root, re-run script as root.
        # Running this script on Raspbian, which does not ask for a password for sudo by default.
        # If you weren't on such a device, consider just running this script off of root's crontab instead.
        sudo /bin/sh $0
        exit 0
    fi
 
    /sbin/ifdown $iface 2> /dev/null
    /sbin/ifup $iface
fi
