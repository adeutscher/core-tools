#!/usr/bin/python

# General modules
from __future__ import print_function
import base64, common, getopt, httplib2, json, os, platform, re, sys

####################################################
# List calendar events in a format that can be     #
#   used by conky task display.                    #
#                                                  #
# To install APIs:                                 #
#   pip install --upgrade google-api-python-client #
####################################################

from apiclient import discovery

# Mail modules
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.MIMEBase import MIMEBase
from email import Encoders

def loadAttachment(filePath):
    f = file(filePath)
    attachment = MIMEBase('application',"octet-stream")
    attachment.set_payload(f.read())
    attachment.add_header('Content-Disposition', 'attachment; filename="{0}"'.format(os.path.basename(filePath)))
    Encoders.encode_base64(attachment)
    return attachment
    content_type, encoding = mimetypes.guess_type(file)

    if content_type is None or encoding is not None:
        content_type = 'application/octet-stream'
    main_type, sub_type = content_type.split('/', 1)
    if main_type == 'text':
        fp = open(file, 'rb')
        msg = MIMEText(fp.read(), _subtype=sub_type)
        fp.close()
    elif main_type == 'image':
        fp = open(file, 'rb')
        msg = MIMEImage(fp.read(), _subtype=sub_type)
        fp.close()
    elif main_type == 'audio':
        fp = open(filePath, 'rb')
        msg = MIMEAudio(fp.read(), _subtype=sub_type)
        fp.close()
    else:
        fp = open(filePath, 'rb')
        msg = MIMEBase(main_type, sub_type)
        msg.set_payload(fp.read())
        fp.close()

    filename = os.path.basename(filePath)
    msg.add_header('Content-Disposition', 'attachment', filename=filename)
    return msg

def validEmail(mail):
    return re.match(r'^[^@]+@[^@]+\.[^@]+$', mail)

def usage():
    print("Usage: ./send-mail.py -t toAddress [(-s|--subject) subject] [(-m|--message) message] [(-f|--from) fromName] [(-c|--cc) ccAddress] [(-b|--bcc) bccAddress] [(-a|--attach|--attachment) attachmentPath] [-H]")

def main():

    unconfirmedAttachments = []
    attachments = []
    toList = []
    ccList = []
    bccList = []
    toList = []
    tag = None

    fromName = platform.node()
    # Default subject
    subject = "Message from %s" % fromName
    # Default content (empty)
    content = ""
    try:
        # Note: Python will not throw a fit if you call for an invalid slice (will simply be empty).
        opts, args = getopt.gnu_getopt(sys.argv[1:],"A:a:c:b:f:hHm:s:t:",["attach=", "attachment=", "bcc=", "cc=", "from=", "help", "html", "message=", "subject=", "to="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    if len(args) > 0:
        content = args[0]

    encoding_type = 'plain'

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-A"):
            tag = arg
        elif opt in ("-a", "--attach"):
            unconfirmedAttachments.append(arg)
        elif opt in ("-b", "--bcc"):
            if(validEmail(arg)):
                bccList.append(arg)
            else:
                common.print_error("Invalid BCC address: %s" % arg)
        elif opt in ("-c", "--cc"):
            if(validEmail(arg)):
                ccList.append(arg)
            else:
                common.print_error("Invalid CC address: %s" % arg)
        elif opt in ("-f", "--from"):
            fromName = arg
        elif opt in ("-H", "--html"):
            encoding_type = 'html'
        elif opt in ("-m", "--message"):
            if arg == "-":
                content = ''
                # Do read-y stuff
                while True:
                    dataBlock = sys.stdin.read(1024)
                    if len(dataBlock) == 0:
                        # Done
                        break
                    else:
                        content = content + dataBlock
            else:
                content = arg
        elif opt in ("-s", "--subject"):
            subject = arg
        elif opt in ("-t", "--to"):
            if(validEmail(arg)):
                toList.append(arg)
            else:
                common.print_error("Invalid target address: %s" % arg)

    # Compile recipient list.
    rcpList = toList[:]
    rcpList.extend([i for i in ccList if i not in rcpList])
    rcpList.extend([i for i in bccList if i not in rcpList])

    # Confirm that each attachment exists.
    for f in unconfirmedAttachments:
        if not os.path.isfile(f):
            common.print_error("File '%s' not found..." % f)
        else:
            attachments.append(f);

    if len(rcpList) == 0:
        common.print_error("No recipients specified...")
    if len(unconfirmedAttachments) != len(attachments):
        common.print_error("Not all attachments were found...")

    if common.error_count:
        exit(2)

    # Get credentials
    credentials = common.get_credentials(tag)
    if not credentials or common.error_count:
        exit(3)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)

    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From'] = fromName
    if len(toList):
        msg['To'] = str.join(",",toList)
    if len(ccList):
        msg['CC'] = str.join(",",ccList)
    if len(bccList):
        msg['BCC'] = str.join(",",bccList)

    for attachment in attachments:
        common.print_notice("Processing attachment: %s" % common.colour_text(common.COLOUR_GREEN, attachment))
        msg.attach(loadAttachment(attachment))

    body = MIMEText(content, encoding_type)
    msg.attach(body)

    if not common.error_count:
        # Prep and send.
        try:
            message = (service.users().messages().send(userId="me", body={'raw': base64.urlsafe_b64encode(msg.as_string())}).execute())
        except Exception as e:
            common.print_error("Unable to send mail: %s" % e)
    else:
        common.print_error("Not sending mail due to at least one argument error (%d in total)." % common.error_count)

if __name__ == '__main__':
    main()
