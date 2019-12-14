#!/usr/bin/env python

from __future__ import print_function
import csv, getopt, json, os, sys

format_name = "YAML"

#
# Common Colours and Message Functions
###

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

def enable_colours(force = False):
    global COLOUR_PURPLE
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_YELLOW
    global COLOUR_BLUE
    global COLOUR_BOLD
    global COLOUR_OFF
    if force or sys.stdout.isatty():
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

error_count = 0
def print_error(message):
    global error_count
    error_count += 1
    _print_message(COLOUR_RED, "Error", message, True)

def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message, True)

def print_usage(message):
    _print_message(COLOUR_PURPLE, "Usage", message, True)

def print_warning(message):
    _print_message(COLOUR_YELLOW, "Warning", message, True)

#
# Script Functions
###

def convert_list_to_csv(l):

    if isinstance(l, dict):
        print_warning("Content is a %s object and not a list. Converting as a single-entry CSV." % format_name)
        l = [l]
    elif not isinstance(l, list):
        print_error("Must provide a list of objects.")
        return

    a = []

    list_count = 0
    for item in l:
        list_count += 1
        if not isinstance(item, dict):
            print_error("Row %s is not a %s object." % (colour_text("#%d" % list_count), format_name))
            continue

        a.append(flattenjson(item, '__'))

    if not a:
        # No rows to print, immediately return.
        print_error("No valid CSV rows detected.")
        return

    columns = [ x for row in a for x in row.keys() ]
    columns = sorted( list( set( columns ) ) )

    csv_w = csv.writer( sys.stdout )
    csv_w.writerow( columns )
    output_count = 0

    for i_r in a:
        output_count += 1

        try:
            csv_w.writerow( map( lambda x: i_r.get( x, "" ), columns ) )
        except Exception as e:
            print_error("Problem (item %s): %s" % (colour_text("#%d" % output_count), e))

def flattenjson( b, delim ):
    val = {}

    for i in b.keys():
        if isinstance( b[i], dict ):
            get = flattenjson( b[i], delim )
            for j in get.keys():
                val[ i + delim + j ] = get[j]
        else:
            val[i] = b[i]

    return val

def get_content(file_handle, title):
    try:
        return yaml.load(file_handle.read())
    except yaml.error.MarkedYAMLError as e:
        # Conveniently, Python's pyyaml module gives a more informative error printout than the JSON module.
        if title == "standard input":
            print_error("Content of standard input is not in readable %s format: %s (line %d, column %d)" % (format_name, e.problem, e.problem_mark.line + 1, e.problem_mark.column + 1))
        else:
            print_error("Content of input (%s) is not in readable %s format: %s (line %d, column %d)" % (colour_text(title, COLOUR_GREEN), format_name, e.problem, e.problem_mark.line + 1, e.problem_mark.column + 1))
        return None

def main():
    file_handle = False
    if len(sys.argv) >= 2:
        source_file = sys.argv[1]
        if source_file == "-":
            file_handle = sys.stdin
            print_notice("Reading %s content from standard input." % format_name)
        elif not os.path.isfile(source_file):
            print_error("%s file does not exist: %s" % (format_name, colour_text(source_file, COLOUR_GREEN)))
        elif not os.access(source_file, os.R_OK):
            print_error("%s file could not be read: %s" % (format_name, colour_text(source_file, COLOUR_GREEN)))
    else:
        print_error("No %s file path provided." % format_name)

    # Quit if there was an argument error.
    global error_count
    if error_count:
        hexit(1)

    # Get our content
    content = None
    try:
        if file_handle:
            # File handle was already set (stdin)
            content = get_content(file_handle, "standard input")
        else:
            with open(source_file) as file_handle:
                content = get_content(file_handle, source_file)
    except Exception:
        # Unexpected problem
        print_error("Problem with getting %s data." % format_name)

    # Quit if there was a loading error.
    if error_count or not content:
        exit(1)

    convert_list_to_csv(content)

    # Quit with non-zero if there was a problem with list conversion
    if error_count:
        exit(1)

def hexit(code = 0):
    print_usage("%s %s-file" % (colour_text("./%s" % os.path.basename(sys.argv[0]), COLOUR_GREEN), format_name.lower()))
    exit(code)

try:
    import yaml
except ImportError:
    print_error("YAML module for Python is not installed.")

if __name__ == "__main__":
    main()
