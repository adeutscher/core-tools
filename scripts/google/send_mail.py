#!/usr/bin/python

####################################################
# Script to send e-mail via GMail                  #
#                                                  #
# To install APIs:                                 #
#   pip install --upgrade google-api-python-client #
####################################################

# General modules
from __future__ import print_function
import base64, common, mimetypes, os, platform, random, re, string, sys, uuid
common.local_files.append(os.path.realpath(__file__))

# Mail modules
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
import email.encoders as Encoders

def load_attachment(file_path):
    content_type, encoding = mimetypes.guess_type(file_path)

    if content_type is None or encoding is not None:
        content_type = 'application/octet-stream'

    main_type, sub_type = content_type.split('/', 1)
    with open(file_path, 'rb') as fp:
        msg = MIMEBase(main_type, sub_type)
        Encoders.encode_base64(msg)
        msg.set_payload(fp.read())

    msg.add_header('Content-Disposition', 'attachment', filename=os.path.basename(file_path))
    msg.set_param("name", os.path.basename(file_path))
    # Imitate the content ID format used by Google. Probably unnecessary to make it this similar...
    content_id = "f_%s" % ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(9))
    msg.add_header("X-Attachment-Id", content_id)
    msg.add_header("Content-ID", "<%s>" % content_id)

    return msg

# Initialize arguments

TITLE_TO = "To Address"
TITLE_CC = "CC Address"
TITLE_BCC = "BCC Address"
TITLE_FROM = "From title"
TITLE_RECIPIENTS = "recipients"
TITLE_ATTACHMENT = "attachment"
TITLE_MESSAGE = "message"
TITLE_SUBJECT = "subject"
TITLE_HTML_FORMAT = "HTML format"

def validate_attachments(self):
    e = []
    for a in self[TITLE_ATTACHMENT]:
        if not os.path.isfile(a):
            e.append("No such attachment file: %s" % common.colour_text(a, common.COLOUR_GREEN))
    return e

def validate_email(self):

    e = []
    recipients = 0

    for t in [TITLE_TO, TITLE_CC, TITLE_BCC]:
        for email in self[t]:
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
                e.append("Invalid %s: %s" % (t, email))
            else:
                recipients += 1

    if not recipients:
        e.append("No valid recipients specified...")

    return e

common.args.add_validator(validate_attachments)
common.args.add_validator(validate_email)

for f,t in [("t", TITLE_TO), ("c", TITLE_CC), ("b", TITLE_BCC)]:
    common.args.add_opt(common.OPT_TYPE_SHORT, f, t, "Add an %s to send the e-mail message to." % t, multiple = True)
common.args.add_opt(common.OPT_TYPE_SHORT, "f", TITLE_FROM, "Set a 'From' title.", default = "Message from %s" % platform.node())
common.args.add_opt(common.OPT_TYPE_SHORT, "a", TITLE_ATTACHMENT, "Attach a file to your e-mail message.", multiple = True)
common.args.add_opt(common.OPT_TYPE_SHORT, "m", TITLE_MESSAGE, "Set e-mail message body.", default = "No Message")
common.args.add_opt(common.OPT_TYPE_SHORT, "s", TITLE_SUBJECT, "Set e-mail message subject.", default = "No Subject")
common.args.add_opt(common.OPT_TYPE_LONG_FLAG, "html", TITLE_HTML_FORMAT, "Enable HTML mode. Message content will be expected to be HTML-formatted.")

def encode_base64(content):
    if sys.version_info[0] >= 3 and type(content) is str:
        return str(base64.urlsafe_b64encode(bytes(content, 'utf-8')), 'utf-8')

    # Python 2
    return base64.urlsafe_b64encode(content)

def main():

    common.process()
    service = common.get_service('gmail')

    msg = MIMEMultipart('mixed')
    msg['Subject'] = common.args[TITLE_SUBJECT]
    msg['From'] = common.args[TITLE_FROM]
    for i, t in [('To', TITLE_TO), ('CC', TITLE_CC), ('BCC', TITLE_BCC)]:
        if common.args[t]:
            msg[i] = str.join(",", common.args[t])

    content = common.args[TITLE_MESSAGE]
    if content == "-":
        content = sys.stdin.read() # Read content from standard input.

    encoding_type = "plain"
    if common.args[TITLE_HTML_FORMAT]:
        encoding_type = "html"

    msg.attach(MIMEText(content, encoding_type))

    for attachment in common.args[TITLE_ATTACHMENT]:
        common.print_notice("Processing attachment: %s" % common.colour_text(attachment, common.COLOUR_GREEN))
        try:
            msg.attach(load_attachment(attachment))
        except Exception as e:
            common.print_exception(e, "loading attachment")

    if not common.error_count:
        # Prep and send.
        try:
            message = (service.users().messages().send(userId="me", body={'raw': encode_base64(msg.as_string())}).execute())
        except Exception as e:
            common.print_error("Unable to send mail: %s" % str(e))
    else:
        common.print_error("Not sending mail due to at least one argument error (%d in total)." % common.error_count)
    if common.error_count:
        return 1
    return 0

if __name__ == '__main__':
    exit(main())
