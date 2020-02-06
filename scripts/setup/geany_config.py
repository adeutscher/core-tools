#!/usr/bin/env python

# Use Python to set specific values in Geany's .ini-format configuration file.

from __future__ import print_function
import configparser, os, sys

# Constant variables
##

# Path to configuration file
FILE_PATH = "%s/.config/geany/geany.conf" % os.environ["HOME"]
# At least one of these "canary" directories must exist.
# Do not bother writing a configuration on a system that appears to be headless.
# TODO: Improve on this check.
DESKTOP_CANARIES = [
  "/usr/share/backgrounds",
  "/usr/share/X11"
  "/etc/mate-settings-daemon"
]

# Define options
# Unfortunately, no master document seems to exist for describing configuration options.
# Values may still need some improvement over time.
# Values must be exptressed as strings
options = {
  "geany": {
    "indent_mode": 2, # Tabs as indents
    "indent_type": 0,
    "pref_editor_tab_width": 4,
  }
}

class Parser(configparser.ConfigParser):
  # The Parser class inherits from ConfigParser because some methods
  #    in ConfigParser on Python 3 gave TypeErrors requesting bytes when
  #    writing to a file.
  def write(self, fp, space_around_delimiters=True):
    """Write an .ini-format representation of the configuration state.

       If `space_around_delimiters' is True (the default), delimiters
       between keys and values are surrounded by spaces.
    """

    if space_around_delimiters:
      d = " %s " % self._delimiters[0]
    else:
      d = self._delimiters[0]

    if self._defaults:
      self._write_section(fp, self.default_section,
                          self._defaults.items(), d)

    for section in self._sections:
      self._write_section(fp, section,
                          self._sections[section].items(), d)

  def _get_bytes(self, data):
    if sys.version_info[0] == 2:
      return bytes(data)
    return bytes(data, 'utf-8')

  def _write_section(self, fp, section_name, section_items, delimiter):
    """Write a single section to the specified `fp'."""

    fp.write(self._get_bytes("[%s]\n" % section_name))
    for key, value in section_items:
      value = self._interpolation.before_write(self, section_name, key, value)

    if value is not None or not self._allow_no_value:
      value = delimiter + str(value).replace('\n', '\n\t')
    else:
      value = ""
      fp.write(self._get_bytes("%s%s\n" % (key, value)))
    fp.write(self._get_bytes("\n"))

# Confirm desktop-ness
canary = False
for candidate in DESKTOP_CANARIES:
  if os.path.isdir(candidate):
    canary = True
    break # If we have one candidate matched, do not bother to continue onto the rest
if not canary:
  print("Skipping Geany configuration on what looks like a headless server.")
  exit(0)

# Make an announcement
print("Applying favoured settings to Geany config: %s" % FILE_PATH)

# Make sure that geany config directory at least exists.
if not os.path.isdir(os.path.dirname(FILE_PATH)):
  os.makedirs(os.path.dirname(FILE_PATH))

# Initialize
data = Parser()
data.read(FILE_PATH)

# Apply options
for section in options:
  # Ensure that section exists.
  if section not in data._sections:
    data.add_section(section)
  for option in options[section]:
    data.set(section, option, str(options[section][option]))

# Write to file
with open(FILE_PATH, 'wb') as file_handle:
  data.write(file_handle)
