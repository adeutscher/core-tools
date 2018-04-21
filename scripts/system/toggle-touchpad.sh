#!/bin/bash

# Get the ID # of the touchpad
device=$(xinput list| grep TouchPad | grep -om1 id\=[0-9]* | cut -d"=" -f 2)
# Double-check that a TouchPad exists.
if [ -n "$device" ]; then
   xinput list-props $device | grep "Device Enabled" | grep -q '1$'
   result=$?
   xinput set-prop $device "Device Enabled" $result
fi

