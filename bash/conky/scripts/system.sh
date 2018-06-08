#!/bin/bash

. functions/common.sh 2> /dev/null

##########
# Header #
##########

printf "\${color #${colour_header}}\${font Neuropolitical:size=16:bold}%s\${font}\${color}\${hr}\n" "${DISPLAY_HOSTNAME:-\${nodename}}"

########
# Time #
########

# Print the time on request.
# This check used to hinge off of detecting the clock-applet, but a later version of the MATE desktop spawned no new processes
#   for the applet. The check probably wasn't entirely compatible with other desktop environments to begin with, anyways.
if (( ${CONKY_ENABLE_CLOCK:-0} )); then
    printf "\${color grey}Time:\${color} \${time %%I}:\${time %%M}:\${time %%S} \${time %%P} (\${time %%Y}-\${time %%m}-\${time %%d}) \n"
fi

#########################################
# Uptime and Battery (where applicable) #
#########################################

# Assume that the only possible battery paths are BAT0 and BAT1 until proven otherwise.
if [ -f "/sys/class/power_supply/BAT0/uevent" ]; then
    . /sys/class/power_supply/BAT0/uevent 2> /dev/null
elif [ -f "/sys/class/power_supply/BAT1/uevent" ]; then
    . /sys/class/power_supply/BAT1/uevent 2> /dev/null
fi

if [ -n "${POWER_SUPPLY_STATUS}" ]; then
    if [ "${POWER_SUPPLY_CAPACITY}" -le 1 ]; then
        # If a battery is correctly reported to be at 0%, then the machine is probably going to die as soon as it's not on AC power.
        # The battery itself is most likely completely fried.
        printf "\${color grey}Uptime:\${color} \${uptime} (\${color #${colour_orange}}Dead Battery\${color})\n"
    elif [ "${POWER_SUPPLY_CAPACITY}" -lt 99 ]; then
        # Regular battery.
        printf "\${color grey}Uptime:\${color} \${uptime} (${POWER_SUPPLY_STATUS} $(colour_percent_desc ${POWER_SUPPLY_CAPACITY})%%)\n"
    elif [ "${POWER_SUPPLY_CAPACITY}" -ge 99 ]; then
        # Full battery. Sometimes, the display halts at 99%.
        printf "\${color grey}Uptime:\${color} \${uptime} (\${color #${colour_green}}Full Battery\${color})\n"
    fi
else
    # No battery, most likely a desktop
    printf "\${color grey}Uptime:\${color} \${uptime}\n"
fi

###############
# Memory Info #
###############

printf "\${color grey}RAM Usage:\${color} \${mem}/\${memmax} - \${memperc}%% \${membar 4}\n"
printf "\${color grey}Swap Usage:\${color} \${swap}/ \${swapmax} - \${swapperc}%% \${swapbar 4}\n"

################################
# CPU Display and Process Info #
################################

# Some systems have a segfault if it is asked for a CPU bar too early after starting or reloading the configuration. No idea why.
cpu_bar_threshold="30"
cpu_bar_time="$(ps -p ${PPID} -o etime= | awk -F ':' '{if (NF == 2) { print $1*60 + $2 } else if (NF == 3) { split($1, a, "-"); if (a[2] > 0) { print ((a[1]*24+a[2])*60 + $2) * 60 + $3; } else { print ($1*60 + $2) * 60 + $3; } } }')"

if [ "${cpu_bar_time:-0}" -gt "${cpu_bar_threshold}" ]; then
  # Older process, larger CPU display (w/ bar)
  printf "\${color grey}Processes:\${color} \${processes}  \${color grey}Running:\${color} \${running_processes}\n\${color grey}CPU Usage:\${color} \${cpu}%% \${cpubar}\n"
else
  # Newer process, smaller CPU display.
  printf "\${color grey}Processes:\${color} \${processes}  \${color grey}Running:\${color} \${running_processes} \${color grey}CPU:\${color} \${cpu}%%"
fi
