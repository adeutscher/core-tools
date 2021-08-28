#!/usr/bin/env python

from __future__ import print_function
import argparse, hashlib, logging, os, shutil, re, sys

def build_logger(label, err = None, out = None):
    obj = logging.getLogger('merge_directories')
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
logger = build_logger('merge_directories')

#
# Common Colours and Message Functions
###

def colour_path(text):
    home = os.environ.get('HOME')
    if home:
        text = text.replace(home, '~')
    return colour_text('%s' % text, COLOUR_GREEN)

def colour_text(text, colour = None):
    if not colour:
        colour = COLOUR_BOLD
    # A useful shorthand for applying a colour to a string.
    return "%s%s%s" % (colour, text, COLOUR_OFF)

def enable_colours(force = False):
    global COLOUR_RED
    global COLOUR_GREEN
    global COLOUR_BLUE
    global COLOUR_BOLD
    global COLOUR_OFF
    if force or sys.stdout.isatty():
        # Colours for standard output.
        COLOUR_RED = '\033[1;91m'
        COLOUR_GREEN = '\033[1;92m'
        COLOUR_BLUE = '\033[1;94m'
        COLOUR_BOLD = '\033[1m'
        COLOUR_OFF = '\033[0m'
    else:
        # Set to blank values if not to standard output.
        COLOUR_RED = ''
        COLOUR_GREEN = ''
        COLOUR_BLUE = ''
        COLOUR_BOLD = ''
        COLOUR_OFF = ''
enable_colours()

# Script Functions

def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def merge(src, dst):
    logger.info("Merging from source '%s' to destination '%s'" % (colour_path(src), colour_path(dst)))

    for (folder, core, files) in os.walk(src):
        dstDir = folder.replace(src, dst)

        if not os.path.exists(dstDir):
            os.makedirs(dstDir, 0o700)
        for f in files:

            srcPath = os.path.join(folder, f)
            dstPath = os.path.join(dstDir, f)

            do_copy = True

            if(os.path.isfile(dstPath)):
                if md5(srcPath) != md5(dstPath):

                    soloName, ext = os.path.splitext(dstPath)
                    i = 0
                    while os.path.exists(dstPath):
                        i += 1
                        dstPath = '%s.%d%s' % (soloName, i, ext)

                    logger.warning('%s: "%s" -> "%s"' % (colour_text('Conflict', COLOUR_RED), colour_path(srcPath), colour_path(dstPath)))
                else:
                    # Continue on. Identical file.
                    do_copy = False

            if do_copy:
                # Note: Using do_copy instead of just saying 'continue' is because of a struggle with test coverage module.
                logger.info('"%s" -> "%s"' % (colour_path(srcPath), colour_path(dstPath)))
                shutil.copy2(srcPath, dstPath)

# Script Operations

def process_args(raw_args):
    parser = argparse.ArgumentParser(description='Encryption/Decryption wrapper')
    parser.add_argument('-c', dest='compile', action='store_true', help='Compile mode. Compile 2+ source directories into one path that does not yet exist.')
    parser.add_argument('-i', action='append', default=[], dest='input', help='Input directory')
    parser.add_argument('-o', dest='output', help='Output directory')

    args = parser.parse_args(raw_args)
    good = True

    if args.compile:
        min_inputs = 2
        wording = "compile-mode merging"
    else:
        min_inputs = 1
        wording = "merging"

    if len(args.input) < min_inputs:
        logger.error('Insufficient input directories for %s.' % wording)
        good = False
    # Verify sources.
    for src in [s for s in args.input if not os.path.isdir(s)]:
        logger.error('Source "%s" does not exist.' % colour_path(src))
        good = False

    if not args.output:
        logger.error("No output directory specified.")
        good = False
    elif args.compile and os.path.isdir(args.output):
        # In compile mode, the destination should not already exist.
        logger.error("Output directory '%s' should not already exist." % colour_path(args.output))
        good = False
    elif not args.compile and not os.path.isdir(args.output):
        # In regular mode, the destination must exist.
        logger.error("Output directory '%s' does not exist." % colour_path(args.output))
        good = False

    return args, good

def run(raw_args, enable_safety = True):

    args, args_good = process_args(raw_args[1:])

    if not args_good:
        return 1

    # Summarize
    ##

    # Announce input
    noun = 'directory'
    if len(args.input) > 1:
        noun = 'directories'
    logger.info('Source %s:' % noun)
    for src in args.input:
        logger.info('  * %s' % colour_path(src))
    # Announce output
    logger.info('Destination directory: %s' % colour_path(args.output))

    if enable_safety and sys.stdout.isatty():
        # With such a massive change pending, wait for user input for safety
        try:
            if sys.version_info[0] < 3:
                input = raw_input
            input('< Press ENTER to continue, Ctrl-C to cancel >')
        except KeyboardInterrupt:
            logger.info('\nCancelled')
            return 130

    paths = args.input.copy()
    if args.compile:
        # Copy the first directory directly to the destination.
        shutil.copytree(paths.pop(0), args.output)

    for src in paths:
        merge(src, args.output)

    return 0

if __name__ == '__main__':
    try:
        exit(run(sys.argv))
    except KeyboardInterrupt:
        exit(130)

