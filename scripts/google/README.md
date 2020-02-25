
# Google Scripts

These are my scripts involving Google services.

Breaking with my usual habit for standalone scripts, all of these scripts rely on being able to load in the `common.py` file for common functions.

## Application Set Up

To run this script requires a JSON file containing a Google API app client ID and secret.

To get the client ID / secret:
1. With your Google account, navigate to the [Google Developer Console](https://console.developers.google.com/).
2. In the top-left of the screen, select the project menu in the drop-down to the right of the "Google APIs" Logo.
  * The phrasing for this will either along the lines "Select Project", or the title of an existing project.
3. In the lefthand menu of the resulting page, select **Credentials**.
4. In the top menu, select **Create Credentials** -> **Oauth client ID**.
  * For the **Application Type**, select 'Other' and enter a description.
5. When the OAuth client ID is created, download it and place it in a location that is
    accessible to the user that will be running the scripts.
  * The default location is `${HOME}/.local/tools/google/client_secret.json`
  * The location can be overriden using the `GOOGLE_SECRET` environment variable.

Because the script uses one or more "sensitive scopes", the app requires verification by Google to run unrestricted.
  However, the limits of an unverified app should be more than enough for personal/small-group use. At this time, I
  haven't seen the need to make an effort to verify my personal app.

The limits on unverified apps are

* Limit of 100 different user accounts.
* 10,000 token grants per day.
* Users receive an additional warning that the app is unsafe when they authenticate.

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
