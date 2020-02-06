#!/usr/bin/python

####################################################
# List calendar events in a format that can be     #
#   used by conky task display.                    #
#                                                  #
# To install APIs:                                 #
#   pip install --upgrade google-api-python-client #
####################################################

from __future__ import print_function
import common,datetime,os,re,sys,time
common.local_files.append(os.path.realpath(__file__))

def main():
    """Shows basic usage of the Google Calendar API.

    Creates a Google Calendar API service object and outputs a list of
    upcoming events on the user's calendar.
    """

    common.process()
    service = common.get_service('calendar', 'v3')

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
    main()
