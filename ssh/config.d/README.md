
# ssh/config.d/ directory

This directory allows users to sort configuration into multiple files.

All files in this directory will be loaded into the SSH configuration when `ssh-compile-config` is run,
with the exception of anything with "readme" in its name (case-insensitive).

Sub-configurations are marked for identification the compiled configuration.
