#!/usr/bin/env python

from __future__ import print_function
import boto3,getopt, json, os, sys, time

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
    _print_message(COLOUR_RED, "Error", message)

def print_notice(message):
    _print_message(COLOUR_BLUE, "Notice", message)

def print_usage(message):
    _print_message(COLOUR_PURPLE, "Usage", message)

def print_warning(message):
    _print_message(COLOUR_YELLOW, "Warning", message)

args = {}

DEFAULT_DELETE = False
TITLE_DELETE = "delete_messages"

TITLE_DIR = "destination directory"

DEFAULT_EXTEND_TIME = 300
TITLE_EXTEND_TIME = "extension time"

TITLE_QUEUE = "queue"

def hexit(code = 0):
    print_usage("%s./%s%s [-d] [-e extension-time] queue destination" % (COLOUR_GREEN, os.path.basename(sys.argv[0]), COLOUR_OFF))
    exit(code)

def process_arguments():

    raw_ints = {}

    try:
        opts, operands = getopt.gnu_getopt(sys.argv[1:], "de:h")
    except getopt.GetoptError as e:
        print_error("Options error: %s" % colour_text(str(e)))
        exit(1)

    for opt,optarg in opts:
        if opt in ('-d'):
            args[TITLE_DELETE] = True
        elif opt in ('-e'):
            raw_ints[TITLE_EXTEND_TIME] = optarg
        elif opt in ('-h'):
            hexit(0)

    try:
        args[TITLE_QUEUE] = operands[0]
        args[TITLE_DIR] = operands[1]
    except:
        pass


    if TITLE_QUEUE not in args:
        print_error("No %s value defined." % colour_text(TITLE_QUEUE))
    elif not re.search('^https://', args[TITLE_QUEUE]):
        print_error("Invalid queue: %s" % colour_text(args[TITLE_QUEUE], COLOUR_GREEN))

    if TITLE_DIR not in args:
        print_error("No %s value defined." % colour_text(TITLE_DIR))
    elif os.path.isdir(args[TITLE_DIR]):
        print_error("Destination directory already exists: %s" % colour_text(args[TITLE_DIR], COLOUR_GREEN))
    else:
        try:
            os.makedirs(args[TITLE_DIR])
        except:
            print_error("Unable to create destination directory: %s" % colour_text(args[TITLE_DIR], COLOUR_GREEN))

    for key in raw_ints:
        try:
            args[key] = int(raw_ints[key])
        except:
            print_error("Invalid %s value: %s" % (colour_text(key), colour_text(raw_ints[key])))

    global error_count
    if error_count:
        exit(1)

process_arguments()

print_notice("Backing up SQS queue: %s" % colour_text(args[TITLE_QUEUE], COLOUR_GREEN))
print_notice("Destination directory: %s" % colour_text(args[TITLE_DIR], COLOUR_GREEN))

if args.get(TITLE_DELETE, DEFAULT_DELETE):
    t = 10
    if sys.stdin.isatty():
        print_notice("Items will be %s out of SQS as they are backed up. You have %s seconds to abort this script." % (
            colour_text("DELETED", COLOUR_RED),
            colour_text(t)
        )

        try:
            time.sleep(t)
        except KeyboardInterrupt:
            print_notice("Aborted backup with delete, interrupted by user.")
            exit(0)
    else:
        print_notice("Items will be deleted out of SQS as they are backed up.")


class QueueSaver:
    def __init__(self):
        self.sqs = boto3.client('sqs')

    def delete_message(self, message):

        if not args.get(TITLE_DELETE, DEFAULT_DELETE):
            return True # Skip deletion

        try:
            self.sqs.delete_message(
                QueueUrl=args[TITLE_QUEUE],
                ReceiptHandle=message['ReceiptHandle']
            )
        except:
            return False
        return True

    def get_message(self):

        response = self.sqs.receive_message(
            QueueUrl=args[TITLE_QUEUE],
            AttributeNames=[
                'SentTimestamp'
            ],
            MaxNumberOfMessages=1,
            MessageAttributeNames=[
                'All'
            ],
            VisibilityTimeout = args.get(TITLE_EXTEND_TIME, DEFAULT_EXTEND_TIME)
        )

        message = None

        if 'Messages' in response and response['Messages']:
            message = response['Messages'][0]

        return message

    def run(self):

        os.chdir(args[TITLE_DIR])

        c = 0
        d = 0
        while True:
            msg = self.get_message()

            if msg is None:
                break

            body = msg["Body"]
            try:
                body = "%s\n" % json.dumps(json.loads(msg["Body"]), sort_keys=True, indent = 4)
            except:
                pass

            self.save_message(body, "%05d.msg" % c)
            c += 1

            if not self.delete_message(msg):
                d += 1

        print_notice("SQS messages backed up: %s" % colour_text(c))
        if d:
            print_notice("Failed to delete some messages: %s" % colour_text(d))

    def save_message(self, body, dest):
        with open(dest, 'w') as f:
            f.write(body)


qs = QueueSaver()
qs.run()
