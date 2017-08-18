######################
# Webcomic Functions #
######################

# Only load these functions if curl is available
if qtype curl; then

    # Run all comic-checking functions
    comic-check-all(){
       # Look through every comic function, excluding this one.
       for __function in $(compgen -A function comic- | sed '/comic-check-all/d'); do
           $__function
       done
       unset __function
    }

    # A set of functions for web-comics.
    #  Mostly for discreetly checking for updates on a comic that
    #      does not update like clockwork for one reason or another.
    #      Alternately, I'm not properly aware of the schedule or am just impatient.

    comic-erma(){
        local __contents="$(curl -s "https://tapas.io/series/erma")"

        local title="$(grep -m1 data-episode-title <<< "$__contents" | cut -d '"' -f 2 | sed 's/^Erma\- //')"

        if [ -n "$title" ]; then
            success "$(printf "Current Erma comic is ${Colour_Bold}%s${Colour_Off}" "$title")"
        else
            error "Unable to get Erma comic data..."
        fi
    }

    # Girl Genius
    comic-gg-day(){

        local dateString=$(curl -s --user-agent "Clockwork Penguin Legion" "http://girlgeniusonline.com/comic.php" 2> /dev/null | strings | grep -o '<div id="datestring">[^<]*</div>' | head -n1 | sed 's/<[^>]*>//g')

        if [ -n "$dateString" ]; then
            success "$(printf "Current Girl Genius webcomic was published ${Colour_Bold}%s${Colour_Off}" "$dateString")"
        else
            error "Unable to get Girl Genius comic data..."
        fi

    }

    # Maddy Scientist
    comic-maddy-scientist(){
        local __contents="$(curl -s "https://tapas.io/series/maddyscientist")"

        local title="$(grep -m1 data-episode-title <<< "$__contents" | cut -d '"' -f 2)"

        if [ -n "$title" ]; then
            success "$(printf "Current Maddy Scientist comic is ${Colour_Bold}#%s${Colour_Off}" "$title")"
        else
            error "Unable to get Maddy Scientist comic data..."
        fi
    }

    # Order of the Stick
    comic-oots-issue(){

        local latestTitle="$(curl -s --user-agent "Seer-o-matic" "http://www.giantitp.com/comics/oots.rss" 2> /dev/null | grep -A4 -m1 '<item>' | grep title | cut -d'>' -f2 | cut -d'<' -f1)"
        # Example title: "1011: Red Means Stop"

        if [ -n "$latestTitle" ]; then
            success "$(printf "Current Order of the Stick comic is ${Colour_Bold}#%s${Colour_Off}" "$latestTitle")"
        else
            error "Unable to get Order of the Stick comic data..."
        fi

    }

    # Questionable Content
    comic-qc-issue(){

        # Get RSS feed. Only need the relatively small number of lines.
        #   The -s switch on curl obscures the error message when head cuts the connection.
        # Switched to feed43 service in r666.
        local rssContents="$(curl -s --user-agent "Orbital Pizza Delivery Service" "https://feed43.com/questionablecontent.xml" 2> /dev/null | grep -m1 -A3 item)"
        local title="$(grep -m1 title <<< "$rssContents" | cut -d'>' -f2 | cut -d'<' -f1 | cut -d' ' -f 2-)"

        if [ -n "$title" ]; then
            success "$(printf "Current Questionable Content comic is #${Colour_Bold}%s${Colour_Off}" "${title}")"
        else
            error "Unable to get Questionable Content comic data..."
        fi

    }

    # XKCD's "What If?"
    comic-whatif(){

        #   The -s switch on curl obscures the error message when head cuts the connection.
        local latestTitle=$(curl -s --user-agent "RaptorOS (SXMgdGhlcmUgYSByYXB0b3IgcmlnaHQgYmVoaW5kIHlvdT8K)" "https://what-if.xkcd.com/" 2> /dev/null | head -n9 | grep -m1 title| cut -d'<' -f 2 | cut -d'>' -f 2 )

        if [ -n "$latestTitle" ]; then
            success "$(printf "Latest XKCD \"What If?\" is: ${Colour_Bold}%s${Colour_Off}" "$latestTitle.")"
        else
            error "Unable to get XKCD's \"What If?\" title data..."
        fi

    }

fi # end curl check
