
######################
 ####################
 # System Functions #
 ####################
######################

# Functions for working with hardware and system properties


# Unset battery directory from possible previous loop (as unlikely as it is to change from reload to reload).
unset __BATTERY_DIR

# Look for the first available battery.
# For the moment, assume only one battery.
for __BAT_NUM in $(seq 0 2); do
    if [ -f "/sys/class/power_supply/BAT${__BAT_NUM}/uevent" ]; then
        __BATTERY_DIR="/sys/class/power_supply/BAT${__BAT_NUM}"
        break
    fi
done
unset __BAT_NUM

if [ -n "${__BATTERY_DIR}" ] || [ -n "${FORCE_LAPTOP_MODE}" ]; then
  if [ -n "${__BATTERY_DIR}" ]; then
    alias battery='echo "Battery status: $(cat "${__BATTERY_DIR}/capacity")% ($(cat "${__BATTERY_DIR}/status"))"'
    alias battery-short="cat $__BATTERY_DIR/capacity"
  else
    alias battery='echo "Laptop status was faked, no battery detected..."'
    alias battery-short="echo 0"
  fi
  alias __is_laptop="(( 1 ))"
else
  # For desktop machines.
  alias battery='echo "No battery detected..."'
  # Add a command so that getting the short battery is not just "not found".
  alias battery-short="echo 0"
  alias __is_laptop="(( 0 ))"
fi

# Make default memory display more verbose.
alias free='free -m -l -t' # show sizes in MB, with verbose information.


## Process Management ##

# Print out the time that each process has been running.
alias ps-time="ps axwo pid,etime,cmd"

get-env-var(){
    # Retrieve a specific environment variable from a process via procfs
    # Usage: get-env-var pid var-name

    local pid=$1
    local var=$2

    if ! grep -q "^[0-9]*$" <<< "$pid"; then
        error "$(printf "Invalid PID: ${Colour_Bold}%s${Colour_Off}" "$pid")" >&2
        notice "Usage: get-env-var pid var-name" >&2
        return 1
    fi

    if ! grep -iq "^[a-z0-9_]*$" <<< "$var"; then
        error "$(printf "Invalid variable name: ${Colour_Bold}%s${Colour_Off}" "$var")" >&2
        notice "Usage: get-env-var pid var-name" >&2
        return 1
    fi

    local envDir="/proc/$pid"
    local envFile="$envDir/environ"

    if [ ! -d "$envDir" ]; then
        error "$(printf "Process with PID of ${Colour_Bold}%d${Colour_Off} does not exist..." "$pid")" >&2
        return 3
    fi

    tr \\0 \\n 2> /dev/null < "$envFile" | grep "$var=" | cut -d"=" -f 2-
}
