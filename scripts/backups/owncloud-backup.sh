#!/bin/bash

ssh_server=$1
config_file=$2
backup_destination=$3

if [ ! -n "$backup_destination" ]; then
  echo "No config destination provided..." >&2
  echo "Usage: $0 ssh-address config-filepath destination-filepath" >&2
  echo "  Note: SSH address is a SSH config entry or a username@password entry." >&2
  echo "  Note: The final backup destination will be a timestamped directory within the specified path."
  exit 2
fi

config_file_contents=$(ssh $ssh_server -- cat $config_file)

# Parse the config file for our properties.
datadirectory=$(echo "$config_file_contents" | grep datadirectory | cut -d"'" -f 4)
dbuser=$(echo "$config_file_contents" | grep dbuser | cut -d"'" -f 4)
dbpassword=$(echo "$config_file_contents" | grep dbpassword | cut -d"'" -f 4)
dbhost=$(echo "$config_file_contents" | grep dbhost | cut -d"'" -f 4)
dbname=$(echo "$config_file_contents" | grep dbname | cut -d"'" -f 4)

# Confirm that we were able to parse our properties correctly.
if [ -z "$datadirectory" ] \
    || [ -z "$dbuser" ] \
    || [ -z "$dbpassword" ] \
    || [ -z "$dbhost" ] \
    || [ -z "$dbname" ]; then

    echo "Failed to parse an essential configuration property from ownCloud config." >&2
    exit 3
fi

## Is the data directory stored in the 'datadirectory' option within the same dir as the config file? To check this:

backup_dir=${backup_destination}/owncloud-backup-$(date +"%Y-%m-%d-%H-%M")

if ! mkdir -p "$backup_dir"; then
    echo "Failed to create backup directory." >&2
    exit 4
fi

# Try to copy the backups from a previous run to prevent redundant downloads.
echo "Looking for previous backups to base the current backup on."
old_backup_dir="${backup_destination}/$(ls "${backup_destination}" | tail -n2 | head -n1)"
# Use a lazy string comparison to make sure that we haven't grabbed our newly-made directory as the most recent one.
if [ -n "$old_backup_dir" ] && [[ "$(basename "$old_backup_dir")" != "$(basename "$backup_dir")" ]]; then
    rsync -av --progress "$old_backup_dir/" "$backup_dir"
    
    # temporary fix for short term testing.
    #rmdir "$backup_dir"
    #ln -s $(realpath "$old_backup_dir/") "$backup_dir"
fi

# Get the path to the parent of the config/ directory
config_parent=$(dirname $(dirname "$config_file"))
if ! echo "$datadirectory" | grep -q "$config_parent"; then
    # Data directory is stored outside of parent directory. Need to do a separate run of rsync.
    echo "User data directory is stored separately from ownCloud files. Backing up data."
    rsync -avP --delete $ssh_server:$datadirectory/ "$backup_dir/data/"

    echo "Backing up ownCloud files"
else
    echo "Backing up ownCloud files and user data."
fi

# Backup the ownCloud files (and also data if it is included).
rsync -avP --delete $ssh_server:$config_parent/ "$backup_dir/owncloud/"

# Backup our database
echo "Backing up database."
ssh $ssh_server "mysqldump --lock-tables -h $dbhost -u $dbuser -p\"$dbpassword\" \"$dbname\" | gzip" > "$backup_dir/owncloud-sqlbkp_$(date +"%Y%m%d-%H-%M").bak.sql.gz"
