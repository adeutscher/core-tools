#/bin/bash

perlDir=$HOME/.perl5

perl -I $perlDir/lib/perl5 -M::lib=$perlDir 2> /dev/null >&2
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