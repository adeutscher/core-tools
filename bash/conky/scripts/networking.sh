#!/bin/bash

# If CONKY_DISABLE_NETWORK evaluates to true, then exit immediately.
if (( "${CONKY_DISABLE_NETWORK}" )); then
    exit 0
fi

# Collecting most of our lists in advance.
# List of all interfaces
interfaces=$(ip a s | grep -e "^[0-9]*:"  | awk '{ print $2 }' | sed -e 's/://g' -e 's/@.*//g' | sort)
# Down interfaces
down_interfaces=$(ip a s | grep -e "^[0-9]*:" | grep -v -e "[<,]UP[,>]" | awk '{ print $2 }' | sed -e 's/://g' -e 's/@.*//g' | sort | tr '\n' ' ')
# Wireless interfaces
wireless_interfaces=$(find -L /sys/class/net/ -maxdepth 2 -name wireless 2> /dev/null | cut -d'/' -f5 | tr '\n' ' ')
# Bridges
bridges=$(find -L /sys/class/net/ -maxdepth 2 -name bridge 2> /dev/null | cut -d'/' -f5 | tr '\\\n' ' ')
# Bridge Members (to do this for a specific bridge, just add an argument to brctl. copy as needed)
bridge_members=$(brctl show 2> /dev/null | sed -e '/bridge name/d' -e 's/\t/\ /g' | awk '{ if(NF > 1){ $1="";$2="";$3="" } print $0 }' | tr '\n' ' ')
# List (default) gateways (any gateway with a destination of "0.0.0.0").
gateways="$(route -n | awk '{ if($1 == "0.0.0.0"){ print $2 } }' | sort -n | uniq)"

# List of interfaces to exclude from listing.
exclude_list="lo ${CONKY_IGNORE_INTERFACES}"
# Notes on exclude_list
## Space-delimited list. For example: "lo eth0 eth1"
## With the current approach, this would skip aliases entirely (e.g. blocking eth0 would block eth0:0),
##    and does not work in reverse since individual aliases are not checked (e.g. eth0:0 could not be specifically blocked)

. functions/common.sh
. functions/network-labels.sh

########################
########################
## Network Interfaces ##
########################
########################

#####################
# Gateway Discovery #
#####################

gateway_count=0
gateway_spacing=10 # For " Gateway: "
gateway_display_limit=3
for ip in ${gateways}; do
    gateway_count=$((gateway_count+1))

    if [ "${gateway_count}" -ge "${gateway_display_limit}" ]; then
        # Conky is set to only print "multiple" if there are 3 or more gateways present.
        # Break out and don't bother doing more processing that will not be displayed past 3.
        break
    fi

    tentative_length=$(expr length "${ip}")

    # Note: May need to add a bit of extra padding for spaces to the left side of the below IF statement
    #   if I decide that you want to display more than 2 gateways before busting out the "multiple" label in the future.
    if [ "$((${tentative_length}+$gateway_spacing))" -ge ${characterWidthLimit} ]; then
        gateway_spacing=$((${tentative_length}+12))
        tentative_gateway="${tentative_gateway},\n             \${color #${colour_network_address}}${ip}\${color}"
    else
        gateway_spacing=$((${tentative_length}+${gateway_spacing}+2))
        tentative_gateway="${tentative_gateway}, \${color #${colour_network_address}}${ip}\${color}"
    fi
done

if [ "${gateway_count}" -gt "0" ]; then
    # Remove leading comma
    tentative_gateway="$(sed 's/^,\ //' <<< "${tentative_gateway}")"

    if [ "${gateway_count}" -ge "${gateway_display_limit}" ]; then
        # Too many gateways to be worth displaying
        # Fall back to conky's default output of just saying "multiple".
        gateway="Gateways: multiple"
    elif [ "${gateway_count}" -eq 1 ]; then
        gateway="Gateway: ${tentative_gateway}"
    else
        # Remaining case: More than one gateway, but under threshold (threshold is currently 3).
        gateway="Gateways: ${tentative_gateway}"
    fi
else
    # No gateways at all
    gateway="No Gateway"
fi

################################
# Header and Basic Information #
################################

printf "\${color #${colour_network}}\${font Neuropolitical:size=16:bold}Networking\${font}\${color}\${hr}\n ${gateway}\n"

##############
# Interfaces #
##############

# List interfaces with details
for iface in ${interfaces}; do

    # Clear/reset variables for upcoming loop.
    unset member_list
    is_vpn=0

    address="$(ip a s ${iface} 2> /dev/null | grep -om1 inet\ [^\/]*\/[0-9]* | cut -d' ' -f2)"
    if_aliases="$(ip a s ${iface} | grep -oP "inet .*${iface}:\d*$" | awk '{ print $2","$NF }')"
    [[ "${iface}" =~ ^(tun|tap)[0-9]+ ]] && is_vpn=1

    if [[ "${exclude_list}" =~ (^|\ )"${iface}"($|\ ) ]]; then
        # Ignore interfaces that we've been asked to exclude.
        continue
    elif [[ "${bridge_members}" =~ (^|\ )"${iface}"($|\ ) ]]; then
        bridge_member_with_ip=1
    elif [[ "${down_interfaces}" =~ (^|\ )"${iface}"($|\ ) ]] && ! [[ "${bridges}" =~ (^|\ )"${iface}"($|\ ) ]]; then
        # Do not list information for down interfaces, even if they have addresses
        # Bridges are the exception to this, since we still want to print members.
        continue
    elif [ -z "${address}" ] && ! [[ "${bridges}" =~ (^|\ )"${iface}"($|\ ) ]] && ! ( [[ "${wireless_interfaces}" =~ (^|\ )"${iface}"($|\ ) ]] && iwconfig ${iface} 2>/dev/null | grep -q "Access Point: [A-F0-9]" ); then
        # Do not print other UP interfaces without addresses.
        # Printing in a separate list.
        # Bridges are the exception to this, since we still want to print members.
        # Wireless interfaces that are up AND associated to an AP are also the exception to this.
        #     Assumes that iwconfig won't give any output after "Access Point: " that starts with a hexidecimal character (capitals for alphabet letters)
        other_up_interfaces="${other_up_interfaces} ${iface}"
        continue
    fi

    # To confirm, if we are still in this loop we are dealing with one of two-three things:
    # * An UP interface with an IP address
    # * A DOWN interface that is a bridge
    # * A DOWN interface that is an associated wireless interface
    # * A bridge member with an IP address
    if ! ((  ${bridge_member_with_ip:-0 } )); then
        if [ -z "${address}" ] || [[ "${address}" =~ \/ ]]; then
            printf " $(colour_interface ${iface}): $(colour_network_address "${address:-No Address}")"
        else
            # If the CIDR-form subnet mask is not already on IP output, then assume that it's a /32.
            # Most likely a tun_ interface.

            # If we can find a case in which the mask is something other than /32, then
            #     uncomment the commented code in this else statement, and adjust printf appropriately.
            # Get subnet mask for interface
            #unset display_mask
            #mask=$(ip a s ${iface} 2> /dev/null | grep -om1 inet\ [^\/]*\/[0-9]* | cut -d '/' -f 2)
            #if [ -n "${mask}" ]; then
            #    display_mask=/${mask}
            #fi
            printf " $(colour_interface ${iface}): $(colour_network_address "${address:-No Address}/32")"
        fi
    # Bridge members
    else
        unset bridge_member_with_ip # Unset for next loop
        # Only go deeper with bridge members if they have addresses, which is unexpected
        if [ -z "${address}" ]; then
            continue
        else
            printf " $(colour_interface ${iface}): \${color #${colour_alert}}Bridge Member w/ IP Address\${color}"
        fi
    fi

    if (( "${is_vpn:-0}" )); then
        printf " (%d routes)" "$(route -n | grep -w "${iface}" | wc -l)"
        if route -n | grep -w "${iface}" | grep -qm1 "^0\.0"; then
            if [ ${gateway_count} -gt 1 ]; then
                printf "\n  \${color #${colour_network}}Default Gateway \#%d (VPN Redirected)\${color}" "$(route -n | grep "^0\.0" | grep -wn "${iface}" | cut -d':' -f1)"
            else
                printf "\n  \${color #${colour_network}}Default Gateway (VPN Redirected)\${color}"
            fi
        fi
    elif route -n | grep -w "${iface}" | grep -q "^0\.0"; then
        if [ ${gateway_count} -gt 1 ]; then
            printf "\n  \${color #${colour_network}}Default Gateway \#%d \${color}" "$(route -n | grep "^0\.0" | grep -wn "${iface}" | cut -d':' -f1)"
        else
            printf "\n  \${color #${colour_network}}Default Gateway\${color}"
        fi
    fi

    if [ -f "/tmp/conky-common/labels/${iface}.label" ]; then
        printf "\n  %s" "$(shorten_string "$(cat "/tmp/conky-common/labels/${iface}.label")" 24)"
    fi

    # Grab start time and do filtering.
    start_time="$(cat "/tmp/conky-common/labels/${iface}.start" 2> /dev/null | grep -oPm1 "^\d+$")"
    if [ -n "${start_time}" ]; then
      current_time="$(date "+%s")"
      diff_time="$((${current_time}-${start_time}))"
      if [ "${diff_time}" -gt 0 ]; then
        printf "\n  Uptime: %s" "$(translate_seconds "${diff_time}")"
      fi
      # Do not care so much about unsetting these variables because
      #   they will definitely be overwritten next loop.
    fi

    # Unset address-related variable for next loop.
    unset address

    #####################
    # Wireless Handling #
    #####################

    # If we're looking at a wireless interface, print extra connection information.
    if [ -d "/sys/class/net/${iface}/wireless" ]; then
        printf '\n'
        mac="$(iwconfig ${iface} 2> /dev/null | grep -om1 "Access Point:\ [^\ ]*" | cut -d' ' -f 3)"
        # Attempt to look for a cached copy of the wireless summary to save a bit of time on label/vendor lookups.
        if [ -f "${tempRoot}/cache/wlan/${mac}.txt" ]; then
            cat "${tempRoot}/cache/wlan/${mac}.txt" | sed "s/INTERFACE/${iface}/g"
        else
        wireless_report=$(printf "  ESSID: \${wireless_essid INTERFACE}\\n  BSSID: ${mac} (\${wireless_link_qual INTERFACE}%%%%)\n")
            location="$(__get_mac_specific_location "${mac}" 2> /dev/null)"
            if [ -n "${location}" ]; then
                wireless_report="${wireless_report}\n$(printf "  AP Location: %s\n" "$(shorten_string "${location}" 24)")"
            else
                # Try to resolve vendor instead
                vendor="$(__get_mac_vendor "${mac}" 2> /dev/null)"
                if [ -n "${vendor}" ]; then
                    # Consider clipping output if necessary...
                    wireless_report="${wireless_report}\n$(printf "  AP Vendor: %s\n" "$(shorten_string "${vendor}" 24)")"
                fi
            fi
            mkdir -p "${tempRoot}/cache/wlan"
            printf "${wireless_report}\n" | tee "${tempRoot}/cache/wlan/${mac}.txt" | sed "s/INTERFACE/${iface}/g"
        fi

    ###################
    # Bridge Handling #
    ###################

    # If we're looking at a bridge interface, print member information
    elif [ -d "/sys/class/net/${iface}/bridge" ]; then
        members=$(brctl show ${iface} | sed -e '/bridge name/d' -e 's/\t/\ /g' | tr -d \\n | awk '{ $1="";$2="";$3="";print $0 }')

        if [[ "${down_interfaces}" =~ (^|\ )"${iface}"($|\ ) ]]; then
            printf " (\${color #${colour_warning}}DOWN\${color})\n"
        else
            printf "\n"
        fi

        if [ $(wc -w <<< "${members}") -gt "0" ]; then

            # "  Members:" is 10 characters
            characterIndex=10

            for member in ${members}; do
                ifaceLength=$(expr length "${member}")
                candidateLength=$((${characterIndex} + ${ifaceLength} + 2))
                if [[ "${down_interfaces}" =~ (^|\ )"${member}"($|\ ) ]]; then
                    memberDown="(\${color #${colour_warning}}D\${color})"
                    candidateLength=$((${candidateLength+3}))
                fi
                if [ ${candidateLength} -le ${characterWidthLimit} ]; then
                    member_list="${member_list} $(colour_interface ${member})${memberDown,}"
                    characterIndex=${candidateLength}
                else
                    member_list="${member_list}@    $(colour_interface ${member}),"
                    # Number of format characters on new line is 5 (4 spaces and a comma)
                    characterIndex=$((${ifaceLength+5}))
                fi
                unset memberDown
            done
            printf "  Members:${member_list}\n" | sed -e 's/,$//' -e 's/@/\n/g'
        else
            printf "  No Members\n"
        fi
    else
      printf "\n"
    fi

    # Print out any aliases that we've assigned to this interface.
    for alias_if in ${if_aliases}; do
      printf "  $(colour_interface $(cut -d',' -f 2 <<< "${alias_if}")): \${color #${colour_network_address}}%s\${color}\n" "$(cut -d',' -f 1 <<< "${alias_if}")"
    done

    if ! [[ "${down_interfaces}" =~ (^|\ )"${iface}"($|\ ) ]]; then
      printf "  Up: \${upspeed ${iface}}  Down: \${downspeed ${iface}}\n"
    fi
done

#######################
# Other UP Interfaces #
#######################

# List other interfaces that are up but do not have addresses.

# Interface hasn't been displayed previously (or is not deliberately excluded) if it does not match our pattern.

# " Other UP:" is 10 characters
characterIndex=10

for iface in ${other_up_interfaces}; do
    ifaceLength=$(expr length "${iface}")
    candidateLength=$((${characterIndex} + ${ifaceLength} + 2))
    if [ ${candidateLength} -lt ${characterWidthLimit} ]; then
        up_display_list="${up_display_list} $(colour_interface ${iface}),"
        characterIndex=${candidateLength}
    else
        up_display_list="${up_display_list}@    $(colour_interface ${iface}),"
        # Number of format characters on new line is 5 (4 spaces and a comma)
        characterIndex=$((${ifaceLength+5}))
    fi
done

[ -n "${up_display_list}" ] && printf "  Other UP:${up_display_list}\n" | sed -e 's/,$//' -e 's/@/\n/g'

###################
# Down Interfaces #
###################

# "  Down:" is 7 characters
characterIndex=7

for iface in ${down_interfaces}; do
    if [[ "${bridge_members}" =~ (^|\ )"${iface}"($|\ ) ]] || [[ "${bridges}" =~ (^|\ )"${iface}"($|\ ) ]]; then
        # If the interfaces is also a bridge member, then skip
        # Downed bridge members are specially marked in the interface display, regardless of whether they're up or not.
        continue
    fi

    ifaceLength=$(expr length "${iface}")
    candidateLength=$((${characterIndex} + ${ifaceLength} + 2))
    # Maybe it's the late hour that this was written at,
    #   but I cannot see what's different about the down interfaces
    #   that makes them need an extra hard-coded character
    if [ ${candidateLength} -le ${characterWidthLimit} ]; then
        down_display_list="${down_display_list} $(colour_interface ${iface}),"
        characterIndex=${candidateLength}
    else
        down_display_list="${down_display_list}@    $(colour_interface ${iface}),"
        # Number of format characters on new line is 5 (4 spaces and a comma)
        characterIndex=$((${ifaceLength+5}))
    fi
done

if [ -n "${down_display_list}" ]; then
  printf "  Down:${down_display_list}\n" | sed -e 's/,$//' -e 's/@/\n/g'
fi

###########################
# Networking Applications #
###########################

# Track active torrents.
# Note: pgrep will not respect searches for the full process name of 'transmission-cli'.
#       Anything beyond a 15th character is ignored.
#       The solution to this is to search for only 'tranmission-cl'
#       For the moment, trusting that there are no false positives that begin with 'transmission-cl'.
#       If such a false positive is ever found, then we could use the -a switch to list the full name, which could then be grepped for.
torrent_instances="$(pgrep -ac transmission-cl)"
if [ "${torrent_instances}" -gt 0 ]; then
    printf " Active Torrents: %d\n" "${torrent_instances}"
fi

##########################
##########################
## Incoming Connections ##
##########################
##########################

ephemeral_file="/proc/sys/net/ipv4/ip_local_port_range"
ephemeral_lower=$(awk '{print $1 }' < "${ephemeral_file}")

# Collect connections from netstat, then format with awk
connections_in="$(netstat -Wtun | grep ESTABLISHED \
    | awk -F' ' '{
          len = split($4, a, ":");
          l[1]=a[1];
          for(i = 2; i < len; i++)
            l[1] = l[1] ":" a[i]
          l[2]=a[len];
          len = split($5, a, ":");
          r[1]=a[1];
          for(i = 2; i < len; i++)
            r[1] = r[1] ":" a[i]
          r[2]=a[len];
          if(l[2] < '${ephemeral_lower}' && (r[2] > '${ephemeral_lower}' || $1 ~ /^tcp/) && ! (r[2] == 2049 && $1 ~ /^tcp/)){
            if(len == 4)
              print "_6_ " $1 " " r[1] " " l[1] " " l[2]
            else
              print r[1] "." l[1] "." l[2] "." $1 " " $1 " " r[1] " " l[1] " " l[2]
          }
      }' \
    | sort -t. -k1,1n -k2,2n -k3,3n -k4,4n -k 5,5n -k 6,6n -k 7,7n -k 8,8n -k 9,9n -k 10,10 \
    | cut -d' ' -f2- | uniq -c | grep --colour=never -Pvw '(127\.0\.0\.1|::1)' \
    | awk '{
        if(!($3 ~ /^(([0-9]){1,3}\.){3}([0-9]{1,3})$/)){
            # IPv6 (source is not in IPv4 foramt).
            if(length($3) > 25 && $1 > 1){
                pad = "\n    (" $2 "/" $5 ", Count: " $1 ")"
            } else if(length($3) > 25){
                pad = "\n    (" $2 "/" $5 ")"
            } else {
                pad=" (" $2 "/" $5 ")"
            }
            print " ${color #'${colour_network_address}'}" $3 "${color}" pad
        } else {
            # IPv4

            # Note: IPv4 addresses may mistakenly have a 'tcp6' label.
            # Strictly speaking, this SHOULD never happened, but it was observed with a MariaDB server.
            # The logic of this script will still treat things as an IPv4 connection.

            # Leaving the 'tcp6' in as a reminder that things are freaky and strange.
            # If I ever did want to strip out the '6': gensub(/(tcp)6?/,"\\1", "g", $2)
            print " ${color #'${colour_network_address}'}" $3 "${color}->${color #'${colour_network_address}'}" $4 "${color} ("$2"/"$5")"
        }
        if(length($3) <= 25 && $1 > 1){
            print "    Count: " $1
        }
    }')"
# A connection is considered incoming if the local port is below the lowest ephemeral port number AND the remote port is above the lowest ephemeral port number.
# TCP connections are somewhat excused and do not require the remote port to always be within the range.
# Excluding localhost connections, since it could get a bit rediculous.
# The special case with TCP/2049 is due to NFS mounting using a rediculously low local port (e.g. client's TCP/696 to server's TCP/2049).
# I *could* also filter out connections where the source address is the same as the destination address, but I choose not to at this time. Maybe some different colouring in the future?
# Confirming that UDP "connections" (extended open sockets) can actually show up and get printed out correctly, though I had to make a situation with nc to have an example to double-check.
# Reminder for re-testing (binds to udp/1234):
## Server (conky machine): nc -u -l 1234 > /dev/null
## Client: cat /dev/zero | nc -u any-address-but-localhost 1234

if [ -n "${connections_in}" ]; then
    # Print a separate header and report content.
    printf "\${color #${colour_network}}\${font Neuropolitical:size=16:bold}Incoming Connections\${font}\${color}\${hr}\n${connections_in}"
fi
