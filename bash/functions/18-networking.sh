##############
# Networking #
##############

# Experimental function to kill background functions
# that are prone to causing "noise" on a network line.
# Needs to be populated a good deal more...
kill-noise(){
   killall dropbox 2> /dev/null
   killall owncloud 2> /dev/null
}

# IPv6
#######

# Lazy shortcuts for doing broadcast ICMPv6 pings.
alias ping6-all-wlan0='ping6 ff02::2%wlan0'
alias ping6-all-eth0='ping6 ff02::2%eth0'

# Network Monitoring

# default switches for iftop
alias iftop="iftop -nNp"

########
# Curl #
########

# Some sites filter out curl based on user agent.
# Using this alias to bypass this
alias curl-firefox-linux="curl --user-agent \"Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:41.0) Gecko/20100101 Firefox/41.0\""
alias curl-firefox-windows="curl --user-agent \"Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.1\""
alias curl-chrome-linux="curl --user-agent \"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.71 Safari/537.36\""
alias curl-chrome-windows="curl --user-agent \"Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36\""
alias curl-internet-exploder="curl --user-agent \"Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; AS; rv:11.0) like Gecko\""
# Some tongue-in-cheek user agents for possibly adding some humour to someone's log parsing.
alias curl-contiki="curl --user-agent \"Contiki/1.0 (Commodore 64; http://dunkels.com/adam/contiki/)\""
alias curl-3ds="curl --user-agent \"Mozilla/5.0 (Nintendo 3DS; U; ; en) Version/1.7567.US\""
alias curl-wii-u="curl --user-agent \"Mozilla/5.0 (Nintendo WiiU) AppleWebKit/536.28 (KHTML, like Gecko) NX/3.0.3.12.15 NintendoBrowser/4.1.1.9601.US\""
alias curl-skynet="curl --user-agent \"Skynet Probe v0.1\""
alias curl-shield="curl --user-agent \"S.H.I.E.L.D. Hyperbrowser v3.01\""
alias curl-star-labs="curl --user-agent \"STAR Labs Cortex Explorer v2.01\""

##############
# HTTP Stuff #
##############

# Aliases for getting HTTP Headers
# get web server headers #
alias http-header='curl -I'
 
# find out if remote server supports gzip / mod_deflate or not #
alias http-headerc='curl -I --compress'

alias wgetdir='wget -r -l1 -P035 -nd --no-parent'

# Share a module through Python SimpleHTTPServer module.
http-quick-share(){
    notice "$(printf "Sharing $Colour_BIGreen%s$Colour_Off" "$(pwd)/")"
    python -m SimpleHTTPServer 8080
}

#######
# SSL #
#######

alias checkssl="openssl s_client -connect"

########
# CIFS #
########

## A lazy umount for network file systems.
## Try to nicely umount systems, then force it if that fails.
alias umount-all-cifs='sudo umount -a -t cifs -f || sudo umount -a -t cifs -l'

#################
# Web Resources #
#################

# Try to determine our public IP
public-ip-short(){
    local ip_url=http://wgetip.com
    curl -s $ip_url 2> /dev/null | egrep --color=none '^(([0-9]){1,3}\.){3}([0-9]{1,3})$'
}

public-ip(){
    local ip=$(public-ip-short)
    if [ -n "$ip" ]; then
        notice "Public IP: $ip"
        if qtype geoiplookup-city; then
            notice "$(printf "Location: %s" "$(geoiplookup-city $ip)")"
        elif qtype geoiplookup; then
            notice "$(printf "Location: %s" "$(geoiplookup $ip)")"
        fi
    else
        error "Public IP is currently unknown."
    fi
}

#########
# GeoIP #
#########

# If we have the city-level GeoIP database on our system,
#     then make an alias for it.
if qtype geoiplookup && [ -f "$HOME/.local/GeoLiteCity.dat" ]; then
    alias geoiplookup-city='geoiplookup -f $HOME/.local/GeoLiteCity.dat'
    alias geoip-city='geoiplookup-city'
fi

#####################################
# NetworkManager Wireless Functions #
#####################################

if __is_laptop && qtype nmcli; then
    # Locking these functions to only laptops until I find
    #     a situation where that is not the case.

    # WiFi Toggle
    alias wifi-on='nmcli radio wifi on'
    alias wifi-off='nmcli radio wifi off'
    alias wifi-list='nmcli -p dev wifi list'
    alias wifi-list-open="nmcli -p dev wifi list | egrep --color=none '(==|\)|SECURITY|\-\-)[ ]*$' | sed 's/)/, open networks only)/g'"
    alias wifi-join='nmcli con up id'
    alias wifi-connections='nmcli con'
    alias wifi-disconnect='nmcli dev disconnect wlan0'
fi

############################
# Other Wireless Functions #
############################

wifi-list-raw(){

    # I made this function to cover the fact that scanning through nmcli doesn't print an access point's BSSID.
    # In addition, nmcli requires the NetworkManager service to be running in the first place in order to work.

    if [ -z "$1" ]; then
        error "Usage: wifi-list-raw interface"
        return 1
    fi
    local iface=$1

    if ! iwconfig "$iface" 2> /dev/null | grep -q "IEEE"; then
        error "$(printf "Interface $Colour_Bold%s$Colour_Off not found or not a wireless interface...")"
        return 2
    fi

    # TODO: This script does not currently detect WEP input, and will incorectly report it as "OPEN"
    sudo iw dev "$iface" scan | tac | awk 'BEGIN { defaultSecurity="OPEN"; security=defaultSecurity; } { if($1 == "BSS" && $2 != "Load:" ){ print substr($2,0,17) " (" security "): " ssid; bssid=""; ssid=""; security=defaultSecurity; } if ($1 == "SSID:" ){ for(i = 2; i <= NF; i++){ if(ssid){ ssid=ssid " " $i } else{ ssid=$i } } }; if ($2 == "Authentication" && $5 == "802.1X" ){ security=$5 } if ($1 == "RSN:") { if(security == "WPA1") { security=security " WPA2" } else if(security != defaultSecurity) { security="WPA2 " security } else { security="WPA2" } } if($1 == "WPA:"){ security="WPA1" } }' | sort -k2,2
}

####################
# hostapd Commands #
####################
if qtype hostapd && [ -x "$toolsDir/scripts/networking/access-point.sh" ]; then
   # Alias tied to our internal script for hostapd.
   # The alias is a front-end to access_point.sh with simplified variables
   alias access-point="$toolsDir/scripts/networking/access-point.sh"

   # This second alias is mostly just around for muscle-memory (my original name for the alias was "ap-standard") and friendliness with tab-completion.
   # Really should get into the habit of using just "access-point" at some point, though...
   alias ap-host="$toolsDir/scripts/networking/access-point.sh"
fi
# Wake on LAN command is named differently on Debian-based systems.
# Keeping the form of any aliases consistent across distributions.
if qtype wakeonlan && ! qtype wol; then
    alias wol=wakeonlan
fi
