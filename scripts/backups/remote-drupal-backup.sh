#!/bin/sh

# Define colours
if [ -t 1 ]; then
    BLUE='\033[1;34m'
    GREEN='\033[1;32m'
    RED='\033[1;31m'
    YELLOW='\033[1;93m'
    BOLD='\033[1m'
    NC='\033[0m' # No Color
fi

error(){
    printf "$RED"'Error'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

notice(){
    printf "$BLUE"'Notice'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

success(){
    printf "$GREEN"'Success'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

warning(){
    printf "$YELLOW"'Warning'"$NC"'['"$GREEN"'%s'"$NC"']: %s\n' "$(basename $0)" "$@"
}

get_opts(){

    while [ -n "$1" ]; do
        local opt=$1
        case "$opt" in
        "-d")
            drush_enabled=1
            ;;
        "-l")
            if [ -z "$local_path" ]; then             
                local_path=$2
                notice "$(printf "Local path for backups: $GREEN%s$NC" "$local_path")"
            fi
            ;;
        "-m")
            if [ -z "$mysqldump_path" ]; then
                mysqldump_path=$2
                notice "$(printf "Absolute path to $BLUE%s$NC on remote machine: $GREEN%s$NC" "mysqldump" "$local_path")"
            fi
            ;;
        "-r")
            if [ -z "$remote_path" ]; then             
                remote_path=$2
                notice "$(printf "Remote path for site: $GREEN%s$NC" "$remote_path")"
            fi
            ;;
        "-s")
            if [ -z "$ssh_alias" ]; then             
                ssh_alias=$2
                notice "$(printf "SSH credentials/alias for remote site: $BOLD%s$NC" "$ssh_alias")"
            fi
            ;;
        esac
        shift
    done

    if [ -z "$local_path" ] || [ -z "$remote_path" ] || [ -z "$ssh_alias" ]; then
        error "Missing required arguments."
        notice "$(printf "Usage: $GREEN%s$NC -s ssh-alias -r remote-path -l local-path [-d] [-m mysqldump-path]" "./$(basename "$0")")"
        exit 1
    fi
}

backup_drupal(){
    local script_dir=`dirname $0`

    local directory="$local_path"

    local site_dir=$directory/backup/site
    local db_dir=$directory/backup/db
    local log_dir=$directory/backup/log
    local other_dir=$directory/backup/log

    # Make sure we're working off of fresh logs.
    rm -rf $log_dir
    # Ensure that these folders exist.
    if ! mkdir -p $db_dir $log_dir $other_dir $site_dir; then
        error "$(printf "Unable to ensure that the directory stucture based around $GREEN%s$NC exists." $directory)"
        return 1
    fi

    # Gather files via rsync.
    notice "Gathering Drupal files..."
    if ! rsync -av --progress --delete $ssh_alias:$remote_path/ $site_dir/ > $log_dir/rsync.log 2> $log_dir/rsync_err.log; then
        error "$(printf "Unable to back up Drupal files to $GREEN%s$NC..." "$site_dir/")"
        return 2
    fi

    if [ -n "$drush_enabled" ]; then
        # Using drush
        if ! ssh $ssh_alias "cd \"$remote_path\" && drush cc all && drush sql-dump | gzip -9" > $db_dir/db.sql.gz 2> $log_dir/db_err.log; then
            error "$(printf "Unable to back up database using $BLUE%s$NC." "drush")"
            return 3
        fi
    else
        # Not using drush
        notice "Gathering database info by parsing settings file."
        local settings_file=$site_dir/sites/default/settings.php

        local db_name="$(cat "$settings_file" | grep '^[^\*]*\$data' -A 8 | grep '^[^\$]*database' | cut -d"'" -f 4)"
        local db_user="$(cat "$settings_file" | grep '^[^\*]*\$data' -A 8 | grep '^[^\$]*username' | cut -d"'" -f 4)"
        local db_password="$(cat "$settings_file" | grep '^[^\*]*\$data' -A 8 | grep '^[^\$]*password' | cut -d"'" -f 4)"
        local db_host="$(cat "$settings_file" | grep '^[^\*]*\$data' -A 8 | grep '^[^\$]*host' | cut -d"'" -f 4)"

        if [ -n "$db_password" ]; then
            local pass=Yes
        else
            local pass=No
        fi

        notice "$(printf "Database info (as seen by remote server): $BOLD%s$NC@$GREEN%s$NC (User: $BOLD%s$NC, Have Password: $BOLD%s$NC)" "$db_name" "$db_host" "$db_user" "$pass")" 
        if [ -z "$db_name" ] || [ -z "$db_user" ] || [ -z "$db_host" ] || [ -z "$db_password" ]; then
            error "Was unable to parse at least one database field."
            return 3
        fi

        notice "Gathering database backup..."
        if ! ssh "$ssh_alias" "${mysqldump_path:-mysqldump} -u \"$db_user\" -p\"$db_password\" \"$db_name\"" | gzip > "$db_dir/db.gz"; then
            error "Failed to back up database..."
            return 4
        fi
    fi

}

get_opts $@
backup_drupal
