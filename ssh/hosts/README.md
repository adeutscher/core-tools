
# ssh/hosts directory

Configurations in this directory will only be added to the SSH configuration if they match the hostname of the system running the script.

For example, The machine with the hostname of `desktop.domain.com` will only load the `config-desktop.domain.com` file.

If no exact match exists and the hostname contains a dash, everything after the last dash is dropped and that name is tried instead. For example, `labpc-01` and `labpc-02` will both load `config-labpc`.
