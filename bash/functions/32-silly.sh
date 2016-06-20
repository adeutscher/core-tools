
#########
# Silly #
#########

alias ffs='sudo'

# Only load on Ubuntu/Debian
if qtype apt-get && [ -f "/etc/debian_version" ]; then
    alias batman='sudo apt-get update'
    alias robin='sudo apt-get upgrade'
fi

# Create a randomly-generated maze.
# May or may not be possible to "solve".
alias maze='while true; do (( $RANDOM % 2 )) && echo -n ╱ || echo -n ╲; sleep 0.05; done'
alias maze-rainbow='while true; do (( RANDOM % 2 )) && echo -ne "\e[3$(( $RANDOM % 8 ))m╱" || echo -n ╲; sleep .05; done'

# Make you look all busy and fancy in the eyes of non-technical people.
alias busy='cat /dev/urandom | hexdump -C | grep "ca fe"'

# Only load if curl is present
if qtype curl; then

    # What-The-Commit is a site that has random silly commit quotes.
    wtc(){
      curl -s "http://whatthecommit.com/" | grep '<div id="content">' -A 1 | tail -n 1 | sed 's/<p>//'
    }

    # Constantly print out wtc quotes.
    wtc-stream(){
      while wtc; do sleep 5; done
    }

fi # end curl check

# Silly telnet movies.
if qtype telnet; then
    alias telnet-nyan="telnet nyancat.dakko.us; reset"
    alias telnet-sw="telnet towel.blinkenlights.nl; reset"
fi
