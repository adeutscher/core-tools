#!/bin/bash

# If CONKY_DISABLE_FILES evaluates to true, then exit immediately.
# All of our file system parsing revolves around parsing /proc/1/mountinfo.
#   If this file cannot be reached (I cannot imagine that it would not exist altogether), then do not bother continuing either.
#   Do not print an error in either case.
if (( "${CONKY_DISABLE_FILES}" )) || [ ! -r "/proc/1/mountinfo" ]; then
    exit 0
fi

. functions/common.sh 2> /dev/null
. functions/network-addresses.sh 2> /dev/null

#############
# Inventory #
#############

# Note: Debian-based (e.g. Ubuntu 12.04) and RHEL-based (e.g. CentOS 6, Fedora 23) have slightly different formats for /proc/1/mountinfo.
#   RHEL has an extra field between some of the fields that we are looking under.
# In order, we are after the following fields:
#   Mount bind source (will just be '/' otherwise).
#   Mount point, file system is mounted to here.
#   File system type
#   Device file or network path of file system
#   Options
if [ "$(head -n1 /proc/1/mountinfo | grep -o " " | wc -l)" -eq 10 ]; then
    # RHEL-observed format.
    cut_fields="4,5,9,10,11"
else
    # Debian-observed format
    cut_fields="4,5,8,9,10"
fi

# Basic file systems: / and /home (if separate from /)
root_file_system=$(cut -d' ' -f ${cut_fields} < /proc/1/mountinfo | grep "/ / " | sed 's/ /\\236/g')

# If our home directory is within /home, apply an extra sed expression
if [[ "${HOME}" =~ ^/home ]]; then
  # If my home directory is in a partition mounted on /home, then I want it to be displayed as simply '~'
  # The extra expression will cause this script to replace part of the displayed file path with '~' before it is displayed.
  home_file_system=$(cut -d' ' -f ${cut_fields} < /proc/1/mountinfo | grep " /home " | sed -e "s| /home | ${HOME} |g" -e 's/ /\\236/g')
else
  home_file_system=$(cut -d' ' -f ${cut_fields} < /proc/1/mountinfo | grep " /home " | sed 's/ /\\236/g')
fi

## Dynamically include other significant mounted file systems.
# File system pattern shows the following mounted file system types:
#   - tmpfs
#   - Any fuse file system
#   - ext*
#   - cifs (Samba) file systems
#   - nfs
#   - File systems containing 'fat'
#   - NTFS
#   - UDF

# Out of the above listed file systems, mount point pattern excludes the following mountpoints:
#   - /, as this path is handled separately
#   - /home (or parent file system), as this path is handled separately.
#   - Anything mounted to or within /dev, /sys, /tmp, or /boot
#   - Anything mounted directly onto /run
#   - /run/cmanager/fs and /run/lock, two tmpfs directories on Ubuntu systems
#   - gvfsd file system at /run/user/${UID}/gvfs
# This should cover all other system-specific, temporary (USB drives, SD cards), or network, network file systems, etc.
extra_file_systems="$(cut -d' ' -f ${cut_fields} < /proc/1/mountinfo | egrep ' (ext.|tmpfs|cifs|nfs4?|vfat|iso9660|fuse\.[^\ ]*|ntfs(\-3g)?|btrfs|fuseblk|udf|hfsplus) ' | egrep -v '^/ / |(/ ((/dev|/sys|/boot|/tmp)|/run |/run/user/\d?|/gvfs|/run/cmanager/fs|/run/lock|/lib/live|/home | / / ))' | sort -t' ' -k1,2 | sed -e 's/ /\\236/g' -e 's/\$/\$\$/g')"

##########
# Header #
##########

printf "\${color #${colour_local_path}}\${font Neuropolitical:size=16:bold}File Systems\${font}\${color}\${hr}\n"

# Cycle through all collected file systems, and print information.
for raw_fs_data in ${root_file_system} ${home_file_system} ${extra_file_systems}; do

    # Reverse encoding
    fs_data="$(sed 's/\\236/ /g' <<< "${raw_fs_data}")"

    # FS Stored in /proc/1/mountinfo
    fs=$(cut -d' ' -f2  <<< "${fs_data}" | sed 's/\\040/ /g' )

    if grep -Pqwm1 "${fs}" <<< "${CONKY_IGNORE_FS}"; then
        # Skip ignored file system.
        # Note: Might not play nicely with particular wacky
        #         mount points with spaces in the path at the moment
        #       Example: If someone had mount points at "/var/doom"
        #                  and "/var/doom gloom" but only wanted to
        #                  ignore "/var/doom"
        #       Assuming that kind of case to be rediculously
        #         rare for the moment.
        continue
    fi

    fs_bind_location=$(cut -d' ' -f1  <<< "${fs_data}" | sed 's/\\040/ /g' )
    fs_type=$(cut -d' ' -f3 <<< "${fs_data}" | sed 's/unknown/???/g')
    fs_source=$(cut -d' ' -f4  <<< "${fs_data}" | sed 's/\\040/ /g' )
    fs_options=$(cut -d' ' -f5  <<< "${fs_data}" | sed 's/\\040/ /g' )
    # Set default options
    print_usage=1
    unset extra_text

    # Substitute home directory path for '~' and shorten.
    fs_title="$(shorten_string "$(sed "s|^${HOME}|\\~|g" <<< "${fs}")" "$((34-$(expr length "${fs_type}")))")"

    # If the target directory does not even exist, do not bother continuing through the loop.
    # Made for static systems, since some target file systems are dynamically listed off of find command.
    [ -d "${fs}" ] || continue

    # Special colour for network-based file systems.
    if egrep -qm1 "cifs|nfs|fuse\.obexfs" <<< "${fs_type}"; then
        fs_colour=${colour_network}
    else
        fs_colour=${colour_local_path}
    fi

    # Apply a special bracket colour to read-only file systems.
    unset bracket_colour
    if egrep -q -e "(^|,)ro($|,)" <<< "${fs_options}"; then
        bracket_colour=red
    fi

    printf  "\${color #${fs_colour}}${fs_title}\$color \${color ${bracket_colour}}(\${color red}${fs_type}\$color\${color ${bracket_colour}})\$color\n"
    
    if ! grep -q "^/$" <<< "${fs_bind_location}" && ! [[ "${fs_type}" =~ "cifs" ]]; then
        # Avoid redundant information by treating bind mounts differently.

        # CIFS for bind mounts is still quite a bit of a pickle.
        # Nothing in a `findmnt -nD` call or /proc/1/mountinfo line for a particular mount reveals its true origin location.
        # I was tempted to try to look for "unambiguous bind mounts" (e.g. if the only other mount of the share is to a higher level),
        #     but another issue put all the necessary nails in the proverbial coffin:
        # It is also not possible to tell a CIFS bind mount apart from a direct mount to a deeper folder in the share
        #     (for example, directly mounting //10.11.12.13/share/inner would appear as a false positive for a bind mount).

        # Until another option shows up to solve the above hurdles, I will NOT be covering CIFS bind mounts.
        # Will just have to suffer through redundant information if we run across this edge case.

        # Get the path to parent file system (as the "fs_source" variable will be to a device file like /dev/sda1 or /dev/mapper/machine-home).
        # This is necessary because "fs_bind_location" will not display the entire file path.
        # For example: Say that /home is a separate file system from / and /home/user is bind-mounted to /mnt.
        #     In that example, "fs_bind_location" would only show "/user"
        fs_bind_parent="$(findmnt -D "${fs_source}" | grep "${fs_source[^}\[]" | awk -F' ' '{ if($7 != "/"){ print $7 }}' )"
        printf " Bind: \${color #${fs_colour}}%s\${color}\n" "$(shorten_string "${fs_bind_parent}${fs_bind_location}" 29)"
        # Note: In cases of multiple binds (e.g. A is bound to B, and B is bound to C), mountinfo will still show the original parent.

    elif [[ "${fs_type}" != "-" ]]; then
        # If df/findmnt reports disk usage as a "-", then we will not be able to get these numbers through conky either.
        # If the file system is not supported by conky, do not try to print usage information.


        # If the file system is a far-away network file system like NFS or CIFS, do not show the usage bar.
        # Far-away file systems could cause conky to seize up, especially if bandwidth is taxed or if access to the network is killed without unmounting.
        # Removing the usage bar removes conky from caring at all about the status of the connection.
        # Does not account for some wise guy using nbd-client/nbd-server to directly mount a remote hard drive...

        # Most of the time for me, a faraway file system is a over a VPN connection to a distant location.
        # For now, a far-away network file system is identified as any connection that has to go through a gateway.

        # TODO: Find a way to recycle the original idea of using a per-mount flag, but this time to mark a "near-ish" server that needs to go through a gateway BUT has a reliably low latency that showing the usage bar wouldn't be the end of the world for performance.
        # TODO: Apply this new far-away approach to NFS as well. Need to check if the fs option is different.
        if [[ "${fs_type}" =~ (cifs|nfs\d{1,}) ]]; then
            if (( ! ${CONKY_ALL_NFS_FAR-0} )) && [ -z "${localNetworks}" ]; then
                # Only get a list of networks if we need to (i.e. if a CIFS system is mounted)
                # This avoids calling twice if we have multiple CIFS shares mounted.

                # Ideally, we would only need to use the gateway column out of the route command to get a faraway network.
                # However, VPN through openconnect (client for Cisco AnyConnect) pulls some sort of shenanigans
                #     that I don't fully understand at the moment to have our remote networks still display a gateway of 0.0.0.0.
                # Note: When checking on this later, I was not able to reproduce the route wackiness. Still leaving this special case in.
                # Since openconnect does this, we will also limit local networks to anything without a tun_ (VPN interface)
                #     or tap_ adapter (alternate VPN adapter. This was going to be an acceptable gap, but we may as well filter it if we're already here)
                # The only gap this would leave would be a super-duper low latency VPN that I wanted to still get usage information for. So a rediculously tiny gap.
                for network in $(route -n | awk '{ if($2 == "0.0.0.0" && $8 !~ /^t(un|ap)/ ){ print $1"/"$3 } }'); do
                    # Convert to numerical values just the once as well.
                    localNetworks="${localNetworks}\n$(cidr-low-dec "${network}"),$(cidr-high-dec "${network}")"
                done
            fi

            # Assume remote IP until proven otherwise.
            extra_text=" (far)"
            print_usage=0

            if (( ${CONKY_ALL_NFS_FAR-0} )); then
                # Skip these checks entirely if CONKY_ALL_NFS_FAR is set
                # Intentionally skipping printing "(far)" text.
                unset extra_text
            else
                # Get share IP address
                shareAddress=$(ip2dec "$(grep -o "addr=[^,]*" <<< "${fs_options}" | cut -d= -f2)")

                if (( $(awk -F, '{if('"$shareAddress"' >= $1 && '"$shareAddress"' <= $2){print "1"; exit(0)}} DONE { print "0" }' <<< "$(printf "${localNetworks}")") )); then
                    unset extra_text
                    print_usage=1
                fi
            fi
        elif [[ "${fs_type}" =~ ^iso9660$ ]]; then  
            print_usage=0
        fi

        if (( ${print_usage} )); then
            printf " Usage: \${fs_used ${fs}}/\${fs_size ${fs}} - \${fs_used_perc ${fs}}%% \${fs_bar 6 ${fs}}\n"
        fi

        # Print remote location for CIFS.
        if [[ "${fs_type}" =~ "cifs" ]]; then
                remote_point="$(shorten_string "${fs_source}" 31)"
                printf " Share%s: \${color #${colour_network}}%s\${color}\n" "${extra_text}" "$(shorten_string ${remote_point} 23)"
        elif [[ "${fs_type}" =~ nfs4 ]]; then
                remote_point="$(shorten_string "${fs_source}" 31)"
                printf " Dir%s: \${color #${colour_network}}%s\${color}\n" "${extra_text}" "$(shorten_string ${remote_point} 28)"
        fi
        # TODO: Do similarly to print the remote location for NFS.
    fi
done

# Experimental: RAID rebuild display.
# Only interested in RAID arrays that are rebuilding for the moment.
# A stable array is not newsworthy.
if [ -r "/proc/mdstat" ]; then
  # Assumed format of output heading into awk (if we have output at all):
  # md0 : active raid1 sdc1[1] sdb1[0]
  #       2930134464 blocks super 1.2 [2/2] [UU]
  #       [===============>.....]  resync = 79.1% (2319136896/2930134464) finish=115.7min speed=87983K/sec
  resyncing_arrays="$(cat "/proc/mdstat" | sed -e '/^unused devices:/d' | grep -A2 "^[a-z]" | grep -B2 "resync =" | awk -F' ' 'BEGIN{stage=1}{if(stage==1){device=$1;type=$4;stage=2} else if(stage==2){stage=3} else if(stage==3){stage=1; split($6,s,"="); if(s[2]){sub(/\.[0-9]*/, "", s[2])}; print " '"\${color ${colour_local_path}}"'/dev/" device "'"\${color}"'(" type "): "  $4 "(ETC: " s[2] ")"} }')"

  # We *could* have awk print out the information in CSV format in order to be able to colour different values differently without a massive nightmare of an awk script.
  if [ -n "${resyncing_arrays}" ]; then
    printf "\${color #${colour_local_path}}\${font Neuropolitical:size=16:bold}Resyncing RAID Arrays\${font}\${color}\${hr}\n%s" "${resyncing_arrays}"
  fi
fi
