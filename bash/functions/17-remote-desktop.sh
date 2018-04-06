
##############################
 ############################
 # Remote Desktop Functions #
 ############################
##############################

# Functions for RDP/VNC, and anything else in a similar vein.

# Aliases for VNC
if qtype vncviewer; then
    alias vncviewer='\vncviewer -CompressLevel 9'
fi

if qtype vncserver; then
    alias vncserver-start='vncserver -autokill'
fi

if qtype x11vnc; then

  vnc-quick-read(){
    if [ -z "${1}" ]; then
      "${toolsDir}/scripts/networking/vnc-quick-share.sh"
    else
      "${toolsDir}/scripts/networking/vnc-quick-share.sh" -p "${1}"
    fi
  }

  vnc-quick-write(){
    if [ -z "${1}" ]; then
      error "Usage: vnc-quick-write password"
      return 1
    fi
    "${toolsDir}/scripts/networking/vnc-quick-share.sh" -w -p "${1}"
  }

  vnc-share-mon-read(){
    local _s="${toolsDir}/scripts/networking/vnc-quick-share.sh"
    if [ -z "${1}" ]; then
      error "Usage: vnc-quick-read monitor password"
      "${_s}" -l
      return 1
    fi

    if [ -z "${2}" ]; then
      "${_s}" -m "${1}"
    else
      "${_s}" -m "${1}" -p "${2}"
    fi
  }

  vnc-share-mon-write(){
    local _s="${toolsDir}/scripts/networking/vnc-quick-share.sh"
    if [ -z "${2}" ]; then
      error "Usage: vnc-quick-write monitor password"
      "${_s}" -l
      return 1
    fi
    "${_s}" -w -m "${1}" -p "${1}"
  }


fi

####################
# Function for RDP #
####################

# If we are using the nightly FreeRDP build, add it to our path.
__add_to_path_if_dir "/opt/freerdp-nightly/bin"

# If xfreerdp is present, add shortcuts.
if qtype xfreerdp; then
  alias rdp="$toolsDir/scripts/networking/rdp.py"
  alias rdp-small="rdp -g 800x600"
fi
