
# Print a report of the reachable devices (by ping or arping) on your network.
# To use this, load in both this file of network-report functions and 'common' ('common' should be loaded first)
# This process *will* take more than a second on average, so it's recommended that this be placed in a "report script" call.
#
# Command format:
#     network_report interface [title]
# Usage Example:
#     network_report eth1 "$HOSTNAME Test Network"
#
# Note: This is mostly intended for networks with a small number of hosts on it.
# I made this for networking situations where at least one of the following is true:
#     - Target network doesn't have a large number of devices on it.
#     - Computer running conky will not communicate with a large number of devices on the network.
#          The script reads off of the exiting arp table, and will not attempt any broadcasts in order to inflate the list.

# Description of functions.
# Use the arp command to list clients on this network (as best we can manage)
# If you need to adapt this for a different host, copy the code and use a different
#
# If the arp command returns an incomplete in place of a MAC address,
#     then it is interpreted as a disconnect and removed from the listing.
# This approach has a major shortcoming in that it takes a while for an ARP table entry to become incomplete.
# Because of this drawback, arp parsing is delegated to a report job that will try arping-ing a host before it is added to the list.

# If the network labels function has not already been loaded, then load it.
if ! qtype __get_mac_record; then
    . functions/network-labels.sh
fi

prep(){

  local cacheDir="$1"

  if [ -z "$cacheDir" ]; then
    return 1
  fi

  # Confirm that the report root exists, plus the sub-directory for this network
  mkdir -p $tempRoot/$cacheDir
}

draft-report(){
  # Make report

  local reportPrefix="$1"
  local cacheDir="$2"

  if [ -z "$cacheDir" ]; then
    return 1
  fi

  local reportFile="$tempRoot/$cacheDir/$reportPrefix$(date +%s)"
  arp -i $iface -na | egrep -v '(incomplete|no match)' | sed -r 's/(\(|\))//g' | cut -d' ' -f 2,4 | while read -r line; do
    unset header
    local ip="$(cut -d' ' -f 1 <<< "$line")"
    if arping -I ${iface} -f -w1 -c1 -q "${ip}" || ping -c1 "${ip}" 2> /dev/null >&2; then
      # Do not bother recording the MAC unless arping was successful.
      local mac="$(cut -d' ' -f 2 <<< "$line")"
      local data="$(sed 's/#/\\#/g' <<< "$(shorten_string "$(__get_mac_label "$mac")" 30)")"
      if [ -z "$data" ]; then
        local data="$(sed 's/#/\\#/g' <<< $(shorten_string "$(__get_mac_vendor "$mac")" 25))"
        if [ -n "$data" ]; then
          local header="Vendor: "
        fi
      fi

      printf "%s %s%s\n" "$line" "$header" "$data" 2> /dev/null
    fi
  done > $reportFile
}

trim(){

  local reportPrefix="$1"
  local cacheDir="$2"

  if [ -z "$cacheDir" ]; then
    return 1
  fi

  # Trim to 3 reports.
  ls -r $tempRoot/$cacheDir/$reportPrefix* | tail -n +4 | xargs -I{} rm {}
}

compile(){
  # Compile reports into one ordered list.

  local reportPrefix="$1"
  local fullReport="$2"
  local title="$3"
  local cacheDir="$5"
  local prefix="$4"

  if [ -z "$cacheDir" ]; then
    return 1
  fi

  # Make sure the new report space is clear.
  rm -f "$tempRoot/$cacheDir/$fullReport.new" "$tempRoot/$cacheDir/$fullReport"
  for mac in $(cat $tempRoot/$cacheDir/$reportPrefix* | sort | cut -d' ' -f 2 | uniq); do
    # Add the most recent entry for a MAC address to the finished report.
    grep -Rhm1 "\ $mac\ " $(ls -r "$tempRoot/$cacheDir/$reportPrefix"*) | head -n1 >> "$tempRoot/$cacheDir/$fullReport.new"
  done
  # Apply the new report.
  mv "$tempRoot/$cacheDir/$fullReport.new" "$tempRoot/$cacheDir/$fullReport"

  # Get information from cached report.
  # Reminder: "Label" is the vendor label or self-defined label, including the header label.
  report=$(cat $tempRoot/$cacheDir/$fullReport 2> /dev/null | awk '{ label=""; for (i = 3; i <= NF; i++) { if(label){ label = label " " $i } else { label = $i; } }; if(label){ print " ${color #'${colour_network_address}'}" $1 "${color} [" $2 "]\n  └╢ "label""  } else { print " ${color #'${colour_network_address}'}" $1 "${color} ["$2"]" } }')

  if [ -n "$report" ]; then
    # Print header and report.
    mkdir -p "$tempRoot/reports"
    printf "\n\${color #${colour_network}}\${font Neuropolitical:size=16:bold}%s\$font\$color\$hr\n%s\n" "$title" "${report}" > "$tempRoot/reports/$formattedReport"
  else
    rm "$tempRoot/reports/$formattedReport"
  fi
}

network_report(){

    local iface="${1:-br9}"
    local title="${2:-"$iface Network"}"
    local prefix="$3"

    cacheDir="cache/network/$iface"
    reportPrefix=arp-report-$iface-draft
    local fullReport=arp-report-$iface
    local formattedReport=arp-report-$iface-formatted

    prep "$cacheDir"
    draft-report "$reportPrefix" "$cacheDir"
    trim "$reportPrefix" "$cacheDir"
    compile "$reportPrefix" "$fullReport" "$title" "$prefix" "$cacheDir"
}
