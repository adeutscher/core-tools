#!/usr/bin/env python

import csv, getopt, json, os, sys

format_name = "JSON"

#
# Common Colours and Message Functions
###

def __print_message(colour, header, message):
    print "%s[%s]: %s" % (colour_text(colour, header), colour_text(COLOUR_GREEN, os.path.basename(sys.argv[0])), message)

def colour_text(colour, text):
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
    print >> sys.stderr, "%s[%s]: %s" % (colour_text(COLOUR_RED, "Error"), colour_text(COLOUR_GREEN, os.path.basename(sys.argv[0])), message)

def print_notice(message):
    print >> sys.stderr, "%s[%s]: %s" % (colour_text(COLOUR_BLUE, "Notice"), colour_text(COLOUR_GREEN, os.path.basename(sys.argv[0])), message)

def print_usage(message):
    print >> sys.stderr, "%s[%s]: %s" % (colour_text(COLOUR_PURPLE, "Usage"), colour_text(COLOUR_GREEN, os.path.basename(sys.argv[0])), message)

def print_warning(message):
    print >> sys.stderr, "%s[%s]: %s" % (colour_text(COLOUR_YELLOW, "Warning"), colour_text(COLOUR_GREEN, os.path.basename(sys.argv[0])), message)

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
            print_error("Row %s is not a %s object." % (colour_text(COLOUR_BOLD, "#%d" % list_count), format_name))
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
            print_error("Problem (item %s): %s" % (colour_text(COLOUR_BOLD, "#%d" % output_count), e))

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
        return json.loads(file_handle.read())
    except Exception as e:
        # Unfortunately, Python's JSON module doesn't give a more informative error printout.
        if title == "standard input":
            print_error("Content of standard input is not in readable %s format: %s" % (format_name, e))
        else:
            print_error("Content of input (%s) is not in readable %s format: %s" % (colour_text(COLOUR_GREEN, title), format_name, e))
        return None

def main():
    file_handle = False
    if len(sys.argv) >= 2:
        source_file = sys.argv[1]
        if source_file == "-":
            file_handle = sys.stdin
            print_notice("Reading %s content from standard input." % format_name)
        elif not os.path.isfile(source_file):
            print_error("%s file does not exist: %s" % (format_name, colour_text(COLOUR_GREEN, source_file)))
        elif not os.access(source_file, os.R_OK):
            print_error("%s file could not be read: %s" % (format_name, colour_text(COLOUR_GREEN, source_file)))
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
    print_usage("%s %s-file" % (colour_text(COLOUR_GREEN, "./%s" % os.path.basename(sys.argv[0])), format_name.lower()))
    exit(code)

if __name__ == "__main__":
    main()
