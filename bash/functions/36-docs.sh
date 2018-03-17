#!/bin/bash

update-docs(){
    # I have a number of version-controlled document directories checked out as 'git-docs' or 'svn-docs'.
    # This is a lazy function to find and update all of them at once.

    # For the sake of shaving off a bit of time:
    #   * Do not follow symbolic links.
    #   * Assuming that I will not be storing one of these document directories very deep within my home directory.
    #      * Deepest example (4-depth): ~/Documents/general-topic/sub-topic/svn-docs/
    #   * Do not leave the current file system.
    for dir in $(find -H "$HOME" -maxdepth 4 -mount -type d \( -name 'git-docs' -o -type d -name 'svn-docs' \)); do
        update-repo "$dir"
    done

    # Axe loop variable
    unset dir
}
