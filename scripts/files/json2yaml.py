#!/usr/bin/env python

from __future__ import print_function
import json, os, sys

# Setting format title as a variable to make it to
#   to copy content between yaml2json.py and json2yaml.py
# The only thing other than this that should need to be adjusted
#   is the convert() function.
format_name = "JSON"

def _print_message(header_colour, header_text, message, stderr=False):
    f=sys.stdout
    if stderr:
        f=sys.stderr
    print("%s[%s]: %s" % (colour_text(header_text, header_colour), colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN), message), file=f)

def colour_text(text, colour = None):
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return "%s%s%s" % (colour, text, COLOUR_OFF)

def convert(file_handle, title):
    try:
        src_body = json.loads(file_handle.read())
    except Exception as e:
        # Unfortunately, Python's JSON module doesn't give a more informative error printout.
        if title == "standard input":
            print_error("Content of standard input is not in readable %s format: %s" % (format_name, e))
        else:
            print_error("Content of input (%s) is not in readable %s format: %s" % (colour_text(title, COLOUR_GREEN), format_name, e))
        return
    dst_body = yaml.safe_dump(src_body, default_flow_style=False, allow_unicode = True, indent=2)
    print("---\n")
    print(dst_body)

def enable_colours(force = False):
    global COLOUR_PURPLE
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_BLUE
    global COLOUR_BOLD
    global COLOUR_OFF
    if force or sys.stderr.isatty():
        # Colours for standard output.
        COLOUR_PURPLE = '\033[1;35m'
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_YELLOW = '\033[1;93m'
        COLOUR_BLUE = '\033[1;94m'
        COLOUR_BOLD = '\033[1m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_PURPLE = ''
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_YELLOW = ''
        COLOUR_BLUE = ''
        COLOUR_BOLD = ''
        COLOUR_OFF = ''
enable_colours()

def hexit(code = 0):
    print_usage("%s %s-file" % (colour_text("./%s" % os.path.basename(sys.argv[0]), COLOUR_GREEN), format_name.lower()))
    exit(code)

#
# Common Message Functions
###

error_count = 0
def print_error(message):
    global error_count
    error_count += 1
    _print_message(COLOUR_RED, "Error", message, True)

def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message, True)

def print_usage(message):
    _print_message(COLOUR_PURPLE, "Usage", message, True)

#
# Script operation
###

try:
    import yaml
except ImportError:
    print_error("YAML module for Python is not installed.")

file_handle = False
if len(sys.argv) >= 2:
    source_file = sys.argv[1]
    if source_file == "-":
        file_handle = sys.stdin
        print_notice("Reading %s content from standard input." % format_name)
    elif not os.path.isfile(source_file):
        print_error("%s file does not exist: %s" % (format_name, colour_text(source_file, COLOUR_GREEN)))
    elif not os.access(source_file, os.R_OK):
        print_error("%s file could not be read: %s%s%s" % (format_name, colour_text(source_file, COLOUR_GREEN)))
else:
    print_error("No %s file path provided." % format_name)

if error_count:
    hexit(1)

if file_handle:
    # File handle was already set (stdin)
    convert(file_handle, "standard input")
else:
    with open(source_file) as file_handle:
        convert(file_handle, source_file)

if error_count:
    exit(1)
