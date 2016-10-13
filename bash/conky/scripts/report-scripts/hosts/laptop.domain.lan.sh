#!/bin/bash

# Even though this script is located in report-scripts/hosts/, it is being run of the base conky directory.
. functions/common
. functions/network-report

# Compile information for test network report.
# This is a periodic job because a timed-out arping will take much too long (1s per failure)

network_report br9 "${DISPLAY_HOSTNAME:-$HOSTNAME} Test Network"
