#!/bin/bash

. functions/common 2> /dev/null

##########
# Header #
##########

printf "\${color #${colour_header}}\${font Neuropolitical:size=16:bold}\$nodename\$font\$color\${hr}\n"

########
# Time #
########

# If you do not have a clock applet running, print the time.
if ! pgrep -u $UID clock-applet > /dev/null; then
    printf "\${color grey}Time:\$color \${time %%I}:\${time %%M}:\${time %%S} \${time %%P} (\${time %%Y}-\${time %%m}-\${time %%d}) \n"
fi

#########################################
# Uptime and Battery (where applicable) #
#########################################

if [ -f "/sys/class/power_supply/BAT0/uevent" ]; then
    . /sys/class/power_supply/BAT0/uevent 2> /dev/null
elif [ -f "/sys/class/power_supply/BAT1/uevent" ]; then
    . /sys/class/power_supply/BAT1/uevent 2> /dev/null
fi

if [ -n "${POWER_SUPPLY_STATUS}" ]; then
    if [ "${POWER_SUPPLY_CAPACITY}" -le 1 ]; then
        # If a battery is correctly reported to be at 0%, then the machine is probably going to die as soon as it's not on AC power.
        # The battery itself is most likely completely fried.
        printf "\${color grey}Uptime:\$color \$uptime (\${color #${colour_orange}}Dead Battery\$color)\n"
    elif [ "${POWER_SUPPLY_CAPACITY}" -lt 99 ]; then
        # Regular battery.
        printf "\${color grey}Uptime:\$color \$uptime (${POWER_SUPPLY_STATUS} $(colour_percent_desc ${POWER_SUPPLY_CAPACITY})%%)\n"
    elif [ "${POWER_SUPPLY_CAPACITY}" -ge 99 ]; then
        # Full battery. Sometimes, the display halts at 99%.
        printf "\${color grey}Uptime:\$color \$uptime (\${color #${colour_green}}Full Battery\$color)\n"
    fi
else
    # No battery, most likely a desktop
    printf "\${color grey}Uptime:\$color \$uptime\n"
fi

###############
# Memory Info #
###############

printf "\${color grey}RAM Usage:\$color \$mem/\$memmax - \$memperc%% \${membar 4}\n"
printf "\${color grey}Swap Usage:\$color \$swap/ \$swapmax - \$swapperc%% \${swapbar 4}\n"

################################
# CPU Display and Process Info #
################################

# Mercury and Outpost have a segfault if it is asked for a CPU bar too early after starting or reloading the configuration. No idea why.
# Affected systems actually work with the CPU bar after about 2 seconds, but giving myself some buffer room for configuration fiddling.
# If this pops up on even more systems, consider making the 30s check apply to all systems so that we don't have to edit every hostname in.
cpu_bar_threshold="30"
if [ "$(ps -p $PPID -o etime= | awk -F ':' '{if (NF == 2) { print $1*60 + $2 } else if (NF == 3) { split($1, a, "-"); if (a[2] > 0) { print ((a[1]*24+a[2])*60 + $2) * 60 + $3; } else { print ($1*60 + $2) * 60 + $3; } } }'  )" -gt "${cpu_bar_threshold}" ]; then

    printf "\${color grey}Processes:\$color \$processes  \${color grey}Running:\$color \$running_processes\n\${color grey}CPU Usage:\$color \$cpu%% \${cpubar}\n"

else

    printf "\${color grey}Processes:\$color \$processes  \${color grey}Running:\$color \$running_processes \${color grey}CPU:\$color \$cpu%%"

fi
