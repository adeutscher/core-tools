# This file is for unsetting unwanted alias/function definitions.

# Functions or aliases may be removed if they do one of the following:
#   - Interfere with the reloading process
#     - This usually happens if I have recently re-made an alias as a function.
#     - These removals will themselves be removed if I am 100% positive that nothing is using the old definitions.
#   - Are an unwanted function/alias from outside of my tools modules.

# 2016-09-06
# Fighting Fedora 24 deprecation nudging by unsetting the 'ifconfig' and 'service' functions.
# These functions print complain (rightly) about the function being deprecated and exit out without doing anything.
# Note: There is also a function to override 'yum', but I am happy with leaving that in.
unset -f ifconfig service 2> /dev/null

# 2018-04-30
# Converted wait-for-pid to a script, mostly to allow it to itself be waited for.
unset -f wait-for-pid 2> /dev/null

# 2018-05-19
# Converted connection aliases.
unset -f connections-in connections-in-all connections-in-remote connections-in-lan connections-in-local
unset -f connections-out connections-out-all connections-out-remote connections-out-lan connections-out-local

# 2018-07-17
# Scriptified 'mux' functions
unset -f mux mux-force
