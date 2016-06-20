
# Ensure that a temporary directory exists for storing data in /tmp, then set permissions
# tmpfs is faster than reading off of an HDD or an SSD.

toolsCache=/tmp/$USER

mkdir "$toolsCache" 2> /dev/null
chmod 700 "$toolsCache"

