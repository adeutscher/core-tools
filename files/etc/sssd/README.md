
# SSSD Setup Reminders

1. Place the file at `/etc/sssd/sssd.conf`
2. Run `chmod 700 /etc/sssd/sssd.conf` and `chown root:root /etc/sssd/sssd.conf`

## Activation on RHEL

To enable SSSD as an authentication option on RHEL-based systems:

    authconfig --enablesssd --enablesssdauth --enablemkhomedir --update

## Activation on Debian

SSSD is automatically activated as an authentication option on Debian-based systems. However, the home directory will not automatically be created.

Add the following to `/etc/pam.d/common-session` (maybe above the `pam_ck_connector.so` line, though I'm not 100% positive that order matters):

    session required pam_mkhomedir.so umask=0022 skel=/etc/skel
