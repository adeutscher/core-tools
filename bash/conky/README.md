
# Conky

This directory contains my `conky` setup.

My goal with this configuration was to make a flexible status display
  that could be used on multiple systems without needing adjust scripts
  each time.
  
For per-system adjustments, the scripts in this configuration
  will listen to various environment variables (described below).

## Usage 

The display must be started through `start.sh` in order
  to be properly positioned.

Switches:

| **Switch**  | **Effect**                                                                                                                            |
|-------------|---------------------------------------------------------------------------------------------------------------------------------------|
| `-h`        | Print a help menu and exit.                                                                                                           |
| `-s screen` | Place conky on a particular  monitor. Overrides `CONKY_SCREEN`, and uses the same format. See below.                                  |
| `-d`        | Debug mode. Runs `conky` in the foreground instead of the normal behavior of working in the background.                               |
| `-r`        | Restart. Runs `killall` to kill ***all*** `conky` instances before starting this display. Beware if running a separate configuration. |

### Variables

Conky uses the following environment variables:

* Export a different value to `DISPLAY_HOSTNAME` to change the
    displayed hostname. Useful for if you need to temporarily
    obfuscate your hostname for a screenshot.
* The `$CONKY_SCREEN` environment variable controls which screen that
    the display will appear in the bottom-right corner of.
  * Use `xrandr` to list your connected displays. Example values:
    * DVI-0
    * DVI-1
    * HDMI-0
  * If no value is given in either the `CONKY_SCREEN` variable or the
      `-s` switch, then the default screen is your primary display.
* The `CONKY_PADDING_X` (default **10**) and `CONKY_PADDING_Y`
    (default **35**) variables determine the offset of your conky
    display from your chosen screen.
  * The defaults were chosen to give a sliver of padding from the
      right-hand side of a screen and a MATE panel.
* Set `CONKY_IGNORE_INTERFACES` to tell `conky` which network interface(s) to ignore.
  * `CONKY_IGNORE_INTERFACES` should be a space-delimited list.
  * Example content to ignore both `wlan0` and `wlan1`:
      `export CONKY_IGNORE_INTERFACES="wlan0 wlan1"`
* Set `CONKY_IGNORE_FS` to tell `conky` which file system(s) to ignore.
  * `CONKY_IGNORE_FS` should be a space-delimited list.
  * Example content to ignore the file systems mounted to `/mnt` and `/srv`:
      `export CONKY_IGNORE_FS="/mnt /srv"`
* Set `CONKY_NETWORK_INDEX` and `CONKY_NETWORK_CACHE` to set where
    `conky` for a CSV to use for resolving MAC addresses to
    user-friendly labels (see below for notes on using labels).
  * By default, `CONKY_NETWORK_INDEX` links to my "secure" module using
      the `secureToolsDir` variable. This makes the default fairly
      useless to anyone who doesn't use an identical naming scheme.
* Some environment variables beginning with `CONKY_DISABLE_` disable
    specific features if you absolutely do not want a feature on a
    particular system.
  * Set `CONKY_DISABLE_TMUX` to **1** to disable the display of `tmux` sessions.
  * Set `CONKY_DISABLE_FILES` to **1** to disable the display of
      file system information.
  * Set `CONKY_DISABLE_NETWORK` to **1** to disable the display of
      networking information.
  * Set `CONKY_DISABLE_BLUETOOTH` to **1** to disable the display of
      connected Bluetooth devices.
  * Set `CONKY_DISABLE_VMS` to **1** to skip the VM display in `scripts/vms.sh`

## `virsh`

In order to use `virsh` to list virtual machines, it's assumed that the user
    has permissions to list VMs in a terminal. I do this by creating
    a PolKit rule like this one in a `.rules` file in `/etc/polkit-1/rules.d/`:

    polkit.addRule(function(action, subject) {
        if (action.id == "org.libvirt.unix.manage" &&
            subject.isInGroup("wheel")) {
                return polkit.Result.YES;
        }
    });

## Network Labels

In order to make some features more human-friendly, I implemented
  a system of resolving MAC addresses to human-friendly labels.

Below is a sample of the format used by the files specified in the
  `CONKY_NETWORK_INDEX` and `CONKY_NETWORK_CACHE` environment variables:

    owner,type,mac,label,general-location,specific-location,description,notes
    Bob,Bluetooth,18:2a:7b:3d:aa:bb,WiiU Pro,Home,Bookshelf,Used for games,purchased 2014
