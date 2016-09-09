
# DNS Blocker

The scripts in this directory convert hosts format files to a format that BIND9 can use. 

The `generate.sh` script reads all `.txt` files out of the `blacklists/` directory, then sanitizes and de-duplicates them before writing them to `denylist.zones`.

Once generated, you need to sub in the path that you intend to place the `denylist.db` file:

    sed -i "s|__DB_PATH__|/etc/named/zones/denylist.db|g" "denylist.zones"

After substituting in the `denylist.db` path, move `denylist.db` to the path that you specified with `sed`, and move `denylist.zone` to someplace permanent that BIND9 will read off of.

Adjust `/etc/named.conf` to load in `denylist.zones`:

    Include /etc/named/denylist.zones;

## Whitelists

Some domain entries from the remotely managed blocklists are domains that I actually do want to let through.

Add whitelist entries into the `whitelists/` directory in files with a `.txt` extension in order to have them be filtered out when `generate.sh` runs. Each line in these `.txt` file should begin with the domain that you wish to whitelist.

Example whitelist content:

    allowed.domain.com # Unbreak a thing

    # This also unbreaks a thing
    other.domain.ca

    # NOTE: ONLY the first domain will be read.
    # In the below example, second.com will NOT be whitelisted.
    first.com second.com

## Other Scripts

To load in remotely managed blocklists, use the `download.sh` script.

To get numbers of duplicates across all records, use the `check.sh` script.
