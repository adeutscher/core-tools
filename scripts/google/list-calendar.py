#!/usr/bin/python

from __future__ import print_function
import common,getopt,httplib2,os,re,sys,time

####################################################
# List calendar events in a format that can be     #
#   used by conky task display.                    #
#                                                  #
# To install APIs:                                 #
#   pip install --upgrade google-api-python-client #
####################################################

try:
    from apiclient import discovery
except ImportError:
    common.print_error("Could not import apiclient.")

import datetime

def hexit(exit_code=0):
    print("./list-calendar.py [-h] [-A account]")
    exit(exit_code)

def main(tag = None):
    """Shows basic usage of the Google Calendar API.

    Creates a Google Calendar API service object and outputs a list of
    upcoming events on the user's calendar.
    """
    credentials = common.get_credentials(tag)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)

    then = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).isoformat() + 'Z' # 'Z' indicates UTC time

    # Getting recent and upcoming events.
    for calendar in ['primary']:
        eventsResult = service.events().list(
            calendarId=calendar, timeMin=then, maxResults=25, singleEvents=True,
            orderBy='startTime').execute()
        events = eventsResult.get('items', [])

        if not events:
            # No events found.
            # Do not corrupt format.
            pass
        for event in events:
            storedDateString = "-".join(event['start'].get('dateTime', event['start'].get('date')).split("-")[0:3])
            if re.match(r"^\d{4}-\d{2}-\d{2}$", storedDateString):
                # Holidays (also manual all-day events?)
                dateObj = time.strptime(storedDateString, "%Y-%m-%d")
            else:
                dateObj = time.strptime(storedDateString, "%Y-%m-%dT%H:%M:00")
            text = "%s,%s" % (time.strftime("%Y-%m-%d,%H:%M", dateObj), event['summary'])
            print(text)

if __name__ == '__main__':

    tag = None

    try:
        opts, args = getopt.getopt(sys.argv[1:],"A:h")
        for opt, arg in opts:
            if opt in ("-A"):
                tag = arg
            elif opt == "-h":
                hexit()
    except Exception as e:
        common.print_error("Argument Parsing Error: %s" % e)

    if common.error_count:
        hexit(1)

    main(tag)
