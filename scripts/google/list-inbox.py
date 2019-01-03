#!/usr/bin/python

from __future__ import print_function
import common,os,re,sys

####################################################
# List calendar events in a format that can be     #
#   used by conky task display.                    #
#                                                  #
# To install APIs:                                 #
#   pip install --upgrade google-api-python-client #
####################################################

def main():
    common.args.process(sys.argv)
    service = common.get_service("gmail")

    # TODO: Add a switch for result count, or at least rethink current value.
    results = service.users().messages().list(userId='me',maxResults=common.args[TITLE_MAX],labelIds=["INBOX"]).execute()
    messages = results.get('messages', [])

    if not messages:
        common.print_error('No e-mail found.')
    else:
      for message in messages:

        # Need to receive full message specifically.
        # Listing returned just a list of IDs and threads.
        fullMessage = service.users().messages().get(userId='me',id=message['id']).execute()
        headers = {}
        # Translate list of dictionaries to a proper dictionary.
        for header in fullMessage['payload']['headers']:
            headers[header['name']] = header

        # TODO: Re-work formatting.
        if common.args[TITLE_CSV_FORMAT]:
            print("\"%s\",\"%s\",\"%s\"" % (headers['Date']['value'], headers['From']['value'], headers['Subject']['value']))
        else:
            print(headers['From']['value'],":",headers['Subject']['value'])

# Set up arguments

DEFAULT_MAX = 5

TITLE_CSV_FORMAT = "csv"
TITLE_MAX = "maximum count"

common.args.add_opt(common.OPT_TYPE_SHORT, "m", TITLE_MAX, "Number of results to return (default: %s)." % common.colour_text(DEFAULT_MAX), converter = int, default = 5)
common.args.add_opt(common.OPT_TYPE_FLAG, "c", TITLE_CSV_FORMAT, "Toggle to display output in a CSV format.")

# Run script

if __name__ == '__main__':
    main()
