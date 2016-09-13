
# Conky

This directory contains my `conky` setup.

My goal with this configuration was to make a flexible status display that could be used on multiple systems without needing to be adjusted each time.

## Usage 

The display must be started through `start.sh`.

Switches:

| **Switch**  | **Effect**                                                                                              |
|-------------|---------------------------------------------------------------------------------------------------------|
| `-h`        | Print a help menu and exit.                                                                             |
| `-s screen` | Place conky on a particular  monitor. Overrides `$CONKY_SCREEN`, and uses the same format.              |
| `-d`        | Debug mode. Runs `conky` in the foreground instead of the normal behavior of working in the background. |
| `-r`        | Restart. Runs `killall` to kill *all* `conky` instances before starting this display.                   |

### Variables

Conky uses the following environment variables:

* The `$CONKY_SCREEN` environment variable controls which screen that the display will appear in the bottom-right corner of.
  * Use `xrandr` to list your connected displays. Example values:
    * DVI-0
    * DVI-1
    * HDMI-0
  * If no value `CONKY_SCREEN` `-s` switch is given, then the default screen is your primary display.
* Set `CONKY_IGNORE_INTERFACES` to tell `conky` to ignore a given interface.
  * `CONKY_IGNORE_INTERFACES` should be a space-delimited list.
  * Example content to ignore both `wlan0` and `wlan1`: `export CONKY_IGNORE_INTERFACES="wlan0 wlan1"`
