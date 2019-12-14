#!/usr/bin/python

# Use Python to set specific values in Geany's .ini-format configuration file.

import ConfigParser, os

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
options = {
  "geany": {
    "indent_mode": 2, # Tabs as indents
    "indent_type": 0,
    "pref_editor_tab_width": 4,
  }
}

# Confirm desktop-ness
canary = False
for candidate in DESKTOP_CANARIES:
  if os.path.isdir(candidate):
    canary = True
    break # If we have one candidate matched, do not bother to continue onto the rest
if not canary:
  print "Skipping Geany configuration on what looks like a headless server."
  exit(0)

# Make an announcement
print "Applying favoured settings to Geany config: %s" % FILE_PATH

# Make sure that geany config directory at least exists.
if not os.path.isdir(os.path.dirname(FILE_PATH)):
  os.makedirs(os.path.dirname(FILE_PATH))

# Initialize
data = ConfigParser.ConfigParser()
data.read(FILE_PATH)

# Apply options
for section in options:
  # Ensure that section exists.
  if section not in data._sections:
    data.add_section(section)
  for option in options[section]:
    data.set(section, option, options[section][option])

# Write to file
with open(FILE_PATH, 'wb') as file_handle:
  data.write(file_handle)
  file_handle.close()
