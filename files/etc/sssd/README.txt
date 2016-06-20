Reminder: Place the file at '/etc/sssd/sssd.conf', then run 'chmod 700 /etc/sssd/sssd.conf' and 'chown root:root /etc/sssd/sssd.conf'

Activation on CentOS: authconfig --enablesssd --enablesssdauth --enablemkhomedir --update

Skel on Debian: Add the following to /etc/pam.d/common-session above 'pam_ck_connector.so' line: session required pam_mkhomedir.so umask=0022 skel=/etc/skel
