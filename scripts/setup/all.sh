#!/bin/bash

# Load common functions.
. "$(dirname "${0}")/functions.sh"

notice "Running all major tool setup scripts."

for s in setup-tools.sh crontab-setup.sh tmux-configuration.sh vimrc-setup.sh; do
  notice "$(printf "Running ${GREEN}%s${NC}" "${s}")"
  ./$s || error "$(printf "Setup failed for ${GREEN}%s${NC}" "${s}")"
done

exit 0
