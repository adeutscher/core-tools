# Logic in this file is meant for major environment checks.
# If something here triggers, then it's something that the user should be informed about immediately.

__toolCount=$((${__toolCount:-0}+1))

if [ ${__toolCount:-0} -gt 1 ]; then
  warning "It looks like core tools are installed twice on this system..."
elif [ "$(date +%s)" -le "1545465600" ]; then
  # Hard-coded date is for midnight at the start of 2018-12-22, the date that this feature was first added.
  # If this logic triggers, then it's likely that the server time reset after a reboot (perhaps because of a bad CMOS battery?)
  #
  # If the server time is off by enough (such as the server that inspired me to add this feature being bumped back to 2001),
  #   then most/all SSL certificates will fail to validate because the server thinks that the certificate start time hasn't happened yet.
  #
  # I pondered on a system wherein the server would update the last-seen date and detect a back-track, but that seemed overly complicated.
  # Starting the date at the start of the present day should be fine for my purposes (most time-jumps would probably be back 10+ years anyways).
  # For reminders to correct the time with short-term gaps, I should update the hard-coded date once or twice a year.

  warning "Machine time ($(date)) is too early. Adjust the system time or contact the system administrator to do so."
fi
