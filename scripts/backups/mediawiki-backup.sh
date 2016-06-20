#!/bin/bash

#set -x

# Common message functions.

if [ -t 1 ]; then
    # Define colours
    BLUE='\033[1;34m'
    GREEN='\033[1;32m'
    RED='\033[1;31m'
    YELLOW='\033[1;93m'
    BOLD='\033[1m'
    NC='\033[0m' # No Color
fi

error(){
    printf "$RED"'Error'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

notice(){
    printf "$BLUE"'Notice'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

success(){
    printf "$GREEN"'Success'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}

warning(){
    printf "$YELLOW"'Warning'"$NC"' ('"$GREEN"'%s'"$NC"'): %s\n' "$(basename $0)" "$@"
}
# end message functions

readonly SITE_DIR=$1

if [ -z "$SITE_DIR" ]; then
    error "$(printf "No site directory specified. Usage: $GREEN%s$NC site_directory backup_directory" "./$(basename $0)")" >&2
    exit 1
fi

# Back up the first MediaWiki installation that we find in our site folder.
readonly WIKI_DIR=$(dirname $(find "$SITE_DIR" -name LocalSettings.php 2>/dev/null | head -n 1))

if [ -z "$WIKI_DIR" ]; then
    error "$(printf "Unable to find a MediaWiki instance in the specified directory ($GREEN%s$NC). Usage: $GREEN%s$NC site_directory_backup_directory" "$SITE_DIR"  "./$(basename $0)")" >&2
    exit 1
fi

# Full path to our LocalSettings.php file.
readonly WIKI_SETTINGS_FILE=$WIKI_DIR/LocalSettings.php
# Full path to our backup directory.
readonly BACKUP_DIR="$2/$(date +"%Y-%m-%d-%H-%M-%S")-wiki-backup"


# Double-check that the local settings file exists
#   (even though we used it as a basis for finding the wiki dir in the first place).
if [ ! -f "$WIKI_SETTINGS_FILE" ]; then
    error "$(printf "LocalSettings.php not found ($GREEN%s$NC)" "$WIKI_SETTINGS_FILE")" >&2
    exit 1
fi

# Checking to see if a backup directory has been specified.
# Will check for existence later.
if [ -z "$BACKUP_DIR" ]; then
    error "$(printf "No backup directory specified. Usage: $GREEN%s$NC site_directory backup_directory" "./$(basename $0)")" >&2
    exit 1
fi

wiki_db=$(cat "$WIKI_SETTINGS_FILE" | grep \$wgDBname\ *\= | grep -o  "[\'\"][^\'\"]*[\'\"];" | sed "s/^[\"\']//g" | sed "s/[\"\'];$//g")
wiki_db_server=$(cat "$WIKI_SETTINGS_FILE" | grep \$wgDBserver\ *\= | grep -o  "[\'\"][^\'\"]*[\'\"];" | sed "s/^[\"\']//g" | sed "s/[\"\'];$//g")
wiki_db_user=$(cat "$WIKI_SETTINGS_FILE" | grep \$wgDBuser\ *\= | grep -o  "[\'\"][^\'\"]*[\'\"];" | sed "s/^[\"\']//g" | sed "s/[\"\'];$//g")
wiki_db_password=$(cat "$WIKI_SETTINGS_FILE" | grep \$wgDBpassword\ *\= | grep -o  "[\'\"][^\'\"]*[\'\"];" | sed "s/^[\"\']//g" | sed "s/[\"\'];$//g")

missing_settings=0
if [ -z "$wiki_db" ]; then
    error 'Was unable to parse LocalSettings.php for a necessary variable: $wgDBname' >&2
    missing_sessings=1
fi

if [ -z "$wiki_db_server" ]; then
    error 'Was unable to parse LocalSettings.php for a necessary variable: $wgDBserver' >&2
    missing_sessings=1
fi

if [ -z "$wiki_db_user" ]; then
    error 'Was unable to parse LocalSettings.php for a necessary variable: $wgDBuser' >&2
    missing_sessings=1
fi

if [ -z "$wiki_db_password" ]; then
    error 'Was unable to parse LocalSettings.php for a necessary variable: $wgDBpassword' >&2
    missing_sessings=1
fi

if [ "$missing_settings" -gt "0" ]; then
    error "$(printf "Unable to parse LocalSettings.php for necessary variables.")" 2> /dev/null
    exit 1
fi

# Check to see if there is a lock file set up in LocalSettings.php
wiki_lock_file=$(cat "$WIKI_SETTINGS_FILE" | grep \$wgReadOnlyFile\ *\= | grep -o  "[\'\"][^\'\"]*[\'\"];" | sed "s/^[\"\']//g" | sed "s/[\"\'];$//g" | sed 's/\$IP/'$(sed 's/\//\\\//g' <<< "$WIKI_DIR")'/g')

# Check to see that the lock file is valid.
# A valid lock file path will not have a PHP file path.
if [ -n "$wiki_lock_file" ]; then
    grep -qi '\.php$' <<< "$wiki_lock_file" && error "Cannot use a file with an extension of '.php' as a lock file" >&2 && exit 3
else
    warning "$(printf "Unable to find a lock file path in ${GREEN}LocalSettings.php${NC}. Add a path under the $BOLD\$wgReadOnlyFile$NC variable to make the wiki read-only.")"
fi

# Motion starts now.

# Double-check that the specified backup directory exists.
# No point in doing the backup with no destination.
if [ ! -d "$BACKUP_DIR" ]; then
    mkdir -p "$BACKUP_DIR" 2> /dev/null
    result=$?
    if [ "$result" -gt 0 ]; then
        error "$(printf "Unable to create backup directory: $BACKUPDIR")"
        exit 2
    fi
fi

if [ -n "$wiki_lock_file" ]; then
    notice "$(printf "Creating lock file: $GREEN%s$NC" "$wiki_lock_file")"
    printf "This wiki is temporarily in read-only mode in order to perform backups." > "$wiki_lock_file"
fi

notice "Backing up wiki files."
if tar cvz --ignore-failed-read -C "$SITE_DIR/.." -f $BACKUP_DIR/wiki-files-$wiki_db-$(date +"%Y-%m-%d-%H-%M-%S").tar.gz "$(basename $SITE_DIR)" 2> /dev/null >&2; then
    success "Successfully backed up wiki files."
else
    error "$(printf "Unable to complete ${BLUE}tar${NC} collection of wiki files.")"
fi

notice "Backing up wiki database."
if nice -n 19 mysqldump -u $wiki_db_user --host=$wiki_db_server --password="$wiki_db_password" $wiki_db -c | nice -n 19 gzip -9 > $BACKUP_DIR/wiki-db-$wiki_db-$(date +"%Y-%m-%d-%H-%M-%S").sql.gz; then
    success "Successfully backed up wiki database."
else
    error "$(printf "Unable to complete ${BLUE}mysqldump${NC} run of wiki database.")"
fi

if [ -n "$wiki_lock_file" ]; then
    notice "$(printf "Removing lock file: $GREEN%s$NC" "$wiki_lock_file")"
    if ! rm -f "$wiki_lock_file"; then
        error "Failed to remove lock file."
    fi
fi

exit 0
