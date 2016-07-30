SSH config is read in and written to ~/.ssh/config through the ssh-compile-config function.

Note: Having a ssh/config is mandatory if you want to use a module for SSH, but after that you may segment the files by placing any config files in config.d/ or a host-specific file in hosts/. ssh/config can even be empty, if you want. The host-specific files in hosts/ must be named in the format "config-$HOSTNAME".

== SSH_DIR ==

Each module will substitute "SSH_DIR" for the path. This allows you to keep any required keys within your module and to avoid any manual work.

For example, if a module is checked out in "/home/user/work/office/tools", then any instance of SSH_DIR in that module will be substituted for "/home/user/work/office/tools/ssh"

Example of an SSH entry using SSH_DIR:

    Host centos-vm-2
        hostname 10.11.12.13
        user local
        IdentityFile SSH_DIR/keys/centos-vm2-key


