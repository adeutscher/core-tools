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
#     redacted-name,Bluetooth,18:2a:7b:3d:aa:bb,WiiU Pro,Home,Bookshelf,Used for games,purchased last year
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

  local __num=$1
  local __c=0
  local __i=0

  # Each "module" should be the unit and the number of that unit until the next phrasing.
  local __modules=(s:60 m:60 h:24 d:7 w:52 y:100 c:100)

  local __modules_count="$(wc -w <<< "${__modules[*]}")"
  while [ "$__i" -lt "$__modules_count" ]; do
    # Cycling through to get values for each unit.
    local __value="$(cut -d':' -f2 <<< "${__modules[$__i]}")"

    local __mod_value="$(($__num % $__value))"
    local __num="$((__num / $__value))"

    local __times[$__i]="$__mod_value"
    local __c=$(($__c+1))
    local __i=$(($__i+1))
    if (( ! $__num )); then
      break
    fi
  done
  unset __module

  local __i=$(($__c-1))
  while [ "$__i" -ge "0" ]; do
    printf "${__times[$__i]}$(cut -d':' -f1 <<< "${__modules[$__i]}")"

    if (( $__i )); then
      printf " "
    fi

    local __i=$(($__i-1))
  done
}
