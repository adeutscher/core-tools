#!/bin/bash

###################
# Background Jobs #
###################
# This section of the script is made to manage tasks that
# meet one or both of the following criteria:
#  - Long execution Time (in terms of conky scripts which should be taking fractions of a second)
#  - Updated infrequently, while being used by scripts
#      that have to otherwise be run more quickly
# It is assumed that the report scripts have already been independently debugged, as conky will show no direct output.
# Load common utilities and variables.
. functions/common

if ls "${reportRoot}/"*sh 2> /dev/null >&2;  then
  for script in ${reportRoot}/*sh; do
    bash $script 2> /dev/null >&2 &
  done
fi

# Run host-specific report. Most likely used by stuff in host-specific.sh
# This is a single file for the moment. IF it is needed, will move to a directory-based approach like with the common reports.
if [ -f "${reportRoot}/hosts/${HOSTNAME%-*}.sh" ]; then
  bash "${reportRoot}/hosts/${HOSTNAME%-*}.sh" 2> /dev/null >&2 &
fi

#################
# External Jobs #
#################
# This section of the script is made to print out any pre-formatted reports from external scripts
# These scripts were made because they matched at least one of two criteria:
#     - I didn't want to try to run the report-generating scripts every 30s like the current reports.
#     - The report-generation scripts contain sensitive information.
#           For example, the script that inspired this feature lists my recent e-mail.
#           The script reads in my credentials from elsewhere, but it still reveals more information
#               than I'd like to have in the more shareable "core tools" that these conky scripts are stored in.
cat "${tempRoot}/reports/"* 2> /dev/null

