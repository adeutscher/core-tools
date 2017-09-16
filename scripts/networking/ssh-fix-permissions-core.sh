#!/bin/bash

# Confirm permissions out of ~/.ssh/
# Assuming that the source files from individual modules are properly secured by their appropriate update functions.
sshConfigDir=$HOME/.ssh

dir-permission-template-ssh "$sshConfigDir" || exit 1
