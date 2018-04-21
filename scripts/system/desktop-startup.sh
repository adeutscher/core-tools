
# A quick and lazy all-in-one startup script for GUI apps.

# Reminder: CONKY_SCREEN provided by environment variables if necessary.
${0%/*}/../../bash/conky/start.sh

if [ -f "$HOME/.local/DiscordCanary/DiscordCanary" ]; then
    "$HOME/.local/DiscordCanary/DiscordCanary" &
fi

#
if type skype 2> /dev/null >&2; then
    skype &
fi



