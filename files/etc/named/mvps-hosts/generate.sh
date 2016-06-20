#!/bin/bash

# Quick and dirty script to convert the MVPS hosts file to a format that can be used by BIND9.

cd "$(dirname $(readlink -f "$0"))"

if [ ! -f hosts.txt ]; then
    printf "Error: hosts.txt not found. Re-download it from http://winhelp2002.mvps.org/hosts.txt and placing it in the same directory as this script.\n"
    exit 1
fi

cat << EOF > blacklist.db

;
; BIND data file for blocked domains
;
\$TTL    3600
@       IN      SOA     blocked.nope. info.blocked.nope. (
                            2014052101         ; Serial
                                  7200         ; Refresh
                                   120         ; Retry
                               2419200         ; Expire
                                  3600)        ; Default TTL
;
@ IN NS localhost.
     A    127.0.0.1 ; This means that naughydomain.com gets directed to the designated address
* IN A    127.0.0.1 ; This wildcard entry means that any permutation of xxx.naughtydomain.com gets directed to the designated address
     AAAA ::1 ; This means that naughydomain.com gets directed to IPv6 localhost
* IN AAAA ::1 ; This wildcard entry means that any permutation of xxx.naughtydomain.com gets directed to IPv6 localhost 

EOF

printf "# Don't forget to include this in your BIND9 configuration.\n" > blacklist.zones
# Note on tr: The first tr is for the Mac-formatted source file. Further tr calls are for illegal characters in source file (assuming that they won't form a legal name that we actually want for the moment)

grep "^0\.0\.0\.0" hosts.txt | cut -d' ' -f2 | tr -d '\r' | tr '_' '-' | sed -r -e "s/^-*//g" -e "s/(-*\.-*)/./g" | xargs -I{} printf 'zone "%s" {type master; file "__DB_PATH__";};\n' "{}" >> blacklist.zones

printf "Blacklist hosts file converted for BIND9.\nDon't forget to include it in your config and to replace __DB_PATH__ with the absolute path of blacklist.db.\ne.g.:  sed -i \"s|__DB_PATH__|/etc/named/zones/blacklist.db|g\" \"blacklist.zones\"\n" 
