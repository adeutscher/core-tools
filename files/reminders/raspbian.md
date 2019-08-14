# DHCP Config

To get Raspbian to pull an address when the kernel detects that a cable has been plugged in, add the following to `/etc/network/interfaces`:

    auto eth0
        allow-hotplug eth0
        iface eth0 inet dhcp

# Immediate SSH Access

By default, a Raspbian install will not have SSH access enabled. To enable SSH access off the bat, add an empty file named `ssh` to the boot partition on the SD card. For emphasis, this is the boot partition and not the `boot/` directory that the boot partition is mounted onto.

# Remove Desktop Packages

If you install a full version of Raspbian by accident when you really just wanted to install the minimal package:

    sudo apt-get remove --auto-remove --purge 'libx11-.*'
    sudo apt-get autoremove	
