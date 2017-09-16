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
        return 1
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

  __wifi_interface=$(iwconfig 2> /dev/null | cut -d' ' -f1 | head -n1)

  # Only continue if we actually have a WiFi interface
  #   (in the off-chance we actually have a laptop without one)
  if [ -n "$__wifi_interface" ]; then
    # WiFi Toggle
    alias wifi-on='nmcli radio wifi on'
    alias wifi-off='nmcli radio wifi off'
    alias wifi-list='nmcli -p dev wifi list'
    alias wifi-list-open="nmcli -p dev wifi list | egrep --color=none '(==|\)|SECURITY|\-\-)[ ]*$' | sed 's/)/, open networks only)/g'"
    alias wifi-join='nmcli con up id'
    alias wifi-connections='nmcli con'
    alias wifi-disconnect="nmcli dev disconnect $__wifi_interface"
    alias wifi-switch="wifi-disconnect && wifi-join"
  fi
  unset __wifi_interface
fi

############################
# Other Wireless Functions #
############################

wifi-list-raw(){

    # I made this function to cover the fact that scanning through nmcli doesn't print an access point's BSSID.
    # In addition, nmcli requires the NetworkManager service to be running in the first place in order to work.
    # It is a terrible awk one-liner, but it works for the moment.
    # NOTE: The output of scanning with `iw` is not considered to be stable by the developers maintaining it.
    #       This function may break over time.
    if [ -z "$1" ]; then
        error "Usage: wifi-list-raw interface"
        return 1
    fi
    local iface=$1

    if ! iwconfig "$iface" 2> /dev/null | grep -q "IEEE"; then
        error "$(printf "Interface ${Colour_Bold}%s${Colour_Off} not found or not a wireless interface..." "$iface")"
        return 2
    fi

    sudo iw dev "$iface" scan | tac | awk 'BEGIN { defaultSecurity="OPEN"; security=defaultSecurity; has_security=0; channel="??"} { if($1 == "BSS" && $2 != "Load:" ){ if(has_security && security == defaultSecurity){ security="WEP" }; print substr($2,0,17) " (" security ", channel " channel "): " ssid; bssid=""; ssid=""; channel="??"; security=defaultSecurity; has_security=0;} else if ($1 == "SSID:" ){ for(i = 2; i <= NF; i++){ if(ssid){ ssid=ssid " " $i } else { ssid=$i } } }; if($1 == "capability:" && match($0,"Privacy")){ has_security=1; }; if ($2 == "Authentication" && $5 == "802.1X" ){ security=$5 } if ($1 == "RSN:") { if(security == "WPA1") { security=security " WPA2" } else if(security != defaultSecurity) { security="WPA2 " security } else { security="WPA2" } } else if($1 == "WPA:"){ security="WPA1" } else if ( $2 == "primary" && $3 == "channel:" ){ channel=$4 } else if($1" "$2" "$3" "$4 == "DS Parameter set: channel"){ channel=$5 } }' | sort -k2,2
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

#######################
# General Wake-On-LAN #
#######################

# Wake on LAN command is named differently on Debian-based systems.
# Keeping the form of any aliases consistent across distributions.
if qtype wakeonlan && ! qtype wol; then
    alias wol=wakeonlan
fi

# Use custom python script if you need to send from arbitrary interfaces.
alias wol-manual="$toolsDir/scripts/networking/wol-manual.py"

################
# IP Addresses #
################

ip2dec(){
  local a b c d ip=$@
  IFS=. read -r a b c d <<< "$ip"
  printf '%d\n' "$((a * 256 ** 3 + b * 256 ** 2 + c * 256 + d))"
}

dec2ip(){
  local ip dec=$@
  for e in {3..0}
  do
    ((octet = dec / (256 ** e) ))
    ((dec -= octet * 256 ** e))
    ip+=$delim$octet
    local delim=.
  done
  unset e octet dec
  printf '%s\n' "$ip"
}

cidr-low(){
  printf $(dec2ip $(cidr-low-dec "$1"))
}

cidr-low-dec(){
  # Print the lowest usable address in a CIDR range.
  # Assumes valid input in one of the the following two formats:
  #   - 10.11.12.13/24
  #   - 10.11.12.13/255.255.255
  # Calculating netmask manually because ipcalc does not support
  #   calculating the minimum/maximum addresses in all distributions.

  local network=$(cut -d'/' -f1 <<< "$1")
  local netmask=$(cut -d'/' -f2 <<< "$1")

  local plus=1
  if grep -qP "255.255.255.255|32" <<< "$netmask"; then
    # /32 networks are single-host networks,
    #   wherein the network ID is the only usable address.
    local plus=0
  fi

  printf $(($(ip2dec "$network")+$plus))
}

cidr-high(){
  printf $(dec2ip $(cidr-high-dec "$1"))
}

cidr-high-dec(){
  # Print the highest usable address in a CIDR range.
  # Assumes valid input in one of the the following two formats:
  #   - 10.11.12.13/24
  #   - 10.11.12.13/255.255.255
  # Calculating netmask manually because ipcalc does not support
  #   calculating the minimum/maximum addresses in all distributions.

  local network=$(cut -d'/' -f1 <<< "$1")
  local netmask=$(cut -d'/' -f2 <<< "$1")

  if ! grep -qP "^\d{1,}$" <<< "$netmask"; then
    # Netmask was not in CIDR format.
    local netmask=$(printf %.$2f $(awk '{ print 32-log(4294967295-'"$(ip2dec "$netmask")"')/log(2)}' <<< ""))
  fi

  # Subtract 2 for network id and broadcast addresss
  #   (unless we have a /32 address)
  local subtract=2
  if [ "$netmask" -eq "32" ]; then
    # /32 networks are single-host networks,
    #   wherein the network ID is the only usable address.
    local subtract=0
  fi

  printf $(($(ip2dec "$network")+(2 ** (32-netmask))-$subtract))
}

# Translate a MAC address to an IPv6 link-local address.
# Courtesy of: http://codereview.stackexchange.com/questions/90263/network-mac-address-conversion-to-ipv6-link-local-address
# Assumes valid input.
ip6linklocal(){
  python -c "p='$1'.split(':'); p.insert(3,'ff'); p.insert(4,'fe'); p[0]='%x'%(int(p[0],16)^2); ipp=[''.join(p[i:i+2]) for i in range(0, len(p), 2)]; print 'fe80::%s/64' % (':'.join(ipp))" 2> /dev/null
}

# Translate an IPv6 link-local address back to a MAC address.
# Assumes valid input.
ip6linklocal-reverse(){
  python -c "ip='$1';
s=ip.find('/');
if s != -1:
  ip = ip[:s];
ipp = ip.split(':'); mp=[];
for ipsp in ipp[-4:]:
  while len(ipsp) < 4:
    ipsp = '0' + ipsp
  mp.append(ipsp[:2])
  mp.append(ipsp[-2:])
np='%02x' % (int(mp[0],16)^2)
del mp[3]
del mp[3]
print ':'.join(mp);"
}
