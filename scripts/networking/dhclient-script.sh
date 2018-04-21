#!/bin/bash
#
# dhclient-script: Network interface configuration script run by
#                  dhclient based on DHCP client communication
#
# Copyright (C) 2008-2014  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): David Cantrell <dcantrell@redhat.com>
#            Jiri Popelka <jpopelka@redhat.com>
#
# ----------
# This script is a rewrite/reworking on dhclient-script originally
# included as part of dhcp-970306:
# dhclient-script for Linux. Dan Halbert, March, 1997.
# Updated for Linux 2.[12] by Brian J. Murrell, January 1999.
# Modified by David Cantrell <dcantrell@redhat.com> for Fedora and RHEL
# ----------
#

PATH=/bin:/usr/bin:/sbin
# scripts in dhclient.d/ use $SAVEDIR (#833054)
export SAVEDIR=/var/lib/dhclient

LOGFACILITY="local7"
LOGLEVEL="notice"

ETCDIR="/etc/dhcp"

logmessage() {
    msg="${1}"
    logger -p "${LOGFACILITY}.${LOGLEVEL}" -t "NET" "dhclient: ${msg}"
}

eventually_add_hostnames_domain_to_search() {
# For the case when hostname for this machine has a domain that is not in domain_search list
# 1) get a hostname with `ipcalc --hostname` or `hostname`
# 2) get the domain from this hostname
# 3) add this domain to search line in resolv.conf if it's not already
#    there (domain list that we have recently added there is a parameter of this function)
# We can't do this directly when generating resolv.conf in make_resolv_conf(), because
# we need to first save the resolv.conf with obtained values before we can call `ipcalc --hostname`.
# See bug 637763
    search="${1}"
    if need_hostname; then
        status=1
        if [ -n "${new_ip_address}" ]; then
            eval $(/usr/bin/ipcalc --silent --hostname "${new_ip_address}" ; echo "status=$?")
        elif [ -n "${new_ip6_address}" ]; then
            eval $(/usr/bin/ipcalc --silent --hostname "${new_ip6_address}" ; echo "status=$?")
        fi

        if [ ${status} -eq 0 ]; then
            domain="$(cut -s -d "." -f 2- <<< "${HOSTNAME}")"
        fi
    else
          domain=$(hostname 2>/dev/null | cut -s -d "." -f 2-)
    fi

    if [ -n "${domain}" ] &&
       [ ! "${domain}" = "localdomain" ] &&
       [ ! "${domain}" = "localdomain6" ] &&
       [ ! "${domain}" = "(none)" ] &&
       [[ ! "${domain}" = *\ * ]]; then
       is_in="false"
       for s in ${search}; do
           if [ "${s}" = "${domain}" ] ||
              [ "${s}" = "${domain}." ]; then
              is_in="true"
           fi
       done

       if [ "${is_in}" = "false" ]; then
          # Add domain name to search list (#637763)
          sed -i -e "s/${search}/${search} ${domain}/" /etc/resolv.conf
       fi
    fi
}

exit_with_hooks() {
    exit_status="${1}"

    if [ -x ${ETCDIR}/dhclient-exit-hooks ]; then
        . ${ETCDIR}/dhclient-exit-hooks
    fi

    exit "${exit_status}"
}

quad2num() {
    if [ $# -eq 4 ]; then
        let n="${1} << 24 | ${2} << 16 | ${3} << 8 | ${4}"
        echo "${n}"
        return 0
    else
        echo "0"
        return 1
    fi
}

ip2num() {
    IFS='.' quad2num ${1}
}

num2ip() {
    let n="${1}"
    let o1="(${n} >> 24) & 0xff"
    let o2="(${n} >> 16) & 0xff"
    let o3="(${n} >> 8) & 0xff"
    let o4="${n} & 0xff"
    echo "${o1}.${o2}.${o3}.${o4}"
}

get_network_address() {
# get network address for the given IP address and (netmask or prefix)
    ip="${1}"
    nm="${2}"

    if [ -n "${ip}" -a -n "${nm}" ]; then
        if [[ "${nm}" = *.* ]]; then
            ipcalc -s -n "${ip}" "${nm}" | cut -d '=' -f 2
        else
            ipcalc -s -n "${ip}/${nm}" | cut -d '=' -f 2
        fi
    fi
}

get_prefix() {
# get prefix for the given IP address and mask
    ip="${1}"
    nm="${2}"

    if [ -n "${ip}" -a -n "${nm}" ]; then
        ipcalc -s -p "${ip}" "${nm}" | cut -d '=' -f 2
    fi
}

class_bits() {
    let ip=$(IFS='.' ip2num "${1}")
    let bits=32
    let mask='255'
    for ((i=0; i <= 3; i++, 'mask<<=8')); do
        let v='ip&mask'
        if [ "$v" -eq 0 ] ; then
             let bits-=8
        else
             break
        fi
    done
    echo $bits
}

is_router_reachable() {
    # handle DHCP servers that give us a router not on our subnet
    router="${1}"
    routersubnet="$(get_network_address "${router}" "${new_subnet_mask}")"
    mysubnet="$(get_network_address "${new_ip_address}" "${new_subnet_mask}")"

    if [ ! "${routersubnet}" = "${mysubnet}" ]; then
        # TODO: This function should not have side effects such as adding or
        # removing routes. Can this be done with "ip route get" or similar
        # instead? Are there cases that rely on this route being created here?
        ip -4 route replace "${router}/32" dev "${interface}"
        if [ "$?" -ne 0 ]; then
            logmessage "failed to create host route for ${router}"
            return 1
        fi
    fi

    return 0
}

add_default_gateway() {
    router="${1}"

    if is_router_reachable "${router}" ; then
        if [ $# -gt 1 ] && [ -n "${2}" ] && [[ "${2}" -gt 0 ]]; then
            ip -4 route replace default via "${router}" dev "${interface}" metric "${2}"
        else
            ip -4 route replace default via "${router}" dev "${interface}"
        fi
        if [ $? -ne 0 ]; then
            logmessage "failed to create default route: ${router} dev ${interface} ${metric}"
            return 1
        else
            return 0
        fi
    fi

    return 1
}

execute_client_side_configuration_scripts() {
# execute any additional client side configuration scripts we have
    if [ "${1}" == "config" ] || [ "${1}" == "restore" ]; then
        for f in ${ETCDIR}/dhclient.d/*.sh ; do
            if [ -x "${f}" ]; then
                subsystem="${f%.sh}"
                subsystem="${subsystem##*/}"
                . "${f}"
                "${subsystem}_${1}"
            fi
        done
    fi
}

flush_dev() {
# Instead of bringing the interface down (#574568)
# explicitly clear ARP cache and flush all addresses & routes.
    ip -4 addr flush dev "${1}" >/dev/null 2>&1
    ip -4 route flush dev "${1}" >/dev/null 2>&1
    ip -4 neigh flush dev "${1}" >/dev/null 2>&1
}

remove_old_addr() {
    if [ -n "${old_ip_address}" ]; then
        if [ -n "${old_prefix}" ]; then
            ip -4 addr del "${old_ip_address}/${old_prefix}" dev "${interface}" >/dev/null 2>&1
        else
            ip -4 addr del "${old_ip_address}" dev "${interface}" >/dev/null 2>&1
        fi
    fi
}

dhconfig() {
    if [ -n "${old_ip_address}" ] && [ -n "${alias_ip_address}" ] &&
       [ ! "${alias_ip_address}" = "${old_ip_address}" ]; then
        # possible new alias, remove old alias first
        ip -4 addr del "${old_ip_address}" dev "${interface}" label "${interface}:0"
    fi

    if [ -n "${old_ip_address}" ] &&
       [ ! "${old_ip_address}" = "${new_ip_address}" ]; then
        # IP address changed. Delete all routes, and clear the ARP cache.
        flush_dev "${interface}"
    fi

    # make sure the interface is up
    ip link set dev "${interface}" up

    # replace = add if it doesn't exist or override (update lifetimes) if it's there
    ip -4 addr replace "${new_ip_address}/${new_prefix}" broadcast "${new_broadcast_address}" dev "${interface}" \
       valid_lft "${new_dhcp_lease_time}" preferred_lft "${new_dhcp_lease_time}" >/dev/null 2>&1

    if [ "${reason}" = "BOUND" ] || [ "${reason}" = "REBOOT" ] ||
       [ ! "${old_ip_address}" = "${new_ip_address}" ] ||
       [ ! "${old_subnet_mask}" = "${new_subnet_mask}" ] ||
       [ ! "${old_network_number}" = "${new_network_number}" ] ||
       [ ! "${old_broadcast_address}" = "${new_broadcast_address}" ] ||
       [ ! "${old_routers}" = "${new_routers}" ] ||
       [ ! "${old_interface_mtu}" = "${new_interface_mtu}" ]; then

        # The 576 MTU is only used for X.25 and dialup connections
        # where the admin wants low latency.  Such a low MTU can cause
        # problems with UDP traffic, among other things.  As such,
        # disallow MTUs from 576 and below by default, so that broken
        # MTUs are ignored, but higher stuff is allowed (1492, 1500, etc).
        if [ -n "${new_interface_mtu}" ] && [ "${new_interface_mtu}" -gt 576 ]; then
            ip link set dev "${interface}" mtu "${new_interface_mtu}"
        fi

        # static routes
        if [ -n "${new_classless_static_routes}" ] ||
           [ -n "${new_static_routes}" ]; then
            if [ -n "${new_classless_static_routes}" ]; then
                IFS=', |' static_routes=(${new_classless_static_routes})
            else
                IFS=', |' static_routes=(${new_static_routes})
            fi
            route_targets=()

            for((i=0; i<${#static_routes[@]}; i+=2)); do
                target=${static_routes[$i]}
                if [ -n "${new_classless_static_routes}" ]; then
                    if [ "${target}" = "0" ]; then
                        # If the DHCP server returns both a Classless Static Routes option and
                        # a Router option, the DHCP client MUST ignore the Router option. (RFC3442)
                        new_routers=""
                        prefix="0"
                    else
                        prefix=${target%%.*}
                        target=${target#*.}
                        IFS="." target_arr=(${target})
                        unset IFS
                        ((pads=4-${#target_arr[@]}))
                        for j in $(seq $pads); do
                            target="${target}.0"
                        done

                        # Client MUST zero any bits in the subnet number where the corresponding bit in the mask is zero.
                        # In other words, the subnet number installed in the routing table is the logical AND of
                        # the subnet number and subnet mask given in the Classless Static Routes option. (RFC3442)
                        target="$(get_network_address "${target}" "${prefix}")"
                    fi
                else
                    prefix=$(class_bits "${target}")
                fi
                gateway=${static_routes[$i+1]}

                # special case 0.0.0.0 to allow static routing for link-local addresses
                # (including IPv4 multicast) which will not have a next-hop (#769463, #787318)
                if [ "${gateway}" = "0.0.0.0" ]; then
                    valid_gateway=0
                    scope='scope link'
                else
                    is_router_reachable "${gateway}"
                    valid_gateway=$?
                    scope=''
                fi
                if [ "${valid_gateway}" -eq 0 ]; then
                    metric=''
                    for t in "${route_targets[@]}"; do
                        if [ "${t}" = "${target}" ]; then
                            if [ -z "${metric}" ]; then
                                metric=1
                            else
                                ((metric=metric+1))
                            fi
                        fi
                    done

                    if [ -n "${metric}" ]; then
                        metric="metric ${metric}"
                    fi

                    ip -4 route replace "${target}/${prefix}" proto static via "${gateway}" dev "${interface}" ${metric} ${scope}

                    if [ $? -ne 0 ]; then
                        logmessage "failed to create static route: ${target}/${prefix} via ${gateway} dev ${interface} ${metric}"
                    else
                        route_targets=(${route_targets[@]} ${target})
                    fi
                fi
            done
        fi

        # gateways
        if [[ ( "${DEFROUTE}" != "no" ) &&
              (( -z "${GATEWAYDEV}" ) || ( "${GATEWAYDEV}" = "${interface}" )) ]]; then
            if [[ ( -z "${GATEWAY}" ) ||
                  (( -n "${DHCLIENT_IGNORE_GATEWAY}" ) && ( "${DHCLIENT_IGNORE_GATEWAY}" = [Yy]* )) ]]; then
                metric="${METRIC:-}"
                let i="${METRIC:-0}"
                default_routers=()

                for router in ${new_routers} ; do
                    added_router=-

                    for r in "${default_routers[@]}" ; do
                        if [ "${r}" = "${router}" ]; then
                            added_router=1
                        fi
                    done

                    if [ -z "${router}" ] ||
                       [ "${added_router}" = "1" ] ||
                       [ "$(IFS='.' ip2num ${router})" -le 0 ] ||
                       [[ ( "${router}" = "${new_broadcast_address}" ) &&
                          ( "${new_subnet_mask}" != "255.255.255.255" ) ]]; then
                        continue
                    fi

                    default_routers=(${default_routers[@]} ${router})
                    add_default_gateway "${router}" "${metric}"
                    let i=i+1
                    metric=${i}
                done
            elif [ -n "${GATEWAY}" ]; then
                routersubnet=$(get_network_address "${GATEWAY}" "${new_subnet_mask}")
                mysubnet=$(get_network_address "${new_ip_address}" "${new_subnet_mask}")

                if [ "${routersubnet}" = "${mysubnet}" ]; then
                    ip -4 route replace default via "${GATEWAY}" dev "${interface}"
                fi
            fi
        fi
    fi

    if [ ! "${new_ip_address}" = "${alias_ip_address}" ] &&
       [ -n "${alias_ip_address}" ]; then
        # Reset the alias address (fix: this should really only do this on changes)
        ip -4 addr flush dev "${interface}" label "${interface}:0" >/dev/null 2>&1
        ip -4 addr replace "${alias_ip_address}/${alias_prefix}" broadcast "${alias_broadcast_address}" dev "${interface}" label "${interface}:0"
        ip -4 route replace "${alias_ip_address}/32" dev "${interface}"
    fi

    # After dhclient brings an interface UP with a new IP address, subnet mask,
    # and routes, in the REBOOT/BOUND states -> search for "dhclient-up-hooks".
    if [ "${reason}" = "BOUND" ] || [ "${reason}" = "REBOOT" ] ||
       [ ! "${old_ip_address}" = "${new_ip_address}" ] ||
       [ ! "${old_subnet_mask}" = "${new_subnet_mask}" ] ||
       [ ! "${old_network_number}" = "${new_network_number}" ] ||
       [ ! "${old_broadcast_address}" = "${new_broadcast_address}" ] ||
       [ ! "${old_routers}" = "${new_routers}" ] ||
       [ ! "${old_interface_mtu}" = "${new_interface_mtu}" ]; then

        if [ -x "${ETCDIR}/dhclient-${interface}-up-hooks" ]; then
            . "${ETCDIR}/dhclient-${interface}-up-hooks"
        elif [ -x ${ETCDIR}/dhclient-up-hooks ]; then
            . ${ETCDIR}/dhclient-up-hooks
        fi
    fi

    if [ -n "${new_host_name}" ] && need_hostname; then
        hostname "${new_host_name}" || echo "See -nc option in dhclient(8) man page."
    fi

    if [[ ( "${DHCP_TIME_OFFSET_SETS_TIMEZONE}" = [yY1]* ) &&
          ( -n "${new_time_offset}" ) ]]; then
        # DHCP option "time-offset" is requested by default and should be
        # handled.  The geographical zone abbreviation cannot be determined
        # from the GMT offset, but the $ZONEINFO/Etc/GMT$offset file can be
        # used - note: this disables DST.
        ((z=new_time_offset/3600))
        ((hoursWest=$(printf '%+d' $z)))

        if (( $hoursWest < 0 )); then
            # tzdata treats negative 'hours west' as positive 'gmtoff'!
            ((hoursWest*=-1))
        fi

        tzfile=/usr/share/zoneinfo/Etc/GMT$(printf '%+d' ${hoursWest})
        if [ -e "${tzfile}" ]; then
            cp -fp "${tzfile}" /etc/localtime
            touch /etc/localtime
        fi
    fi

    execute_client_side_configuration_scripts "config"
}

# Section 18.1.8. (Receipt of Reply Messages) of RFC 3315 says:
# The client SHOULD perform duplicate address detection on each of
# the addresses in any IAs it receives in the Reply message before
# using that address for traffic.
add_ipv6_addr_with_DAD() {
            ip -6 addr replace "${new_ip6_address}/${new_ip6_prefixlen}" \
                dev "${interface}" scope global valid_lft "${new_max_life}" \
                                          preferred_lft "${new_preferred_life}"

            # repeatedly test whether newly added address passed
            # duplicate address detection (DAD)
            for i in $(seq 5); do
                sleep 1 # give the DAD some time

                addr=$(ip -6 addr show dev "${interface}" \
                       | grep "${new_ip6_address}/${new_ip6_prefixlen}")

                # tentative flag == DAD is still not complete
                tentative=$(echo "${addr}" | grep tentative)
                # dadfailed flag == address is already in use somewhere else
                dadfailed=$(echo "${addr}" | grep dadfailed)

                if [ -n "${dadfailed}" ] ; then
                    # address was added with valid_lft/preferred_lft 'forever', remove it
                    ip -6 addr del "${new_ip6_address}/${new_ip6_prefixlen}" dev "${interface}"
                    exit_with_hooks 3
                fi
                if [ -z "${tentative}" ] ; then
                    if [ -n "${addr}" ]; then
                        # DAD is over
                        return 0
                    else
                        # address was auto-removed (or not added at all)
                        exit_with_hooks 3
                    fi
                fi
            done
            return 0
}

dh6config() {
    if [ -n "${old_ip6_prefix}" ] ||
       [ -n "${new_ip6_prefix}" ]; then
        echo "Prefix ${reason} old=${old_ip6_prefix} new=${new_ip6_prefix}"
        exit_with_hooks 0
    fi

    case "${reason}" in
        BOUND6)
            if [ -z "${new_ip6_address}" ] ||
               [ -z "${new_ip6_prefixlen}" ]; then
                exit_with_hooks 2
            fi

            add_ipv6_addr_with_DAD
            ;;

        RENEW6|REBIND6)
            if [[ -n "${new_ip6_address}" ]] &&
               [[ -n "${new_ip6_prefixlen}" ]]; then
               if [[  ! "${new_ip6_address}" = "${old_ip6_address}" ]]; then
                   [[ -n "${old_ip6_address}" ]] && ip -6 addr del "${old_ip6_address}" dev "${interface}"
               fi
               # call it even if new_ip6_address = old_ip6_address to update lifetimes
               add_ipv6_addr_with_DAD
            fi

            ;;

        DEPREF6)
            if [ -z "${new_ip6_prefixlen}" ]; then
                exit_with_hooks 2
            fi

            ip -6 addr change "${new_ip6_address}/${new_ip6_prefixlen}" \
                dev "${interface}" scope global preferred_lft 0
            ;;
    esac

    execute_client_side_configuration_scripts "config"
}


#
# ### MAIN
#

if [ -x ${ETCDIR}/dhclient-enter-hooks ]; then
    exit_status=0

    # dhclient-enter-hooks can abort dhclient-script by setting
    # the exit_status variable to a non-zero value
    . ${ETCDIR}/dhclient-enter-hooks
    if [ ${exit_status} -ne 0 ]; then
        exit ${exit_status}
    fi
fi

if [ ! -r /etc/sysconfig/network-scripts/network-functions ]; then
    echo "Missing /etc/sysconfig/network-scripts/network-functions, exiting." >&2
    exit 1
fi

if [ ! -r /etc/rc.d/init.d/functions ]; then
    echo "Missing /etc/rc.d/init.d/functions, exiting." >&2
    exit 1
fi

. /etc/sysconfig/network-scripts/network-functions
. /etc/rc.d/init.d/functions

if [ -f /etc/sysconfig/network ]; then
    . /etc/sysconfig/network
fi

if [ -f /etc/sysconfig/networking/network ]; then
    . /etc/sysconfig/networking/network
fi

cd /etc/sysconfig/network-scripts
CONFIG="${interface}"
need_config "${CONFIG}"
source_config >/dev/null 2>&1

# In case there's some delay in rebinding, it might happen, that the valid_lft drops to 0,
# address is removed by kernel and then re-added few seconds later by dhclient-script.
# With this work-around the address lives a minute longer.
# "4294967235" = infinite (forever) - 60
[[ "${new_dhcp_lease_time}" -lt "4294967235" ]] && new_dhcp_lease_time=$((new_dhcp_lease_time + 60))
[[ "${new_max_life}" -lt "4294967235" ]] && new_max_life=$((new_max_life + 60))

new_prefix="$(get_prefix "${new_ip_address}" "${new_subnet_mask}")"
old_prefix="$(get_prefix "${old_ip_address}" "${old_subnet_mask}")"
alias_prefix="$(get_prefix "${alias_ip_address}" "${alias_subnet_mask}")"

case "${reason}" in
    MEDIUM|ARPCHECK|ARPSEND)
        # Do nothing
        exit_with_hooks 0
        ;;

    PREINIT)
        if [ -n "${alias_ip_address}" ]; then
            # Flush alias, its routes will disappear too.
            ip -4 addr flush dev "${interface}" label "${interface}:0" >/dev/null 2>&1
        fi

        # upstream dhclient-script removes (ifconfig $interface 0 up) old adresses in PREINIT,
        # but we sometimes (#125298) need (for iSCSI/nfs root to have a dhcp interface) to keep the existing ip
        # flush_dev ${interface}
        ip link set dev "${interface}" up
        if [ -n "${DHCLIENT_DELAY}" ] && [ "${DHCLIENT_DELAY}" -gt 0 ]; then
            # We need to give the kernel some time to get the interface up.
            sleep "${DHCLIENT_DELAY}"
        fi

        exit_with_hooks 0
        ;;

    PREINIT6)
        # ensure interface is up
        ip link set dev "${interface}" up

        # remove any stale addresses from aborted clients
        ip -6 addr flush dev "${interface}" scope global permanent

        # we need a link-local address to be ready (not tentative)
        for i in $(seq 50); do
            linklocal=$(ip -6 addr show dev "${interface}" scope link)
            # tentative flag means DAD is still not complete
            tentative=$(echo "${linklocal}" | grep tentative)
            [[ -n "${linklocal}" && -z "${tentative}" ]] && exit_with_hooks 0
            sleep 0.1
        done

        exit_with_hooks 0
        ;;

    BOUND|RENEW|REBIND|REBOOT)
        if [ -z "${interface}" ] || [ -z "${new_ip_address}" ]; then
            exit_with_hooks 2
        fi
        if arping -D -q -c2 -I "${interface}" "${new_ip_address}"; then
            dhconfig
            exit_with_hooks 0
        else  # DAD failed, i.e. address is already in use
            ARP_REPLY=$(arping -D -c2 -I "${interface}" "${new_ip_address}" | grep reply | awk '{print toupper($5)}' | cut -d "[" -f2 | cut -d "]" -f1)
            OUR_MACS=$(ip link show | grep link | awk '{print toupper($2)}' | uniq)
            if [[ "${OUR_MACS}" = *"${ARP_REPLY}"* ]]; then
                # the reply can come from our system, that's OK (#1116004#c33)
                dhconfig
                exit_with_hooks 0
            else
                exit_with_hooks 1
            fi
        fi
        ;;

    BOUND6|RENEW6|REBIND6|DEPREF6)
        dh6config
        exit_with_hooks 0
        ;;

    EXPIRE6|RELEASE6|STOP6)
        if [ -z "${old_ip6_address}" ] || [ -z "${old_ip6_prefixlen}" ]; then
            exit_with_hooks 2
        fi

        ip -6 addr del "${old_ip6_address}/${old_ip6_prefixlen}" \
            dev "${interface}"

        execute_client_side_configuration_scripts "restore"

        if [ -x "${ETCDIR}/dhclient-${interface}-down-hooks" ]; then
            . "${ETCDIR}/dhclient-${interface}-down-hooks"
        elif [ -x ${ETCDIR}/dhclient-down-hooks ]; then
            . ${ETCDIR}/dhclient-down-hooks
        fi

        exit_with_hooks 0
        ;;

    EXPIRE|FAIL|RELEASE|STOP)
        execute_client_side_configuration_scripts "restore"

        if [ -x "${ETCDIR}/dhclient-${interface}-down-hooks" ]; then
            . "${ETCDIR}/dhclient-${interface}-down-hooks"
        elif [ -x ${ETCDIR}/dhclient-down-hooks ]; then
            . ${ETCDIR}/dhclient-down-hooks
        fi

        if [ -n "${alias_ip_address}" ]; then
            # Flush alias
            ip -4 addr flush dev "${interface}" label "${interface}:0" >/dev/null 2>&1
        fi

        # upstream script sets interface down here,
        # we only remove old ip address
        #flush_dev ${interface}
        remove_old_addr

        if [ -n "${alias_ip_address}" ]; then
            ip -4 addr replace "${alias_ip_address}/${alias_prefix}" broadcast "${alias_broadcast_address}" dev "${interface}" label "${interface}:0"
            ip -4 route replace "${alias_ip_address}/32" dev "${interface}"
        fi

        exit_with_hooks 0
        ;;

    TIMEOUT)
        if [ -n "${new_routers}" ]; then
            if [ -n "${alias_ip_address}" ]; then
                ip -4 addr flush dev "${interface}" label "${interface}:0" >/dev/null 2>&1
            fi

            ip -4 addr replace "${new_ip_address}/${new_prefix}" \
                broadcast "${new_broadcast_address}" dev "${interface}" \
                valid_lft "${new_dhcp_lease_time}" preferred_lft "${new_dhcp_lease_time}"
            set ${new_routers}

            if ping -q -c 1 -w 10 -I "${interface}" "${1}"; then
                dhconfig
                exit_with_hooks 0
            fi

            #flush_dev ${interface}
            remove_old_addr
            exit_with_hooks 1
        else
            exit_with_hooks 1
        fi
        ;;

    *)
        logmessage "unhandled state: ${reason}"
        exit_with_hooks 1
        ;;
esac

exit_with_hooks 0
