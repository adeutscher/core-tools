#!/usr/bin/python

# Compares two files, and reports on the number of differences between them.
# Output:
#  - First difference, if a non-matching block was found.
#  - If one file was smaller than the other, a full match is impossible.
#      But are these files two sides of a transfer that was just interrupted?
#      Reports on how match statistics as a percentage of the smaller file.
#  - Reports match statistics as a percentage of larger file.

import getopt, os, sys

def usage():
    print "Usage: ./compare-files.py -a file-a -b file [-s block-size]"

def main(argv):

    block_size = 1024
    file_a = None
    file_b = None

    # Tell the user each error that they've made at the same time.
    errors = []
    try:
        # Note: Python will not throw a fit if you call for an invalid slice (will simply be empty).
        opts, args = getopt.getopt(argv[1:],"a:b:hs:")
    except getopt.GetoptError:
        errors.append("Error parsing arguments")
    for opt, arg in opts:
        if opt == '-a':
            file_a = arg
        if opt == "-b":
            file_b = arg
        elif opt == "-s":
            block_size = int(arg)

    if block_size <= 0:
        errors.append("Block size must be greater than 0 (was set to %d)." % block_size)
    if file_a is None:
        errors.append("File A not set (-a file-a)")
    elif not os.path.isfile(file_a):
        errors.append("File A does not exist: %s" % file_a)
    if file_b is None:
        errors.append("File B not set (-b file-b)")
    elif not os.path.isfile(file_b):
         errors.append("File B does not exist: %s" % file_b)

    if len(errors):
        for e in errors:
            print e
        usage()
        exit(1)

    print "Comparing %s to %s, %d bytes at a time." % (file_a, file_b, block_size)
    compare(file_a, file_b, block_size)

def compare(file_a, file_b, block_size):
    size_a = os.path.getsize(file_a)
    size_b = os.path.getsize(file_b)
    a = open(file_a, 'r')
    b = open(file_b, 'r')

    marker = 0
    first = None
    iteration = 0

    size_max = max(size_a, size_b)
    size_min = min(size_a, size_b)
    match = 0

    while marker < size_a and marker < size_b:
        a_contents = a.read(block_size)
        b_contents = b.read(block_size)

        if a_contents == b_contents:
            match = match + block_size
        else:
            if first is None:
                first = (marker, iteration)
        marker = marker + block_size
        iteration = iteration + 1

    match = min(match, size_max)

    if first is not None:
        print "First non-matching block starting at %d, iteration #%d" % first
    if size_min != size_max:
        print "Reached the end of the smaller file (%d iterations)" % iteration
        # Print statistics in terms of the smaller file.
        # This helps us if a file has been cut off mid-transfer.
        print "%d / %d identical blocks within smaller file: %.04f%% match" % (min(match, size_min), size_min, float(match)/float(size_min)*100)
        print "Reminder: High match percentage within smaller file could be from\n\t\tthe smaller file being indivisible with block size."
    print "%d / %d identical blocks: %.04f%% match" % (match, size_max, float(match)/float(size_max)*100)
    a.close()
    b.close()

if __name__ == "__main__":
    main(sys.argv)
