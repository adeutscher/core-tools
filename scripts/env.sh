#!/bin/bash

# Lazy env dump for testing script hooks.

ENV=/usr/bin/env
file=$HOME/temp/env.out
mkdir -p "${file%/*}"
echo $$ > $file
$ENV >> $file
/bin/ps fwaux >> $file

