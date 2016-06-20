
if qtype perl; then
    perl-local-setup(){
        local perlDir=$HOME/.perl5
        
        perl -I $perlDir/lib/perl5 -Mlocal::lib=$perlDir 2> /dev/null >&2
        mkdir -p $perlDir/lib/perl5 $perlDir/bin

        # For the moment, storing the ~300KB cpanm script as-needed in our perl directory instead of using up space in every tools checkout.
        if [ ! -f "$perlDir/bin/cpanm" ]; then
            notice "$(printf "Downloading $Colour_Command%s$Colour_Off" "cpanm")"
            if mkdir -p $perlDir/bin && curl -L https://raw.githubusercontent.com/miyagawa/cpanminus/master/cpanm > /tmp/cpanm; then
                mv /tmp/cpanm $perlDir/bin/
                chmod 700 $perlDir/bin/cpanm
            else
                error "$(printf "Failed to grab $Colour_Command%s$Colour_Off..." "cpanm")"
            fi
        fi
    }

    # loda output from local::lib if appropriate
    if [ -d "$HOME/.perl5" ]; then
        __add_to_path "$HOME/.perl5/bin"; export PATH;
        PERL5LIB="$HOME/.perl5/lib/perl5${PERL5LIB+:}${PERL5LIB}"; export PERL5LIB;
        PERL_LOCAL_LIB_ROOT="$HOME/.perl5${PERL_LOCAL_LIB_ROOT+:}${PERL_LOCAL_LIB_ROOT}"; export PERL_LOCAL_LIB_ROOT;
        PERL_MB_OPT="--install_base \"$HOME/.perl5\""; export PERL_MB_OPT;
        PERL_MM_OPT="INSTALL_BASE=$HOME/.perl5"; export PERL_MM_OPT;
        export MANPATH=$HOME/perl5/man:$MANPATH
    fi
fi
