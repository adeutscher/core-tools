#!/bin/bash

update-docs(){
    # I have a number of checkouts for documents checked out as 'git-docs' or 'svn-docs'.
    # This is a lazy function to find and update all of them at once.

    # For the sake of speed, assuming that I will not be storing one of these document directories very deep within my home directory.
    for dir in $(find "$HOME" -type d -name 'git-docs' -o -type d -name 'svn-docs'); do
        update-repo "$dir"
    done

    # Axe loop variable
    unset dir
}
