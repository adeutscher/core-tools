
# This file covers binary shortcuts.
###

# Perl Variables

if qtype perl && [ -d "$HOME/.perl5" ]; then
    __add_to_path "$HOME/.perl5/bin"; export PATH;
    PERL5LIB="$HOME/.perl5/lib/perl5${PERL5LIB+:}${PERL5LIB}"; export PERL5LIB;
    PERL_LOCAL_LIB_ROOT="$HOME/.perl5${PERL_LOCAL_LIB_ROOT+:}${PERL_LOCAL_LIB_ROOT}"; export PERL_LOCAL_LIB_ROOT;
    PERL_MB_OPT="--install_base \"$HOME/.perl5\""; export PERL_MB_OPT;
    PERL_MM_OPT="INSTALL_BASE=$HOME/.perl5"; export PERL_MM_OPT;
    export MANPATH=$HOME/perl5/man:$MANPATH
fi

# Ruby

if [ -f "$HOME/.rvm/scripts/rvm" ] && ! qtype rvm; then
    . "$HOME/.rvm/scripts/rvm"
fi

# Bluetooth Files
if qtype bluetoothctl; then
    __add_to_path "$toolsDir/bin/topics/bluetooth"
fi
