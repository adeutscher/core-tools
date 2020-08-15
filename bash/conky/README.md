
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

The following environment variables can be exported to affect my `conky` display:

| Variable                  | Effect                                                                                                        | Example Value(s)    |
|---------------------------|---------------------------------------------------------------------------------------------------------------|---------------------|
| CONKY_SCREEN              | Controls primary display location. Display will be placed in the bottom-right corner.                         | DVI-1, HDMI-0       |
| CONKY_PADDING_X           | Horizontal offset of primary display from bottom-right corner (default: 10).                                  | 10                  |
| CONKY_PADDING_Y           | Vertical offset of primary display from bottom-right corner (default: 35).                                    | 35                  |
| CONKY_INTERVAL            | Primary display's update interval in seconds (default: 2.0)                                                   | 2.0                 |
| CONKY_DISABLE_LUA         | Set to '1' to disable Lua-driven rounded corners. Useful if conky does not have Cairo support.                | 1                   |
| CONKY_ENABLE_CLOCK        | Set to '1' to enable a time display in system information area.                                               | 1                   |
| CONKY_ENABLE_TASKS        | Set to '1' to enable the secondary display (off by default). See "Tasks Display" section for more information | 1                   |
| CONKY_SECONDARY_SCREEN    | Controls secondary display location. Display will be placed in the bottom-right corner.                       | DVI-1, HDMI-0       |
| CONKY_SECONDARY_PADDING_X | Horizontal offset of secondary display from bottom-left corner (default: 10).                                 | 10                  |
| CONKY_SECONDARY_PADDING_Y | Vertical offset of secondary display from bottom-left corner (default: 35).                                   | 35                  |
| CONKY_INTERVAL            | Secondary display's update interval in seconds (default: 3.14)                                                | 3.14                |
| CONKY_TASKS_FILE          | Path to tasks CSV file read by secondary display.                                                             | ${HOME}/tasks.csv   |
| CONKY_WINDOW_TYPE         | Customize `own_window_type` window type property in `conky` configuration.                                    | override, dock      |
| CONKY_IGNORE_INTERFACES   | Space-delimited list of network interfaces to be ignored.                                                     | "lo eth0"           |
| CONKY_IGNORE_FS           | Space-delimited list of file systems to be ignored.                                                           | "/srv/data"         |
| CONKY_ALL_NFS_FAR         | Treat all NFS/CIFS mounts as "remote" by default and do not print space information.                          | 1, 0                |
| CONKY_NETWORK_INDEX       | Set location of MAC label index (see below for notes on using MAC labels).                                    | "${HOME}/index.csv" |
| CONKY_NETWORK_INDEX       | Set location of MAC label cache (see below for notes on using MAC labels).                                    | "/tmp/index.csv"    |
| CONKY_DISABLE_TMUX        | Do not run list `tmux` sessions.                                                                              | 1                   |
| CONKY_DISABLE_FILES       | Do not list file system information.                                                                          | 1                   |
| CONKY_DISABLE_NETWORK     | Do not run list network interface information.                                                                | 1                   |
| CONKY_DISABLE_BLUETOOTH   | Do not list connected Bluetooth devices.                                                                      | 1                   |
| CONKY_DISABLE_VMS         | Do not list virtual machines.                                                                                 | 1                   |
| DISPLAY_HOSTNAME          | Spoof hostname display. Useful for screenshots. Can also be set with `prompt-set-hostname` function           | demo.localdomain    |

#### Tasks Display

Example format of the CSV file specified by `CONKY_TASKS_FILE`:

    YYYY-MM-DD,HH:MM,LABEL

Example content of the CSV file specified by `CONKY_TASKS_FILE`:

    2017-01-02,16:00,Afternoon appointment

Populating this file is the responsibility of the user,
    whether manually or through a separate script.

## `virsh`

In order to use `virsh` to list virtual machines, it's assumed that the user
    has permissions to list VMs in a terminal. This can be done with a PolKit rule
    in a `.rules` file in `/etc/polkit-1/rules.d/` such as the one below for the ***wheel*** group:

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
    Bob,Bluetooth Device,18:2a:7b:3d:aa:bb,WiiU Pro,Home,Bookshelf,Used for games,purchased 2014
