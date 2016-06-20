#!/bin/bash

. functions/common 2> /dev/null

#########################################
# LibVirt Host (tested with KVM guests) #
#########################################

# Confirm that virsh is available, and 
#   attempt to confirm that the user is a member
#   of a possible group with access to run virsh
#   without needing to escalate their permissions.
# Potential groups for conky are ranked in terms of least to most likely for me to be using.
if which virsh 2> /dev/null >&2 && egrep -qm1 '(^|\ )(wheel|libvirt|adm|root)($|\ )' <<< "$(groups)"; then
    # Put initial listing in CSV format.
    vm_listing="$(virsh --connect "qemu:///system" list | tail -n +3 | sed -e '/^$/d' -e '/^\-/d' | awk -F' ' '{print $1","$2","$3" "}')"
    
    if [ -n "$vm_listing" ]; then
    
        printf "\n\${color #$colour_header}\${font Neuropolitical:size=16:bold}Virtual Machines\$font\$color\$hr\n"
    
        for listing in $vm_listing; do
            # Extract names from CSV for use.
            vm_id="$(cut -d"," -f1 <<< "$listing")"
            vm_name="$(cut -d"," -f2 <<< "$listing")"
            vm_state="$(cut -d"," -f3 <<< "$listing")"
            
            case "$vm_state" in
            "running")
                case_colour="${colour_good}"
                ;;
            *)
                case_colour="${colour_alert}"
            esac
            
            # Search through the XML configuration for interface names.
            raw_vm_ifaces=$(virsh --connect "qemu:///system" dumpxml "${vm_name}" | grep vnet | cut -d"'" -f 2)
            
            # Print initial VM data.
            printf " \${color #${colour_kvm}}${vm_name}\$color (${vm_id}, \${color #${case_colour}}${vm_state}\$color"
            
            # Interface listing
            # Up to 3 interface entries per line.
            # Initial VM data will be the equivalent of two entries.
            count=2
            # If there were no interfaces detected to write to $raw_vm_ifaces, this will be skipped
            for if in $raw_vm_ifaces; do
                if [ "$count" -eq "3" ]; then
                    # Put in a newline and padding as well as comma
                    printf ',\n             %s' "$(colour_interface ${if})"
                    count=0
                else
                    # Put in a comma.
                    printf ", %s" "$(colour_interface ${if})"
                fi
                count=$(($count+1))
            done
            # Close our display.
            printf ")\n"
            
        done
    fi
fi
