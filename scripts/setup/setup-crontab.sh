#!/bin/bash

cd "$(dirname "$0")"

if [ ! -f "../../files/common-crontab" ]; then
    printf "Common crontab file not found...\n"
    exit 1
fi

crontab_contents="$(crontab -l)"

if ! grep -qm1 "common-crontab-marker" <<< "${crontab_contents}"; then
    printf "Installing common crontab jobs...\n"
    (printf "$crontab_contents\n\n"; cat "../../files/common-crontab") | crontab -
else
    printf "Common crontab tools are already installed!\n"
fi
