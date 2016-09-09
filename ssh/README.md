
# SSH Configuration

SSH config from `core-tools` and any attached modules are read in and written to a configuration file through the `ssh-compile-config` function.

Using this system allows me to maintain module-specific SSH configs and lets me avoid editing my SSH unless absolutely necessary.

## Usage

To compile SSH configuration to `~/.ssh/config`:

    ssh-compile-config

If you wish to write configuration to a different path (perhaps for debugging?), add the file path as your first argument:

    ssh-compile-config target-file

## Mechanics

### Structure

SSH configuration is read from the following locations in each loaded module (relative to the directory that the module was checked out to):

* `ssh/config`
  * **Note**: Having a `ssh/config` file is mandatory for the moment if you want to use a module for SSH. It can even empty if you want to exclusively use other loading options.
* `ssh/config.d/*` : Any files in this directory will be loaded.
  * The exception to this rule is any file with "readme" in its name, which will be ignored. This is to avoid loading `README.md` or any similar guide files into your SSH configuration and causing syntax errors.
* `ssh/hosts/config-$HOSTNAME`
  * Files in `ssh/hosts/` will only be loaded in if by a specific host. For example, `config-host.domain.lan` would only be loaded in on `host.domain.lan`.

### Updates

`ssh-compile-config` checks to see whether each module needs an update by grabbing a checksum of every path that the host would read in. Configurations are written in-place to preserve ordering. Because of this, it is very important that the header and footer markers for each module remain intact and don't get manually edited.

**Note**: The checksum process is for the moment an exception to the rule about "readme" files in `ssh/config.d/` being ignored.

### Priority

I needed a way of prioritizing the SSH configuration in the general *core-tools* over other modules, so `ssh-compile-config` will look for a priority tag in `ssh/config`. Modules with a lower number are considered to be earlier in the queue and will be written first.

**Note**: Priority ordering is ***not*** retro-active at the moment. If you add a module with a priority of **2** to a setup that already has a priority **1** and **12**, then the new **2** module will still only be appended to the configuration file. 

### SSH_DIR

Each module will substitute out "**SSH_DIR**" for the path to the SSH directory. This allows you to keep any required keys within your module and to avoid any manual work or the potential security problem of moving SSH keys outside of the version-controlled directory that the tools have been checked out to.

For example, if a module is checked out in `/home/user/work/office/tools`, then any instance of **SSH_DIR** in that module will be substituted for `/home/user/work/office/tools/ssh`

Example of an SSH entry using **SSH_DIR**:

    Host centos-vm-2
        hostname 10.11.12.13
        user local
        IdentityFile SSH_DIR/keys/centos-vm2-key
