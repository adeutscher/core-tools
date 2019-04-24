#!/usr/bin/python

# Take messages collected over a network and display them as desktop notifications.

import os, re, subprocess, sys
import SimpleMessages as sm
sm.local_files.append(os.path.realpath(__file__))
# Commonly-used items from SimpleMessages
from SimpleMessages import args, colour_text

COMMAND_NOTIFY = "notify-send"
TITLE_SKIP_NOTIFY = "no-notify"
args.add_opt(sm.OPT_TYPE_FLAG, "n", TITLE_SKIP_NOTIFY, "Do not invoke %s, only printing to standard output." % colour_text(COMMAND_NOTIFY, sm.COLOUR_BLUE))

class DesktopNotifyHandler:
    def __init__(self, session):
        self.session = session
        if session.udp:
            session.reply = False

    def handle(self, header, data):
        # Strip out everything including  after the first newline.
        # Ignore unprintable characters.
        message = re.sub(r"\n.*", "", data)

        if not message or re.match(r"[^ -~]", message):
            # We stripped out ALL data or found unprintable bytes.
            # Print an error and do not go to desktop notification.
            # This probably triggers because the script was run on a
            #   common port and picked up another protocol.
            if print_headers:
                sm.print_error("%s: %s%s%s" % (header, colour_text("No printable data.", sm.COLOUR_RED)))
            return

        sm.print_notice("%s: %s" % (header, message))

        if args[TITLE_SKIP_NOTIFY]:
            return # Notifications disabled. Return after printing to standard output.

        icon = "network-receive" # Default icon
        # Regex search message to make some attempt at context-specific icons.
        if re.match(r"important", message, re.IGNORECASE):
            icon = "dialog-warning"
        if re.match(r"error", message, re.IGNORECASE):
            icon = "dialog-error"
        elif re.match(r"urgent", message, re.IGNORECASE):
            icon = "software-update-urgent"
        elif re.match(r"appointment", message, re.IGNORECASE):
            icon = "appointment"
        elif re.match(r"(firewall|security)", message, re.IGNORECASE):
            icon = "security-medium" # I like the MATE medium security icon more than the high security icon.

        try:
            p = subprocess.Popen([COMMAND_NOTIFY, "--icon", icon, "Message from %s" % self.session.addr[0], message])
            p.communicate()
        except OSError as e:
            print_error(sys.stderr, "OSError: %s" % str(e))
            return "os-error\n"
        return "printed\n"

if __name__ == '__main__':
    args.process(sys.argv)
    sm.announce_common_arguments("Printing notifications")
    sm.serve(DesktopNotifyHandler)
