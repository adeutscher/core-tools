#!/bin/bash 
printf "\${color1}┣━os: \${color2}ARCH LINUX\n"
printf "\${color1}┣━architecture: \${color2}\${machine}\n"
printf "\${color1}┃\n"
printf "\${color1}┣━kernel: \${color2}\$kernel\n"
printf "\${color1}┣━packages: \${color2}"
pacman -Q | wc -l
printf "\${color1}┣━aur packages: \${color2}"
pacman -Qm | wc -l
printf "\${color1}┣━last sync: "

GAP=$(($(date +%Y%m%d) - $(date -d $(grep 'full system upgrade' /var/log/pacman.log | tail -1 | cut -c2-11) +"%Y%m%d")))

if [ $GAP -lt 2 ]
then
    printf "\${color2}"
elif [ $GAP -lt 4 ]
then
    printf "\${color3}"
elif [ $GAP -lt 8 ]
then
    printf "\${color4}"
elif [ $GAP -lt 16 ]
then
    printf "\${color5}"
else
    printf "\${color6}"
fi

grep 'full system upgrade' /var/log/pacman.log | tail -1 | cut -c2-17
printf "\${color1}┣━uptime: \${color2}\${uptime}\n"
printf "\${color1}┃\n"


OUTPUT="$(lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT)"
printf "\${color1}┣━${OUTPUT}" | sed -n 1'p' | awk '{print tolower($0)}'
printf "\${color2}"
OUTPUT=`echo "${OUTPUT}" | sed '1d'`
IFS=$'\n'
for LINE in `echo "${OUTPUT}"`
do
    printf "\${color1}┃\${color2} $LINE\n"
done
