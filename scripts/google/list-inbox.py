#!/usr/bin/python

from __future__ import print_function
import common,datetime,getopt,httplib2,os,re,sys,time
from apiclient import discovery

####################################################
# List calendar events in a format that can be     #
#   used by conky task display.                    #
#                                                  #
# To install APIs:                                 #
#   pip install --upgrade google-api-python-client #
####################################################

def hexit(exit_code=0):
    print("./list-inbox.py [-h] [-A account] [-c] [-m max_results]")
    sys.exit(exit_code)

def main(output_format, max_results, tag = None):
    credentials = common.get_credentials(tag)
    if not credentials or common.error_count:
        hexit(1)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)

    # TODO: Add a switch for result count, or at least rethink current value.
    results = service.users().messages().list(userId='me',maxResults=max_results,labelIds=["INBOX"]).execute()
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

        # TODo: Re-work formatting.
        if output_format == "csv":
            print("\"%s\",\"%s\",\"%s\"" % (headers['Date']['value'], headers['From']['value'], headers['Subject']['value']))
        else:
            print(headers['From']['value'],":",headers['Subject']['value'])

if __name__ == '__main__':
    max_results = 5
    output_format = "cli"
    tag = None

    if len(sys.argv) > 1:
        try:
        # Note: Python will not throw a fit if you call for an invalid slice (will simply be empty).
            opts, args = getopt.getopt(sys.argv[1:],"A:chm:")
            for opt, arg in opts:
                if opt in ("-A"):
                    tag = arg
                if opt == "-c":
                    output_format = "csv"
                elif opt == "-h":
                    hexit()
                elif opt == "-m":
                    max_results = int(arg)
        except Exception as e:
            print_error("Argument Parsing Error: %s" % e)

        if common.error_count:
            hexit(1)
    main(output_format, max_results, tag)
