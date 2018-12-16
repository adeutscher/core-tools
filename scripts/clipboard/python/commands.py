
# Note: These functions assume that my common message functions are also being used.
#       Replace print_foo functions with a flat print if this is not the case.

import os, subprocess, sys

#
# Command running and escalation functions.
#

def confirm_root_or_rerun():
    if not os.geteuid():
        # Already root, no need to continue.
        return

    cmd = list(sys.argv)
    cmd.insert(0, "sudo")

    print_notice("We are not %s, so %s will be re-run through %s." % (colour_text(COLOUR_RED, "root"), colour_text(COLOUR_GREEN, cmd[1]), colour_text(COLOUR_BLUE, cmd[0])))

    # Run command. Do not set sudo_required because of the alternate message was printed above.
    exit(run_command(cmd))

def run_command(cmd, sudo_required = False, ctrl_c_error = True, stdout = sys.stdout, stderr = sys.stderr):
    ret = 0
    try:
        if sudo_required and os.geteuid():
            command_list.insert(0, "sudo")
            print_notice("We are not %s, so %s will be run through %s." % (colour_text(COLOUR_RED, "root"), colour_text(COLOUR_BLUE, cmd[1]), colour_text(COLOUR_BLUE, cmd[0])))

        p = subprocess.Popen(cmd, stdout = stdout, stderr = stderr)
        p.communicate()
        ret = p.returncode
        if ret < 0:
            ret = 1
    except KeyboardInterrupt:
        # If ctrl_c_error is set to False, then ctrl-c'ing out of of the script is an expected action.
        if ctrl_c_error:
            ret = 130
    except Exception as e:
        print_exception(e)
        ret = 1
    return ret
