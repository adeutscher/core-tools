
# Whitelists

Some domain entries from the remotely managed blocklists are domains that I actually do want to let through.

Add whitelist entries into the `whitelists/` directory in files with a `.txt` extension in order to have them be filtered out when `generate.sh` runs. Each line in these `.txt` file should begin with the domain that you wish to whitelist.

Example whitelist content:

    allowed.domain.com # Unbreak a thing

    # This also unbreaks a thing
    other.domain.ca

    # NOTE: ONLY the first domain will be read.
    # In the below example, second.com will NOT be whitelisted.
    first.com second.com

