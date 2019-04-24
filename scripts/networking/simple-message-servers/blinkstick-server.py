#!/usr/bin/python

# A likely over-engineered script to relay UDP datagrams from one host to multiple targets.
# I mostly made this to work with my desktop-notify-relay.py script and its audio-playing cousin.

import os, sys, thread, time
import SimpleMessages as sm
sm.local_files.append(os.path.realpath(__file__))
# Commonly-used items from SimpleMessages
from SimpleMessages import args, colour_text
try:
    from blinkstick import blinkstick
except ImportError:
    print_error("Unable to import %s module." % colour_text("blinkstick"))
    exit(1) # Exit immediately, as regular argument parsing depends on blinkstick module.

DEFAULT_COUNT = 8
DEFAULT_PORT = 3333
sm.set_default_port(DEFAULT_PORT)

TITLE_COUNT = "light count"
TITLE_SERIAL = "serial number"
args.add_opt(sm.OPT_TYPE_SHORT, "c", TITLE_COUNT, converter = int, default = DEFAULT_COUNT, default_announce = True, description="Number of lights on BlinkStick.")
args.add_opt(sm.OPT_TYPE_SHORT, "s", TITLE_SERIAL, description="Declare a specific BlinkStick serial number.")

DATA_COLOUR = 1
DATA_STYLE = 2
DATA_UNTIL = 3

DATA_STYLE_SOLID = "solid"
DATA_STYLE_BLINK = "blink"
STYLES = [DATA_STYLE_SOLID, DATA_STYLE_BLINK]

DATA_DEFAULT_COLOUR = "off"
DATA_DEFAULT_STYLE = DATA_STYLE_SOLID

def background_thread():
    tick = 0
    count = args[TITLE_COUNT]
    while True:
        try:
            for i in range(count):
                s = states[i]
                until = s.get(DATA_UNTIL, 0)
                if until > 0 and until < time.time():
                    states[i] = {}
                    continue

                colour = s.get(DATA_COLOUR, DATA_DEFAULT_COLOUR)
                if colour == DATA_DEFAULT_COLOUR:
                    device.set_color(index = i, name = "off")
                    continue

                style = s.get(DATA_STYLE, DATA_DEFAULT_STYLE)
                if style == DATA_STYLE_BLINK and tick % 2:
                    colour = DATA_DEFAULT_COLOUR
                device.set_color(index = i, name = colour)
        except Exception as e:
            sm.print_exception(e, "Background Worker")

        tick = (tick + 1) % 2 # Prep for next loop
        time.sleep(time.time() % 0.25) # Sleep until next tick.

def summarize_arguments():
    sm.announce_common_arguments("Managing blinkstick device")
    if args[TITLE_SERIAL]:
        sm.print_notice("Manual BlinkStick serial: %s" % colour_text(args[TITLE_SERIAL]))

def validate_blinkstick_device(self):
    global device
    if self[TITLE_SERIAL]:
        device = blinkstick.find_by_serial(self[TITLE_SERIAL])
        if device is None:
            return "Unable to find an attached BlinkStick with serial: %s" % colour_text(self[TITLE_SERIAL])
    else:
        device = next(iter(blinkstick.find_all()), None)
        if device is None:
            return "Unable to find an attached BlinkStick device."

def validate_count(self):
    if self[TITLE_COUNT] <= 0:
        return "Light count must be greater than 1."
    global states
    states = [{} for i in range(self[TITLE_COUNT])]

args.add_validator(validate_count)
args.add_validator(validate_blinkstick_device)

class BlinkstickServerHandler:
    def __init__(self, session):
        self.session = session
        self.json = True

    def handle(self, header,  data):
        # ToDo: Improve on validation.
        index = int(data.get("index", 0))
        colour = data.get("colour", data.get("color", DATA_DEFAULT_COLOUR))
        style = data.get("style", DATA_DEFAULT_STYLE)
        duration = int(data.get("time", 0))
        if duration > 0:
            duration += time.time()

        states[index] = {DATA_COLOUR: colour, DATA_STYLE: style, DATA_UNTIL: duration}

        device.set_color(index = index, name = colour)

if __name__ == '__main__':
    sm.set_mode_tcp_default()
    args.process(sys.argv)
    summarize_arguments()
    thread.start_new_thread(background_thread, ())
    sm.serve(BlinkstickServerHandler)
