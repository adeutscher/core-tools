#!/bin/bash

update-docs(){
    # I have a number of checkouts for documents checked out as 'svn-docs'.
    # This is a lazy function to find and update all of them at once.

    # For the sake of speed, assuming that I will not be storing 'svn-docs' very deep within my home directory.
    for dir in $(find "$HOME" -maxdepth 4 -type d -name 'svn-docs'); do
        update-repo "$dir"
    done

    # Axe loop variable
    unset dir
}
