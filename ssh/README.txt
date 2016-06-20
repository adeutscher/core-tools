SSH config is read in and written to ~/.ssh/config through the ssh-compile-config function.

Note: Having a config file in ssh/ is mandatory, but after that you may segment the files by placing any config files in config.d/ or a host-specific file in hosts/. Host-specific files must be named in the format (config-$HOSTNAME)
