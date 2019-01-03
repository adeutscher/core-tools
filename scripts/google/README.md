
# Google Scripts

These are my scripts involving Google services.

Breaking with my usual habit for standalone scripts, all of these scripts rely on being able to load in the `common.py` file for common functions.

## Environment Variables

My Google scripts currently use the following variables:

| Variable        | Description                                                                       | Default Value                                    |
|-----------------|-----------------------------------------------------------------------------------|--------------------------------------------------|
| GOOGLE_SECRET   | Describes the path to your application's client secret data JSON.                 | `${HOME}/.local/tools/google/client_secret.json` |
| GOOGLE_AUTH_DIR | Describes the directory that will hold authorization data for different accounts. | `${HOME}/.local/tools/google/authorization`      |

## Managing Access

If you want to revoke your application's access to your gmail, go to your Google account's [Permissions](https://myaccount.google.com/permissions) page.
Removing your script app from this screen will invalidate any authorization tokens that have already been handed out,

## Scripts

### list-calendar.py

List calendar events.

The script accepts the following arguments:

| Argument     | Description                                                                                                                                               |
|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `-A profile` | Set the profile that you wish to list from (default: `default`). Selecting a profile that does not exist will trigger an authentication flow with Google. |
| `-h`         | Print a help menu and exit.

### list-inbox.py

List recent mail in your inbox.

The script accepts the following arguments:

| Argument     | Description                                                                                                                                               |
|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `-A profile` | Set the profile that you wish to list from (default: `default`). Selecting a profile that does not exist will trigger an authentication flow with Google. |
| `-c`         | Output in CSV format.                                                                                                                                     |
| `-h`         | Print a help menu and exit.                                                                                                                               |
| `-m max`     | Set the maximum number of results to display (default: 5)                                                                                                 |

### send-mail.py

Send an e-mail message through GMail.

The script accepts the following arguments:

| Argument                                              | Description                                                                                                                |
|-------------------- ---|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `-a file`,             | Attach a file to your e-mail message.                                                                                                                     |
| `-A profile`           | Set the profile that you wish to send with (default: `default`). Selecting a profile that does not exist will trigger an authentication flow with Google. |
| `-b a@b.com`           | Add an e-mail address to BCC the e-mail message to.                                                                                                       |
| `-c a@b.com`           | Add an e-mail address to CC the e-mail message to.                                                                                                        |
| `-f from-name`,        | Set a "From" title.                                                                                                                                       |
| `-h`, `--help`         | Print a help menu and exit.                                                                                                                               |
| `-H`, `--html`         | Enable HTML mode. Message content will be expected to be HTML-formatted.                                                                                                 |
| `-m "message-content"` | Set e-mail message content.                                                                                                                               |
| `-s subject`           | Set e-mail message subject.                                                                                                                                    |
| `-t a@b.com`           | Set an address to send the e-mail message to.                                                                                                             |

Other notes:

* At least one recipient must be given. Recipients can be any combination of 'to', 'cc', or 'bcc' addresses.
