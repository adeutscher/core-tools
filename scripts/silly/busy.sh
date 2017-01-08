#!/bin/bash

# Make you look all busy and fancy in the eyes of non-technical people.
# I forget the original author of this, probably someone on Reddit.
cat /dev/urandom | hexdump -C | grep --color=auto "ca fe"
