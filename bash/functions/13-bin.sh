
# This file covers PATH management and obselete ~/.local/bin a bit.

__add_to_path "$toolsDir/bin"
__add_to_path "$toolsDir/bin/$HOSTNAME"
__add_to_path "$HOME/.local/bin" # TODO: This may be redundant. Double-check on more distributions.

# In lieu of setting a million symlinks up in bin/ or ~/.local/bin,
#     experimenting using aliases for one-off programs instead.

if [ -x "$HOME/.local/blender/blender" ]; then

    alias blender="$HOME/.local/blender/blender"

fi

if [ -x "$HOME/.local/Discord/Discord" ]; then
    alias discord="$HOME/.local/Discord/Discord"
elif [ -x "$HOME/.local/DiscordCanary/DiscordCanary" ]; then
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

if qtype perl && [ -d "$HOME/.perl5" ]; then
    __add_to_path "$HOME/.perl5/bin"; export PATH;
    PERL5LIB="$HOME/.perl5/lib/perl5${PERL5LIB+:}${PERL5LIB}"; export PERL5LIB;
    PERL_LOCAL_LIB_ROOT="$HOME/.perl5${PERL_LOCAL_LIB_ROOT+:}${PERL_LOCAL_LIB_ROOT}"; export PERL_LOCAL_LIB_ROOT;
    PERL_MB_OPT="--install_base \"$HOME/.perl5\""; export PERL_MB_OPT;
    PERL_MM_OPT="INSTALL_BASE=$HOME/.perl5"; export PERL_MM_OPT;
    export MANPATH=$HOME/perl5/man:$MANPATH
fi

if [ -f "$HOME/.rvm/scripts/rvm" ] && ! qtype rvm; then
    . "$HOME/.rvm/scripts/rvm"
fi
