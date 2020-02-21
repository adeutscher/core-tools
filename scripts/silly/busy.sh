#!/bin/bash

# Make you look all busy and fancy in the eyes of non-technical people.
# I forget the original author of this, probably someone on Reddit.
hexdump -C /dev/urandom | grep --color=auto "ca fe"
