
# System Scripts

Scripts for working with desktop systems, hardware, and system processes.

## add-ca-cert.sh

A lazy script to add a truster CA certfificate.

Usage example:

    ./add-ca-cert.sh self-signed.crt

## beep.sh

Attempt to make a 'beep' noise with the system speaker.

Usage:

    ./beep.sh [beep-count]

The beep count draws a cap on beeps per call at 25.

## burn.sh

Lazy wrapper around `wodim`/`cdrecord`.

Usage:

    ./burn.sh item.iso

## countdown-seconds.sh

Do a countdown of seconds. Usage example:

    ./countdown-seconds.sh 300

## hash-index.sh

Store checksums in a data file (currently `~/.local/hash-index.dat`, echoing out the old hash. This was made as a way to track updates to items like configuration files or scraped web pages.

Example of usage:

    ./hash-index.sh keyword 5eb63bbbe01eeed093cb22bb8f5acdc3

The script will always output the value for the key that was stored in the index when the script was invoked. This is to say that if a new hash is entered, the old hash will be printed. This allows the script to be used as intended within other scripts to see if something has changed. An example of this in another script would be:

    checksum="$(md5sum <<< "${data}" | cut -d' ' -f1)"
    if [[ "${checksum}" != "$(./hash-index.sh keyword "${checksum}")" ]]; then
      echo "An update happened."
    fi

## memdump.sh

A wrapper around a technique suggested by some StackOverflow/LinuxQuestions users to dump a processes memory.

Usage:

    ./memdump.sh 1234 [...]

Note:

* You must be root to read processes that you do not own.

## script-output-wrapper.sh

This wrapper was made to deal with the problems caused by problems like this:

    ./other-script.sh > file.data

If the destination file is constantly being read from (such as by a `conky` display), then there could be a disruption to the display when the destination file is truncated as the script runs.

An example of this script in use:

    ./script-output-wrapper.sh file.data ./other-script.sh

## security-check.sh

Attempts to skim through a system to detect possible security problems.

Usage:

    ./security-check.sh

The following checks are performed:

* Hak5 devices: Look for potential Hak5 devices plugged into the machine such as a LANTurtle. Also look to see if the system is connected to a WiFi access point with a Hak5 MAC.
   * This check is based on Hak5's habit of using a '00:13:37' prefix by default. However, this check is a bit flimsy because the sort of person to use the device in a serious manner would also be likely to just change their MAC address in the device's configuration.
* List all users with key-based SSH logins. Users in `/home` with key logins are noteworthy to mundane, while other users with keyless logins might be a bit more troubling.
   * Users probably will not be checkable if you are not `root`.
   * This check goes off of `/etc/passwd`, so it will not pick up on users acquired from outside services such as SSSD.
* Check for masked processes.
  * It is fairly easy to mask a process so that it appears to have a different name/arguments in `ps` and similar. However, the original command still survives in the procfs entry for that command. This function looks through all possible processes to see if the call in the `exe` path matches the command information in `cmd`.
     * `exe` presents as a symbolic link, but it is freaky and different.
  * In order to check processes that you do not own, you will need to be `root`.
  * This check still has some false positives that I have not dealt with. Most of these are systemd-related.
* Check for ShellShock. Should not trigger on pretty much any system that has been updated in the last 4 years or so.

## toggle-touchpad.sh

Turn your laptop touchpad on/off.

Usage:

    ./toggle-touchpad.sh

## update-dotfile.sh

Updates the contents of a dotfile by inserting content in a section. If the content was updated since its last run, then the content shall be replaced in its original position.

Usage:

    ./update-dotfile.sh target-file file-marker content-path [comment-character]

Arguments:

* target-file: Path of file to be written to
* file-marker: Internal marker to place within file. Each marker should be unique amongst sections.
* content-path: Path to file containing contents. Set to '-' to instead read from stdin. If content is empty, then the script will abort without writing anything.
* comment-character: Character used to initiate a comment. Defaults to '#'

## wait-for-pid.sh

Wait for processes by PID or name

Usage examples:

    ./wait-for-pid.sh 1234 [...] [-s interval]
    ./wait-for-pid.sh yum [...] [-s interval]

Notes:

* The `-s` switch can be used to specify how often processes should be checked for completeness. By default, this is every 0.5 seconds.
* The script currently assumes that a PID will not be re-used by another process between check intervals.
* If no PIDs exist when the script is invoked, then the script will exit with a non-zero exit code.
* Process names are dealt with by invoking `pgrep`. `pgrep` reads off of the Linux procfs. Procfs is a bit unfortunate in that the name of a process (which `pgrep` searches for by default trims the process name to be a maximum of 15 characters.
  Command searches longer than 15 characters shall not register.
* A downside of this script is that it is unable to detect whether or not a process ended with a non-zero exit code.

### Use Cases

This script might be useful for the following kinds of situations:

* If you want to begin multiple actions simultaneously after another job has finished, then multiple instances of `wait-for-pid` could be used.
* Being non-commital to actions taken after long-running processes. For example, `dnf upgrade && poweroff` would mean that you either need to cancel a system upgrade or shut down your machine. `wait-for-pid` allows long-running tasks to remain open while a shutdown was cancelled.
* On the other hand, the script could be used to add on actions after a long-running process after the process has already been started. To flip the previous non-commital example, one could add `wait-for-pid dnf && poweroff` to shut down a machine after an upgrade had finished.

## zombie-scanner.sh

A script by Marius Voila (https://www.mariusv.com/automatic-zombie-processes-killing-shell-script) to look for and optionally kill zombie processes.

Usage:

    ./zombie-scanner.sh {--cron|--admin}
