#!/usr/bin/env python

import boto3, getopt, json, os, sys

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

args = {}

TITLE_DIR = "source directory"

DEFAULT_JSON = True
TITLE_JSON = "check JSON format"

TITLE_QUEUE = "queue"

def hexit(code = 0):
    print_usage("%s./%s%s [-a] dest-queue source-dir" % (COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF))
    exit(code)

def process_arguments():

    raw_ints = {}

    try:
        opts, operands = getopt.gnu_getopt(sys.argv[1:], "ah")
    except getopt.GetoptError as e:
        print_error("Options error: %s" % colour_text(COLOUR_BOLD, str(e)))
        exit(1)

    for opt,optarg in opts:
        if opt in ('-a'):
            args[TITLE_JSON] = False
        elif opt in ('-h'):
            hexit(0)

    try:
        args[TITLE_QUEUE] = operands[0]
        args[TITLE_DIR] = operands[1]
    except:
        pass


    if TITLE_QUEUE not in args:
        print_error("No %s value defined." % colour_text(COLOUR_BOLD, TITLE_QUEUE))

    if TITLE_DIR not in args:
        print_error("No %s value defined." % colour_text(COLOUR_BOLD, TITLE_DIR))
    elif not os.path.isdir(args[TITLE_DIR]):
        print_error("Source directory does not exist: %s" % colour_text(COLOUR_GREEN, args[TITLE_DIR]))

    global error_count
    if error_count:
        exit(1)

process_arguments()

print_notice("Source directory: %s" % colour_text(COLOUR_GREEN, args[TITLE_DIR]))
print_notice("Loading backups to SQS queue: %s" % colour_text(COLOUR_GREEN, args[TITLE_QUEUE]))
if args.get(TITLE_JSON, DEFAULT_JSON):
    print_notice("All submitted files must be in JSON format.")
else:
    print_notice("Files will not be checked for a valid JSON format.")

class QueueLoader:
    def __init__(self):
        self.sqs = boto3.client('sqs')
        self.queue = boto3.resource('sqs').Queue(args[TITLE_QUEUE])

    def process_files(self, dry_run = False):

        c = 0
        e = 0
        for (folder, core, files) in os.walk(args[TITLE_DIR]):
            for file_name in files:

                path = os.path.realpath("%s/%s" % (folder, file_name))

                with open(path, 'r') as f:
                    contents = f.read() # Get file contents to send/validate.

                if args.get(TITLE_JSON, DEFAULT_JSON):
                    try :
                        json_contents = json.loads(contents)
                    except:
                        print_error("File is not in proper JSON format: %s" % colour_text(COLOUR_GREEN, path))
                        e += 1
                    if not dry_run:
                        contents = json.dumps(json_contents) # Re-serialize without formatting.

                if not dry_run:
                    # Not a dry run, actually try to send the file into the queue.
                    self.queue.send_message(MessageBody=contents)
                c += 1
            break # Break after first directory, do not recurse.

        global error_count

        if e or error_count:
            print_error("Files not in proper format: %s" % colour_text(COLOUR_BOLD, e))
            print_error("Aborting upload.")
            exit(1)

        return c

    def run(self):

        if args.get(TITLE_JSON, DEFAULT_JSON):
            self.process_files(True)

        c = self.process_files()

        print_notice("SQS messages loaded up: %s" % colour_text(COLOUR_BOLD, c))

qs = QueueLoader()
qs.run()
