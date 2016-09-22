
# VNC
alias vncserver-start='vncserver -autokill -geometry 1280x960'

##################
# Sound toggling #
##################

nuc-audio-hdmi(){
  pacmd set-default-sink 0
  notice "$(printf "${Colour_BIGreen}%s${Colour_Off} set to play audio out of HDMI. May need to restart some applications." "${DISPLAY_HOSTNAME:-$HOSTNAME}")"
}

nuc-audio-usb(){
  local index="$(pacmd list-sinks | grep Logitech_USB_Headset | grep -m1 card | awk -F' ' '{print $2}')"
  if [ -z "$index" ]; then
    error "Are you sure that the USB adapter is plugged in?"
    return 1
  fi
  pacmd set-default-sink "$index"
  notice "$(printf "${Colour_BIGreen}%s${Colour_Off} set to play audio out of USB adapter (index %d). May need to restart some applications." "${DISPLAY_HOSTNAME:-$HOSTNAME}" "$index")"
}
