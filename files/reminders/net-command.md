
The `net` command can be used to interact with various Windows or Windows-like (i.e SAMBA) services.

## List Remote Shares

List shares on 10.11.12.10 with the username 'redacted-username'
    net  -I 10.11.12.10 -U 'redacted-username' rap share

## Remote Shutdown of Windows Machine

To tell the machine at the address of 10.11.12.3 to reboot after 30s using the credentials of 'administrator':

    net rpc shutdown -I 10.11.12.3 -U administrator

To perform the same operation from Windows (after 20s, using the credentials of your current user):

    shutdown /s /t 20 /m \\10.11.12.3

### Remote Reboot

To restart the remote Windows machine instead of shutting it down entirely, add the ***-r*** switch:

    net rpc shutdown -I 10.11.12.3 -U administrator -r

## Abort Remote Shutdown of Windows Machine

Abort the shutdown of the machine at the address of 10.11.12.3 using the credentials of 'administrator' from Linux:

    net rpc abortshutdown -I 10.11.12.3 -U administrator

To perform the same operation from Windows:

    shutdown /a /m \\10.11.12.3
