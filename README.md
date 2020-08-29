
# core-tools

This is the central module for managing my scripts and tools.

## Setup

To set up the core module, run the setup script:

    ./tools/scripts/setup/setup-tools.sh

The `scripts/setup/` directory also contains the following setup assist scripts:

* `crontab-setup.sh`: Setup core cron jobs.
* `tmux-configuration.sh`: Set up `tmux` theme.
* `all.sh`: A lazy setup script that runs all of the above (including `setup-tools.sh`).

## Useful Features

The core tools hold a number of useful scripts and functions.

### Ansible

The `files/ansible/` directory is made to hold playbooks that I use for setting up my environments.

### Battery

If you are using a laptop, then you can use `battery` to display your remaining battery life.

### Conky

My `conky` display was made to support multiple systems with little to no reconfiguration. For more information on `conky`'s parameters, see the [conky directory](bash/conky).

### Network Connection Listing

You can use the `connections` command to list incoming and outgoing network connections.

This function has a number of switches for controlling output. Use `connections -h` for a full options listing.

The script also has a number of aliases for convenience:

* `connections-in-local`/`connections-out-local`: The inverse of `connections-in`, list all connections involving localhost.
* `connections-in-lan`: List incoming connections coming from IP addresses that are within `10.0.0.0/8`, `172.16.0.0/12`, or `192.168.0.0/16`.
* `connections-in-remote`: The inverse of `connections-in-lan`, lists IPs not within `10.0.0.0/8`, `172.16.0.0/12`, or `192.168.0.0/16`.
* `connections-in-all`: List all incoming connections.
* `connections-out-lan`: List outgoing connections coming from IP addresses that are within `10.0.0.0/8`, `172.16.0.0/12`, or `192.168.0.0/16`.
* `connections-lan`: A lazy alias of `connections-out-lan`.
* `connections-out-remote`: The inverse of `connections-out-lan`, lists IPs not within `10.0.0.0/8`, `172.16.0.0/12`, or `192.168.0.0/16`.
* `connections-out-all`: List all outgoing connections.

Other similar functions/aliases:

* `connections-in-ipv6`: List incoming IPv6 connections.
* `connections-out-ipv6`: List outgoing IPv6 connections.

### SSH Configuration Compilation

I use my module system to store SSH configurations in sub-modules. The sensitive nature of SSH configurations are a major part of why the module system even exists, and I wanted to create a convenient method of deploying them and applying changes.

    ssh-compile-config

SSH configuration compilation detects changes to your modules' SSH configuration files, and updates your `~/.ssh/config` file. It then reports in on modules that have had updated configurations. If you wish to test this feature without meddling with your current `~/.ssh/config` file, provide a path as your first argument:

    ssh-compile-config demo-config

For more information on `ssh-compile-config`, see the `README.md` file in the [SSH directory](ssh/) directory.

### Prompt

I've added a number of bells and whistles my prompt:

* Dynamic colouring for the following areas:
  * Username changes depending on who the current user is.
  * Hostname:
     * Certain network-only servers have blue hostnames.
     * Servers that I use for a desktop environment have green hostnames.
     * Some development or work machines have red hostnames.
   * File Path:
     * Local filesystems (**ext2**, **ext3**, **ext4**, **xfs**) are green.
     * Network file systems (**nfs**, **cifs**) are blue.
     * OS and memory-based filesystems (**sysfs**, **proc**, any kind of **tmpfs**) are purple.
     * Hot-plugged filesystems (**udf**, **fuseblk**, any kind of **ntfs** or **fat** filesystem) are red.
  * Box edges are set by the output of `uname`:
     * Linux systems are in a blue box.
     * FreeBSD systems are in a red box.
     * Mac OSX systems are in a yellow box.
     * Windows systems using MobaXterm are in a cyan box. This feature is currently not tested for other Unix-in-Windows environments.
  * Prompt Symbol (**$** for non-root, **#** for root):
     * If the previous command was not found (*exit code 127*), then the symbol will be yellow.
     * If we attempted to run a script without the execute permission (*exit code 126*), then the symbol will be cyan.
     * If the previous command gave a non-zero exit code not covered above, then the symbol will be red.
     * If the previous command exited successfully with an exit code of *0*, then the symbol will be white.
* Remote SSH client.
  * The remote address will not be displayed if your terminal session was started within a `tmux`, `screen`, or `vnc` session.
  * This feature will be disabled if the `PROMPT_IGNORE_SSH` environment variable has a non-zero value.
  * Use the `prompt-toggle-ssh` function to toggle this feature off or on.
* Version control information:
  * SVN version information (Credit: [Eric Leblond](https://github.com/regit/subversion-prompt))
  * Git branch and status information (Credit: http://ezprompt.net/).
  * If you need a reminder of what the red indicators in `git` repository mean, use the `git-prompt-reminder` function.
  * Version control information will not be printed for NFS/CIFS file systems due to performance concerns.
  * SVN output will take precedence over Git output, if you have a directory that for some reason has both.
  * This feature will be disabled if the `PROMPT_IGNORE_VC` environment variable has a non-zero value.
  * Use the `prompt-toggle-version-control` function to toggle this feature off or on.
 (Set a value to `PROMPT_IGNORE_VC` to disable this)
* Compression. If the prompt gets to be so large that you begin running out of room, then the prompt will be shortened:
  * Hostname will be shortened to one character.
  * Username will be shortened to one character.
  * Only the name of the current directory will be displayed.
  * This feature will be permanently enabled if the `PROMPT_ALWAYS_COMPRESS` environment variable has a non-zero value.
  * Use the `prompt-toggle-compression` function to toggle dynamic compression off or on.
  * There is currently not an option for "never compress".
* Temporary hostname/username display change, useful for when you are debugging or recording demonstration videos.
  * Setting `DISPLAY_USER` will override the display of your session's real username in the prompt.
  * Setting `DISPLAY_HOSTNAME` will override the display of your server's real hostname in the prompt.

#### Variables

If you want to disable all of these bells and whistles, set the `BASIC_PROMPT` variable to **1**.

### rdp

The `scripts/networking/rdp.py` is made to make the `xfreerdp` command more convenient to use.
It is available in `bin/` under the name `rdp`.

It boils down basic usage to a basic `rdp target-server`, whether you are using a older version of `xfreerdp` or a modern one.

Arguments:

| Argument    | Description                                                             | Example                      |
|-------------|-------------------------------------------------------------------------|------------------------------|
| -d domain   | Sets the login domain.                                                  | `-d LOCALDOMAIN`             |
| -e          | Key file, implying an EC2 instance. Requires boto3 and pycrypto         | `-e path-to-keyfile`         |
| -g          | Single-argument for display geometry (WxH).                             | `-g 800x600`, `-g 800,600`   |
| --height    | Sets display height.                                                    | `--height 600`               |
| -p password | Sets the login password.                                                | `-p swordfish`               |
| -P          | Prompt for a password.                                                  | `-P`                         |
| -u user     | Sets the login user. Also accepts domain name using backslash.          | `-u user`, `-u DOMAIN\\user` |
| -width      | Sets display width.                                                     | `-width 800`             |

#### Variables

You can set the following environment variables to adjust your default RDP parameters:

* `RDP_WIDTH` sets the width of the `rdp` window (default: 1600).
* `RDP_HEIGHT` sets the height of the `rdp` window (default: 900).
* `RDP_USER` sets the domain.
* `RDP_USER` sets the user.
* `RDP_PASSWORD` sets the password.

Each of these environment variables can be overridden by manually specifying a value in the `rdp.sh` script.

### Sleep

A few lazy functions for sleeping (each one only accepts integers):

* `sleep-minutes`
* `sleep-hours`
* `sleep-days`
* `countdown-seconds`
* `countdown-minutes`
* `countdown-hours`
* `countdown-days`

## Modules

I made a module-based system for storing functions in order to limit unneeded data leaks.

### Module Creation

A directory is considered to be a module if it has a `bash/bashrc` file that defines a tools directory variable.

The tools directory variable must:

* Have a unique amongst the tool directories.
* Draw off of `$__current_module_dir` variable, which is set in the cycling of the `bashrc` file of these core tools that loads in modules.
  * The exception to this is `$toolsDir`, which is set in a system bashrc or `~/.bashrc` by the setup script.
    * A number of modules do fall back to guessing at a location, but this is not recommended.
* End in `ToolsDir` (case-insensitive).
    This is necessary because some functions (`ssh-compile-config`, for example)
    actually looks for tool directory variables in order to work.

### Locations

Modules are read out of the following directories:

| Location                                                                  | Example(s)                                          |
|---------------------------------------------------------------------------|-----------------------------------------------------|
| `~/tools` directory                                                       | `~/tools`, `~/tools/core-tools`                     |
| `~/work`directory                                                         | `~/work/company-a-tools`, `~/work/company-b/tools`  |
| `modules`directory, nested within core tools checkout (SVN checkout only) | `modules/audio-tools`                               |
| `secure` directory, nested within core tools checkout (SVN checkout only) | `secure/`                                           |

### History

The original tools were just a single directory stored in SVN in order to avoid having to manually keep my different scripts in sync.

As my needs for my tools expanded, I wanted to start placing them on more systems.
The problem with this was that the original tools directories had some very sensitive material on them,
    such as network configurations, passwords, and SSH keys.

I originally only had one "*secure*" module, which would be checked out to the `secure/` path within the tools checkout.
The nesting relied on the `svn` command throwing an error if someone tried to add it to tools. Even with `.gitignore` as an option,
    the modern core-tools will not accept nesting in a `git` checkout.

Over time, I needed to split things up even more.
The following kind of problems were not covered by just the main tools and "*secure*" tools:

* Sharing functions/aliases affecting a private resource.
* Needing specific pieces of the "*secure*" tools on a system that I didn't want other information on.
* A lot of functions that would **never** even need to be considered on certain systems. For example:
  * A headless server will never need sound-playing aliases.
  * A headless server or work-oriented machine should never need to load game aliases.
* Work-related information that I did not want to live in any locally hosted repository.

