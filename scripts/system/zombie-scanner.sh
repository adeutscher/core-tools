#!/bin/bash
# Zombie processes killing script.
# Must be run under root.
# Credit: Marius Voila (https://www.mariusv.com/automatic-zombie-processes-killing-shell-script)

get_zombies()
{
    ps "x${1}" | awk '{print $1}' | grep -v "PID" | xargs -n 1 ps lOp | grep -v "UID" | awk '{print"pid: "$3" *** parent_pid: "$4" *** status: "$10" *** process: "$13}' | grep ": Z"
}

case "$1" in
--scan)
        # Look through all variables if we are running as root.
        # Otherwise, just look through the processes for our current users.
        if [ "$EUID" -eq 0 ]; then
            admin_flag='a'
        fi
        stat=$(get_zombies "${admin_flag}")

        if ((${#stat} > 0));then
    	    echo zombie processes found:
	    echo .
	    ps ax | awk '{print $1}' | grep -v "PID" | xargs -n 1 ps lOp | grep -v "UID" | awk '{print"pid: "$3" *** parent_pid: "$4" *** status: "$10" *** process: "$13}' | grep ": Z"
	    echo -n "Kill zombies? [y/n]: "
	    read -r keyb
	    if [ "${keyb}" == 'y' ];then
		echo "killing zombies..."
		ps ax | awk '{print $1}' | grep -v "PID" | xargs -n 1 ps lOp | grep -v "UID" | awk '{print$4" status:"$10}' | grep "status:Z" | awk '{print $1}' | xargs -n 1 kill -9
	    fi
	else
	    echo 'No zombies found!'
	fi
;;
--cron)
	stat=$(get_zombies "a")
        if ((${#stat} > 0));then
        ps ax | awk '{print $1}' | grep -v "PID" | xargs -n 1 ps lOp | grep -v "UID" | awk '{print$4" status:"$10}' | grep "status:Z" | awk '{print $1}' | xargs -n 1 kill -9
	printf "%s: killed some zombie proceses!\n" "$(date)" >> /var/log/zombies.log
	fi
;;
*)	echo 'usage: zombies {--cron|--scan}'
;;
esac
exit 0
