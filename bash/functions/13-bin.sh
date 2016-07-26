
# In lieu of setting a million symlinks up in bin/ or ~/.local/bin,
#     experimenting using aliases for one-off programs instead.

if [ -x "$HOME/.local/blender/blender" ]; then

    alias blender="$HOME/.local/blender/blender"

fi

if [ -x "$HOME/.local/DiscordCanary/DiscordCanary" ]; then

    alias discord="$HOME/.local/DiscordCanary/DiscordCanary"

fi

if [ -d "$HOME/.local/eclipse" ]; then
     for __eclipse in "$HOME/.local/eclipse"/*; do
         if [ -d "$__eclipse" ]; then
             alias eclipse-${__eclipse##*/}="$__eclipse/eclipse"
         fi
     done
     unset __eclipse
fi

if [ -f "$HOME/.local/yed/yed.jar" ]; then
    alias yed="java -jar \"$HOME/.local/yed/yed.jar\""
fi
