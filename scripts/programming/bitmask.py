#!/usr/bin/env python

from __future__ import print_function
from getopt import gnu_getopt as get_args
from json import load as load_json
from json.decoder import JSONDecodeError
import logging, os, sys, re

def _build_logger(label, err = None, out = None):
    obj = logging.getLogger(label)
    obj.setLevel(logging.DEBUG)
    # Err
    err_handler = logging.StreamHandler(err or sys.stderr)
    err_filter = logging.Filter()
    err_filter.filter = lambda record: record.levelno >= logging.WARNING
    err_handler.addFilter(err_filter)
    obj.addHandler(err_handler)
    # Out
    out_handler = logging.StreamHandler(out or sys.stdout)
    out_filter = logging.Filter()
    out_filter.filter = lambda record: record.levelno < logging.WARNING
    out_handler.addFilter(out_filter)
    obj.addHandler(out_handler)
    return obj
logger = _build_logger('bitmask')

# Colour functions

def _enable_colours(force = None):
    global COLOUR_BOLD
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_OFF
    if force == True or (force is None and sys.stdout.isatty()):
        # Colours for standard output.
        COLOUR_BOLD = '\033[1m'
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_YELLOW = '\033[1;93m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_BOLD = ''
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_YELLOW = ''
        COLOUR_OFF = ''
_enable_colours()

def colour_text(text, colour = None):
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return '%s%s%s' % (colour, text, COLOUR_OFF)

# Script Functions

def display(value, **kwargs):

    mask = kwargs.get('mask', 0)
    guide = kwargs.get('guide')
    only_true = kwargs.get('only_true')

    if mask:
        logger.info('Filtering value of %d (%#08x) through a mask of %d (%#08x)' % (value, value, mask, mask))

        result = value & mask
        s = 'Result: %#08x & %#08x = %#08x (%d) ' % (value, mask, result, result)
        if result:
            if (value & mask) == mask:
                s += colour_text('Full Match', COLOUR_GREEN)
            else:
                s += colour_text('Partial Match', COLOUR_YELLOW)
        else:
            s += colour_text('No Match', COLOUR_RED)
        logger.info(s)

        value = result

    if not value:
        return

    logger.info('Getting the bitmask flags in value of %d (%#08x)' % (value,value))

    power = 0
    num = 0
    limit = max(value, mask)

    while True:
        num = pow(2, power)

        if num > limit:
            break

        result = value & num

        if not result and only_true:
            # Increment for next loop
            power += 1
            continue

        s = '2 ^ %s: (%s, %s): ' % (colour_text('%03d' %  power), colour_text('%10d' %  num), colour_text('%#010x' %  num))
        if result:
            s+= '1 (%s)  ' % colour_text('True', COLOUR_GREEN)
        else:
            s += '0 (%s) ' % colour_text('False', COLOUR_RED)
        if guide and num in guide:
            s += colour_text(guide[num])
        logger.info('  %s' % s.strip())

        # Increment for next loop
        power += 1

def main(args_raw):
    try:
        data = parse_args(args_raw)

        for value in data['values']:
            display(value, **data)

        return 0
    except KeyboardInterrupt:
        return 130

def parse_args(args_raw):

    error = False

    def check_number(value_raw, label = None, check = lambda v: v > 0):
        base = 10
        if value_raw.lower().startswith('0x'):
            base = 16
        try:
            value = int(value_raw, base)
            if check(value):
                return value, True
        except ValueError:
            # Note: Only passing because the fall-through
            #         behavior is to report the raw value as invalid.
            pass

        if label is not None:
            logger.error('Invalid %s: %s' % (label, value_raw))
        return None, False

    def hexit(exit_code):
        logger.error('Usage: %s number [-g guide-json] [-h] [-m mask] [-t]' % os.path.basename(__file__))
        exit(exit_code)

    def load_guide(path):
        if not os.path.isfile(path):
            logger.error('No such file: %s' % path)
            return None, False

        try:
            with open(path, 'r') as f:
                data_raw = load_json(f)
        except JSONDecodeError as e:
            logger.error('Bad JSON content in %s: %s' % (path, e))
            return None, False
        except OSError as e:
            # Using the more general 'OSError' for the sake of Python2.
            logger.error('Bad file permissions on %s: %s' % (path, e))
            return None, False

        data = {}
        for key in data_raw:
            value, good = check_number(key)
            if good:
                data[value] = data_raw[key]

        return data, True

    try:
        args, operands = get_args(args_raw, 'g:hm:t')
    except Exception as e:
        logger.error('Error parsing arguments: %s' % str(e))
        hexit(1)

    good = True
    data = {'values':[]}

    for arg, value_raw in args:
        if arg == '-h':
            hexit(0)
        if arg == '-g':
            data['guide_file'] = value_raw
        elif arg == '-m':
            data['mask'], value_good = check_number(value_raw, 'mask')
            good = good and value_good
        elif arg == '-t':
            data['only_true'] = True

    guide_file = data.get('guide_file')
    if guide_file:
        data['guide'], guide_good = load_guide(guide_file)
        good = good and guide_good

    if not operands:
        logger.error('No values provided.')
        good = False

    for value_raw in operands:
        value, value_good = check_number(value_raw, 'value')
        data['values'].append(value)
        good = good and value_good

    if not good:
        hexit(1)

    return data

if __name__ == '__main__':
    exit(main(sys.argv[1:])) # pragma: no cover
