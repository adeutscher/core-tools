#!/usr/bin/python

# Compares two files, and reports on the number of differences between them.
# I originally made this script to troubleshoot a from-scratch file transfer program.
#
# Output:
#  - First difference, if a non-matching block was found.
#  - If one file was smaller than the other, a full match is impossible.
#      However, the files could still be two sides of a transfer that was simply interrupted.
#      Reports on how match statistics as a percentage of the smaller file.
#  - Reports match statistics as a percentage of the larger file.

import getopt, os, sys

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
    __print_message(COLOUR_RED, "Error", message)

def print_notice(message):
    __print_message(COLOUR_BLUE, "Notice", message)

def print_usage(message):
    __print_message(COLOUR_PURPLE, "Usage", message)

def print_warning(message):
    __print_message(COLOUR_YELLOW, "Warning", message)

def hexit(exit_code = 0):
    print_usage("Usage: ./compare-files.py file-a file-b [-s block-size]")
    exit(exit_code)

def main(argv):

    block_size = 1024
    file_a = None
    file_b = None

    raw_size = None

    # Tell the user each error that they've made at the same time.
    errors = []

    try:
        # Note: Python will not throw a fit if you call for an invalid slice (will simply be empty).
        opts, operands = getopt.getopt(argv[1:],"hs:")
    except getopt.GetoptError:
        errors.append("Error parsing arguments")
    for opt, arg in opts:
        if opt == "-h":
            hexit(0)
        elif opt == "-s":
            raw_size = arg
    try:
        file_a = operands[0]
        if not os.path.isfile(file_a):
            errors.append("File A does not exist: %s" % colour_text(COLOUR_GREEN, file_a))

        file_b = operands[1]
        if not os.path.isfile(file_b):
            errors.append("File B does not exist: %s" % colour_text(COLOUR_GREEN, file_b))
    except IndexError:
        errors.append("Must provide two files for comparison (%s provided)." % colour_text(COLOUR_BOLD, len(operands)))

    if len(operands) > 2:
        print_warning("Only the first two paths provided will be compared (%s provided)." % colour_text(COLOUR_BOLD, len(operands)))

    if raw_size:
        try:
            block_size = int(raw_size)
        except ValueError:
            errors.append("Invalid block size: %s" % colour_text(COLOUR_BOLD, block_size))

    if block_size <= 0:
        errors.append("Block size must be greater than 0 (was set to %s)." % colour_text(COLOUR_BOLD, block_size))

    if len(errors):
        for e in errors:
            print_error(e)
        hexit(1)

    print_notice("Comparing %s to %s, %s bytes at a time." % (colour_text(COLOUR_GREEN, file_a), colour_text(COLOUR_GREEN, file_b), colour_text(COLOUR_BOLD, block_size)))
    compare(file_a, file_b, block_size)

def compare(file_a, file_b, block_size):
    size_a = os.path.getsize(file_a)
    size_b = os.path.getsize(file_b)
    a = open(file_a, 'r')
    b = open(file_b, 'r')

    marker = 0
    first = None
    iterations = 0

    size_max = max(size_a, size_b)
    size_min = min(size_a, size_b)
    match = 0

    while marker < size_a and marker < size_b:
        a_contents = a.read(block_size)
        b_contents = b.read(block_size)

        if a_contents == b_contents:
            match += 1
        else:

            if first is None:
                first = (marker, iterations)
        marker += block_size
        iterations += 1

    match = min(match, size_max)

    if first is not None:
        print_notice("First non-matching block starting at %d, iteration #%d" % first)
    if size_min != size_max:
        print_notice("Reached the end of the smaller file (%d iterations)" % iterations)
        # Print statistics in terms of the smaller file.
        # This helps us if a file has been cut off mid-transfer.
        print_notice("%d / %d identical blocks within smaller file: %.04f%% match" % (min(match, size_min), size_min, float(match)/float(size_min)*100))
        print_notice("Reminder: High match percentage within smaller file could be from\n\t\tthe smaller file being indivisible with block size.")
    print_notice("%d / %d identical blocks: %.04f%% match" % (match, iterations, float(match)/float(iterations)*100))
    a.close()
    b.close()

if __name__ == "__main__":
    main(sys.argv)
