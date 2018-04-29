
# Setup Scripts

This directory is for general one-off scripts for things like setting up these tools or setting up `tmux`.

Since these scripts are so closely tied to the workings of the tool suite itself and lean on an existing script for update functions,
  these tools will break my usual rule of making scripts that can be easily plucked from the collection by using a common functions file.

## crontab-setup.sh

Gets common crontab jobs that I use across multiple machines and appends them to my crontab.

## export-prep.sh

Fully sanitize the core tools module for public release.

## get-tools

`get-tools.sh` is a lazy buton for downloading other tools modules. Use `./get-tools.sh -h` for a full options listing.

## install-basic-packages.sh

Install a few basic packages on fresh systems. Since I only look at it when I have a new system that will use these tools, it doesn't get updated a whole lot.

## make-tmux-configuration

Make a `tmux` configuration file. Colour scheme will vary based on hostname.

## setup-tools

Set up the core tools so that they will be loaded with future terminal sessions.

## vimrc-setup
