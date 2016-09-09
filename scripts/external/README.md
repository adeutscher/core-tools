
# External Scripts

These scripts seem to go out of their way to mess with my sorting system, so they get filed as "none-of-the-above".

* Though these are scripts, they are not run directly. They are implemented in other locations instead, so they could go within `files/`.
* At the moment, these scripts are largely networking-focused, which would place them in `scripts/networking/`
* These scripts may need to be added into other scripts, which would technically make them something that might go in `scripts/clipboard/`.

# Script List

## dns-compiler

Generate configuration snippets for BIND9 using information from NetworkManager or VPN connection scripts, then reload your configuration so that you can access both your internal domains and your default DNS server. Still a work in progress.

### Setup

The setup location for this script varies on where you are getting your domain information from:

| Connection Type   | Location                                   |
|-------------------|--------------------------------------------|
| NetworkManager    | `/etc/NetworkManager/dispatcher.d/` script |
| OpenVPN           | Addition to `vpnc-script`                  |
| Cisco OpenConnect | Addition to `--up`/`--down` scripts        |

Notes on usage:

* Before deploying these scripts, you should also confirm the following variables:
  * `DNS_COMPILER_DATA`: This is the path to a CSV file that contains information on acquired domains.
  * `DNS_COMPILER_TARGET`: This is the path that the information contained in `DNS_COMPILER_DATA` will be compiled in a format that can be read by BIND9.
    * You must manually adjust your configuration to read in the contents of this file.
    * The file must be readable by the `named` user on RHEL-based systems, or the `bind` user on Debian-based systems.
* If the NetworkManager service is enabled, then dispatcher scripts in `/etc/NetworkManager/dispatcher.d/` will probably run after either OpenVPN or Cisco. If NetworkManager is running, then you don't really need to bother implementing the script in any other places.

### Future

This script works by making a new configuration file and restarting BIND9, which can be a bit slow (~4s or higher) because of the DNS blacklist that I also use. At some point in the near future, I hope to hammer out my troubles with the `rndc addzone` and `rndc delzone` commands to be able to avoid restarting BIND9 and make the new configuration available a little faster.

### 

## snat-adjuster

If IPv4 forwarding is enabled when a new interface connects, then add an SNAT rule for traffic coming out of the new interface.

The setup location for this script varies on where your new interface or connection came from:

| Connection Type   | `fix_interface_snat` example   | Location                                   |
|-------------------|--------------------------------|--------------------------------------------|
| NetworkManager    | `fix_interface_snat $IP_IFACE` | `/etc/NetworkManager/dispatcher.d/` script |
| OpenVPN           | `fix_interface_snat $dev`      | Addition to `vpnc-script`                  |
| Cisco OpenConnect | `fix_interface_snat $tundev`   | Addition to `--up`/`--down` scripts        |

Notes on usage:

* This script uses the following variables that should be configured per-system:
  * `SNAT_CHAIN`: The chain in the NAT table that will be read from and written to
  * `SNAT_LABEL`: Label for the benefit of anyone manually looking through the chain.
  * `OTHER_FILTERS`: Extra iptables filters
* If the NetworkManager service is enabled, then dispatcher scripts in `/etc/NetworkManager/dispatcher.d/` will probably run after either OpenVPN or Cisco. If NetworkManager is running, then you don't really need to bother implementing the script in any other places.
* Since the interface variables are mutually exclusive (at least so far as I've observed), I'm tempted to just advise throwing all of the variables into one argument and letting things sort themselves out.
* If you want these scripts to SNAT to an address other than the one parsed out of `ip` output, then you can call `fix_snat` directly using the desired SNAT address as your second argument.
  * For example: `fix_snat eth0 192.168.2.2`
