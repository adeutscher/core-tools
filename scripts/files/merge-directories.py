#!/usr/bin/python

from __future__ import print_function
import getopt, hashlib, os, shutil, re, sys

if sys.version_info[0] < 3:
    input = raw_input

#
# Common Colours and Message Functions
###

def _print_message(header_colour, header_text, message):
    print("%s[%s]: %s" % (colour_text(header_text, header_colour), colour_text(os.path.basename(sys.argv[0]), COLOUR_GREEN), message))

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

error_count = 0
def print_error(message):
    global error_count
    error_count += 1
    _print_message(COLOUR_RED, "Error", message)

def print_exception(e, msg=None):
    # Shorthand wrapper to handle an exception.
    # msg: Used to provide more context.
    sub_msg = ""
    if msg:
        sub_msg = " (%s)" % msg
    print_error("Unexpected %s%s: %s" % (colour_text(type(e).__name__, COLOUR_RED), sub_msg, str(e)))

def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message)

# Script Functions

def hexit(exit_code = 0):
    print('./%s [-h] [-c] src_a src_b dst' % colour_path(os.path.basename(os.path.realpath(sys.argv[0]))))

def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def merge(src, dst):
    print_notice("Merging from source '%s' to destination '%s'" % (colour_path(src), colour_path(dst)))

    for (folder, core, files) in os.walk(src):
        dstDir = folder.replace(src, dst)

        if not os.path.exists(dstDir):
            os.makedirs(dstDir, 0o700)

        for f in files:
            srcPath = '%s/%s' % (folder, f)
            dstPath = '%s/%s' % (dstDir, f)

            if(os.path.isfile(dstPath)):
                if md5(srcPath) != md5(dstPath):
                    print_notice('%s: "%s" -> "%s"' % (colour_text('Conflict', COLOUR_RED), colour_path(srcPath), colour_path(dstPath)))
                    soloName, ext = os.path.splitext(dstPath)
                    dstPath = '%s.from-%s%s' % (soloName, os.path.basename(src), ext)
                else:
                    # Continue on. Identical file.
                    continue

            print_notice('"%s" -> "%s"' % (colour_path(srcPath), colour_path(dstPath)))
            shutil.copy2(srcPath, dstPath)

# Script Operations

compile_mode = False

try:
    opts, operands = getopt.gnu_getopt(sys.argv[1:], 'ch')
except Exception as e:
    print_exception(e)

for opt,value in opts:
    if opt == '-c':
        compile_mode = True
    elif opt == '-h':
        hexit()

min_args = 2
wording = "merging"

if compile_mode:
    min_args = 3
    wording = "compile-mode merging"

if len(operands) < min_args:
    print_error("Insufficient arguments for %s." % wording)
    exit(1)

dst = os.path.abspath(operands[-1])
paths = []

# Verify sources.
for i in range(len(operands)-1):
    src = operands[i]
    if not os.path.isdir(src):
        print_error('Source "%s" does not exist.' % colour_path(operands[i]))
    else:
        paths.append(os.path.abspath(src))

if compile_mode:
    # In compile mode, the destination should not already exist.
    if os.path.isdir(dst):
        print_error("Destination '%s' already exists." % colour_path(dst))
elif not os.path.isdir(dst):
    # In regular mode, the destination must exist.
    print_error("Destination '%s' does not exist." % colour_path(dst))

if error_count:
    exit(1)

# Summarize:

noun = 'directory'
if len(paths) > 1:
    noun = 'directories'

print_notice('Source %s:' % noun)

for src in paths:
    print_notice('  * %s' % colour_path(src))

print_notice('Destination directory: %s' % colour_path(dst))

if sys.stdout.isatty():
    # With such a massive change pending, could
    try:
        input('< Press ENTER to continue, Ctrl-C to cancel >')
    except KeyboardInterrupt:
        print_notice('\nCancelled')
        exit(130)

if compile_mode:
    # Copy the first directory directly to the destination.
    shutil.copytree(paths[0], dst)

for src in paths:
    merge(src, dst)
