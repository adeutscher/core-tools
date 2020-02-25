#!/usr/bin/python

############################################################################
# Download Google Drive spreadsheet sheet                                  #
#     in CSV format                                                        #
# Based on: https://gist.github.com/xflr6/57508d28adec1cd3cd047032e8d81266 #
#                                                                          #
# To install APIs:                                                         #
#   pip install --upgrade google-api-python-client                         #
############################################################################

from __future__ import print_function
import common,contextlib,csv,os,re,sys
common.local_files.append(os.path.realpath(__file__))

if sys.version_info.major == 2:
    from itertools import izip as zip

def itersheets(service, id):

    doc = service.spreadsheets().get(spreadsheetId=id).execute()

    title = doc['properties']['title']
    sheets = [s['properties']['title'] for s in doc['sheets']]
    params = {'spreadsheetId': id, 'ranges': sheets, 'majorDimension': 'ROWS'}
    result = service.spreadsheets().values().batchGet(**params).execute()
    for name, vr in zip(sheets, result['valueRanges']):
        yield (title, name), vr['values']

def export_csv(service, docid, filename_template='%(title)s - %(sheet)s.csv'):

    error_count = common.error_count # Note original error count

    if docid and re.match("^https://docs.google.com/spreadsheets/d/", docid, re.IGNORECASE):
        docid = docid.split("/")[5]

    try:
        for (doc, sheet), rows in itersheets(service, docid):
            file_name = filename_template % {'title': doc, 'sheet': sheet}
            file_path = os.path.join(common.args[TITLE_DIR], common.args[TITLE_PREFIX], file_name)
            common.print_notice("Saving \"%s\" sheet to file: %s" % (common.colour_text(sheet), common.colour_text(file_name, common.COLOUR_GREEN)))
            with open(file_name, 'w') as fd:
                write_csv(service, fd, rows)
    except Exception as e:
        common.print_exception(e)
    return error_count == common.error_count

def main():
    """Shows basic usage of the Google Calendar API.

    Creates a Google Calendar API service object and outputs a list of
    upcoming events on the user's calendar.
    """

    common.process()
    service = common.get_service('sheets', 'v4')

    exit_code = 0
    for o in common.args.operands:
        if not export_csv(service, o):
            exit_code = 1
    return exit_code

def pad_list(l, max_columns):
    while len(l) < max_columns: l.append('')
    return l

def validate_arg_operands(self):
    if not self.operands:
        return "No spreadsheed IDs defined."
common.args.add_validator(validate_arg_operands)

def validate_arg_dir(self):
    if not os.path.isdir(self[TITLE_DIR]):
        try:
            os.makedirs(self[TITLE_DIR])
        except Exception as e:
            return "Could not create CSV directory %s: %s" % (common.colour_text(self[TITLE_DIR], common.COLOUR_GREEN), str(e))
common.args.add_validator(validate_arg_dir)

def write_csv(service, fd, rows, dialect='excel'):
    csvfile = csv.writer(fd, dialect=dialect)
    max_columns = max([len(r) for r in rows])
    for r in rows:
        csvfile.writerow(pad_list(r, max_columns))

DEFAULT_DIR = "."
TITLE_DIR = "target_dir"
TITLE_PREFIX = "prefix"

common.args.add_opt(common.OPT_TYPE_SHORT, "d", TITLE_DIR, "Specify output directory.", default = DEFAULT_DIR)
common.args.add_opt(common.OPT_TYPE_SHORT, "p", TITLE_PREFIX, "File name prefix", default = "")

if __name__ == '__main__': exit(common.run(main))
