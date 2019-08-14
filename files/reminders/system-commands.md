A few misc system commands.

# Commands in Editor

To open up an editor in order to methodically craft a command, the Ctrl+x+e shortcut.

If you want to revise previous command:

    fc

To revise a specific history number:

    fc 1234

To revise the first command beginning with a pattern:

    fc vi

**WARNING**": If you call up a command with `fc`, clear out the editor and use the 'save' function for your editor. If you do not do this, then every command line in the original output will be executed.

# Detect RAM

To get information on your system's RAM:

    sudo dmidecode --type 17

# Mount additional tmpfs

If you wish to mount up an additional RAM-based file system on top of the one normally mounted on `/tmp/`:

    mount -t tmpfs tmpfs /mnt/ram -o size=8192M
