#!/bin/bash

# Quick and dirty script to convert the MVPS hosts file to a format that can be used by BIND9.

cd "$(dirname $(readlink -f "$0"))"

# We want at leasts mvps-hosts.txt, but we will be looking through any .txt file while assuming a hosts file format.
if [ "$(ls blacklists/ | wc -l)" -eq 0 ]; then
    printf "Error: No blacklist hosts files found. Re-download into blacklists/ directory per README.\n"
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

# Assume that all *.txt files are hosts files (though the regex will only pick up on the ones that begin in 0.0.0.0 anyways)
grep "^0\.0\.0\.0" blacklists/*.txt | tr '\t' ' ' | cut -d' ' -f2 | tr -d '\r' | tr '[:upper:]' '[:lower:]' | tr '_' '-' | sed -r -e "s/:.*//g" -e "s/^-*//g" -e "s/(-*\.-*)/./g" | sort | uniq | xargs -I{} printf 'zone "%s" {type master; file "__DB_PATH__";};\n' "{}" >> blacklist.zones

# Remove case-by-case exceptions (since blacklists are massive lists that we don't want to be pruning after each update).
cat whitelists/*.txt 2> /dev/null | tr '\t' ' ' | cut -d' ' -f1 | grep -v "^#" | xargs -I{} sed -i '/\"{}\"/d' blacklist.zones

printf "Blacklist hosts file converted for BIND9.\nDon't forget to include it in your config and to replace __DB_PATH__ with the absolute path of blacklist.db.\ne.g.:  sed -i \"s|__DB_PATH__|/etc/named/zones/blacklist.db|g\" \"blacklist.zones\"\n" 
