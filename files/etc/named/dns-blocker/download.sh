#!/bin/bash

# A quick-and-lazy little script to re-get different hosts files.


cd "$(dirname $0)"

curl "http://winhelp2002.mvps.org/hosts.txt" > blacklists/mvps-hosts.txt

curl "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts" > blacklists/steven-black-hosts.txt

curl http://someonewhocares.org/hosts/zero/ | grep "^0\.0\.0\.0" > blacklists/someone-who-cares.txt
