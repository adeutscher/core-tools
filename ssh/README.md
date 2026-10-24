
# SSH Configuration

SSH config from `core-tools` and any attached modules are read in and written to a configuration file through the `ssh-compile-config` function.

Using this system allows me to maintain module-specific SSH configs and lets me avoid editing my SSH unless absolutely necessary.

## Usage

To compile SSH configuration to `~/.ssh/config`:

    ssh-compile-config

If you wish to write configuration to a different path (perhaps for debugging?), add the file path as your first argument:

    ssh-compile-config target-file

To also remove sections left behind by modules that are no longer loaded (see [Leftover Sections](#leftover-sections)):

    ssh-compile-config --clean

## Mechanics

### Structure

SSH configuration is read from the following locations in each loaded module (relative to the directory that the module was checked out to):

* `ssh/config`
  * **Note**: Having a `ssh/config` file is mandatory for the moment if you want to use a module for SSH. It can even empty if you want to exclusively use other loading options.
* `ssh/config.d/*` : Any files in this directory will be loaded.
  * The exception to this rule is any file with "readme" in its name, which will be ignored. This is to avoid loading `README.md` or any similar guide files into your SSH configuration and causing syntax errors.
* `ssh/fluid` and `ssh/fluid.d/` are used in the same way as `ssh/config` and `ssh/config.d/`. The expectation is that there is a `.gitignore` file that keeps these files out of version control.
  * `ssh/fluid` and `ssh/fluid.d/` were made with the idea that you might have SSH configurations to write that were too volatile to justifiably place in version control but that you would still want to keep organized within a module. I originally wrote the script to use these fluid files when I was doing a number of experiments with Amazon EC2 instances that would have a lifespan of hours.
* `ssh/hosts/config-$HOSTNAME`
  * Files in `ssh/hosts/` will only be loaded in if by a specific host. For example, `config-host.domain.lan` would only be loaded in on `host.domain.lan`.

### Updates

`ssh-compile-config` checks to see whether each module needs an update by grabbing a checksum of every path that the host would read in. Configurations are written in-place to preserve ordering. Because of this, it is very important that the header and footer markers for each module remain intact and don't get manually edited.

Because the config file is shared by multiple modules, it is expected to be a regular file. If it is a symlink, a warning is printed and an update will replace the link with a regular file.

All changes are made to a working copy, which is checked with `ssh -G` before being installed in a single step. If validation fails, the target file is left unchanged and the compiled config is kept at `<target>.failed` (e.g. `~/.ssh/config.failed`) for review. The previous config is backed up to `<target>.bak` whenever an update is installed. Where `flock` is available, `<target>.lock` prevents two runs from updating the file at the same time.

If an executable `.sh` or `.py` script in `config.d/` or `fluid.d/` fails, its output is left out and a comment noting the failure is written in its place.

`ssh-compile-config` exits with a status of 1 if any error occurred, including a failed script, a missing module directory, an unwritable config file, or a failed validation.

**Note**: The checksum process is for the moment an exception to the rule about "readme" files in `ssh/config.d/` being ignored.

### Leftover Sections

If the config file contains a section for a module whose `*toolsDir` variable is no longer defined, a warning is printed for it on every run. Running with `--clean` removes those sections instead. The removal goes through the same validation and backup as any other update.

* A module whose variable is still defined, but whose directory or `ssh/config` is missing, still counts as loaded. Its section is not reported or removed.
* A leftover section with no end marker is not removed, since there is no safe way to tell where it stops. It must be removed by hand.

### Priority

I needed a way of prioritizing the SSH configuration in the general *core-tools* over other modules, so `ssh-compile-config` will look for a priority in `ssh/priority`. This file holds a single integer. Blank lines and `#` comments are ignored. Modules with a lower number are considered to be earlier in the queue and will be written first. Modules without a priority use the default of **10**.

For older modules, a `# priority:N` comment on its own line in `ssh/config` is still read if `ssh/priority` does not exist, but a notice suggesting the move to `ssh/priority` will be printed.

**Note**: Priority ordering is ***not*** retro-active at the moment. If you add a module with a priority of **2** to a setup that already has a priority **1** and **12**, then the new **2** module will still only be appended to the configuration file. 

### SSH_DIR

Each module will substitute out "**SSH_DIR**" for the path to the SSH directory. This allows you to keep any required keys within your module and to avoid any manual work or the potential security problem of moving SSH keys outside of the version-controlled directory that the tools have been checked out to.

For example, if a module is checked out in `/home/user/work/office/tools`, then any instance of **SSH_DIR** in that module will be substituted for `/home/user/work/office/tools/ssh`

Example of an SSH entry using **SSH_DIR**:

    Host centos-vm-2
        hostname 10.11.12.13
        user local
        IdentityFile SSH_DIR/keys/centos-vm2-key

#### Similar Variables

In the same style as **SSH_DIR**, the following substitutions can also be used:

* **TOOLS_DIR**: Substituted for the base of your tool module's directory.
* **TOOLS_PARENT**: Subsituted for the parent directory of your tool module.
