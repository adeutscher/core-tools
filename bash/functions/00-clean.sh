# This file is for cleaning out definitions that may interfere when reloading.
# So far, this has only come up for functions that have the same name as former aliases.

unalias update-tools 2> /dev/null
unalias reload-tools 2> /dev/null

# 2016-01-06
unalias encrypt-rsa 2> /dev/null
unalias vnc-quick-write 2> /dev/null

# 2016-01-26
unalias rdp 2> /dev/null

# 2016-02-03
unalias vnc-quick-read 2> /dev/null

# 2016-02-22
# Added after implementing distributed SSH config, SSH will no longer be a SVN checkout.
unset -f update-tools-ssh 2> /dev/null

# 2016-03-07
# Changed wine-games from an alias to a function.
unalias wine-games 2> /dev/null
