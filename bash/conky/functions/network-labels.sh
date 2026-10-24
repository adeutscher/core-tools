# Look in a data file in the secure/ directory to try to resolve MAC addresses to a computer name.
# If the file doesn't exist or there is no entry, print nothing and let above logic handle it.

# To use this, load in both this file of network-labels functions and 'common' ('common' should be loaded first, as this file assumes that the common items are present)

# Label Functions

network_index="${INDEX_NETWORK_CACHE:-$toolsCache/network-index.csv}"
network_cache="${INDEX_NETWORK_DATA:-$secureToolsDir/files/tool-data/network-index.csv}"

vendor_cache="${INDEX_NETWORK_CACHE:-$tempRoot/../vendor-mac.psv}"
vendor_index="${INDEX_NETWORK_DATA:-$secureToolsDir/files/tool-data/vendor-mac.psv}"

# Example record line (plus header):
#     owner,type,mac,label,general-location,specific-location,description,notes
#     Alan,Bluetooth,18:2a:7b:3d:aa:bb,WiiU Pro,Home,Bookshelf,Used for games,purchased last year
__get_mac_record(){
    if [ -n "$1" ]; then
        # Try cache and then try for a secure tools checkout (not mourning an error if secureToolsDir does not exist.
        # secureTools dir should still be loaded even if this is run as part of a startup script.
        grep -Pim1 "^([^,]*,){2}$1," "$network_cache" 2> /dev/null || grep -Pim1 "^([^,]*,){2}$1," "$network_index" 2> /dev/null | tee -a "$network_cache"
    fi
}

# fetch description field
__get_mac_description(){
    if [ -n "$1" ]; then
        __get_mac_record "$1" | cut -d',' -f 7
    fi
}

# fetch label field
__get_mac_label(){
    if [ -n "$1" ]; then
        __get_mac_record "$1" | cut -d',' -f 4
    fi
}

# fetch general location field
__get_mac_general_location(){
    if [ -n "$1" ]; then
        __get_mac_record "$1" | cut -d',' -f 5
    fi
}

# fetch notes field
__get_mac_notes(){
    if [ -n "$1" ]; then
        __get_mac_record "$1" | cut -d',' -f 8
    fi
}

# fetch owner field
__get_mac_owner(){
    if [ -n "$1" ]; then
        __get_mac_record "$1" | cut -d',' -f 1
    fi
}

# fetch specific location field
__get_mac_specific_location(){
    if [ -n "$1" ]; then
        __get_mac_record "$1" | cut -d',' -f 6
    fi
}

# fetch type field
__get_mac_type(){
    if [ -n "$1" ]; then
        __get_mac_record "$1" | cut -d',' -f 2
    fi
}

__get_mac_vendor_inner(){
    if [ -n "$1" ] && [ -f "$vendor_index" ]; then
        grep -im1 "^${1:0:8}" "$vendor_cache" 2> /dev/null || grep -im1 "^${1:0:8}" "$vendor_index" | tee -a "$vendor_cache" 2> /dev/null
    fi
}

__get_mac_vendor(){
    __get_mac_vendor_inner "$1" | cut -d'|' -f 2
}

# Translation for interface uptime labels

translate_seconds(){
  # Translate a time given in seconds (e.g. the difference between two Unix timestamps) to more human-friendly units.
  # Stripped down version of usual with more abbreviated units.
  # Units with a value of zero are left out. A year is treated as 365 days.

  local __num="${1}"
  local __unit __size
  local __parts=()

  # Only accept non-negative integers.
  [[ "${__num}" =~ ^[0-9]+$ ]] || return 1
  __num=$((10#${__num}))

  # Each unit should be its abbreviation and its length in seconds, from largest to smallest.
  for __unit in c:3153600000 y:31536000 w:604800 d:86400 h:3600 m:60 s:1; do
    __size="${__unit#*:}"
    if (( __num / __size )) || { (( __size == 1 )) && (( ! ${#__parts[@]} )); }; then
      __parts+=("$((__num / __size))${__unit%%:*}")
    fi
    __num=$((__num % __size))
  done

  printf "%s" "${__parts[0]}"
  (( ${#__parts[@]} > 1 )) && printf " %s" "${__parts[@]:1}"
}
