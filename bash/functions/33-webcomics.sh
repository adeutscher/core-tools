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

    # Girl Genius
    comic-gg-day(){

        local dateString=$(curl -s --user-agent "Clockwork Penguin Legion" "http://girlgeniusonline.com/comic.php" 2> /dev/null | strings | grep -o '<div id="datestring">[^<]*</div>' | head -n1 | sed 's/<[^>]*>//g')

        if [ -n "$dateString" ]; then
            success "$(printf "Current Girl Genius webcomic was published ${Colour_Bold}%s${Colour_Off}" "$dateString")"
        else
            error "Unable to get Girl Genius comic data..."
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
        local rssContents="$(curl -s --user-agent "Orbital Pizza Delivery Service" "http://feed43.com/questionablecontent.xml" 2> /dev/null | grep -m1 -A3 item)"
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
        local latestTitle=$(curl -s --user-agent "RaptorOS (SXMgdGhlcmUgYSByYXB0b3IgcmlnaHQgYmVoaW5kIHlvdT8K)" "http://what-if.xkcd.com/" 2> /dev/null | head -n9 | grep -m1 title| cut -d'<' -f 2 | cut -d'>' -f 2 )

        if [ -n "$latestTitle" ]; then
            success "$(printf "Latest XKCD \"What If?\" is: ${Colour_Bold}%s${Colour_Off}" "$latestTitle.")"
        else
            error "Unable to get XKCD's \"What If?\" title data..."
        fi

    }

    # Dragonball Abridged. Not actually a webcomic, but I don't have a better place for the function and it performs the same commands.
    comic-dbza-episode(){
        # Note: The sed before the egrep will strip out all special characters. Could especially backfire with a legitimate '&amp;'.
        local latest="$(curl -s --user-agent "Muffin Button" "http://teamfourstar.com/series/dragonball-z-abridged/" 2> /dev/null | grep -m1 archivetitle | sed 's/\&[^;]*;//g' | egrep -o '>D(ragonball|BZ)[^<&]*' | cut -d' ' -f4- | sed -e 's/^[ \t]*//' |  sed -e 's/[ \t]*$//')"

        # Attempt to parse out the progress of the next episode.
        local progressState="$(curl -s --user-agent "Makankōsappō" "http://teamfourstar.com/" | grep -m1 progressmeter | cut -d'"' -f 4 | cut -d'-' -f2)"
        case "$progressState" in
        1)
            __progress="Writing (8%)"
            ;;
        2)
            __progress="Writing (17%)"
            ;;
        3)
            __progress="Writing (25%)"
            ;;
        4)
            __progress="Writing (33%)"
            ;;
        5)
            __progress="Recording (42%)"
            ;;
        6)
            __progress="Recording (50%)"
            ;;
        7)
            __progress="Recording (58%)"
            ;;
        8)
            __progress="Recording (67%)"
            ;;
        9)
            __progress="Editing (75%)"
            ;;
        10)
            __progress="Editing (83%)"
            ;;
        11)
            __progress="Editing (92%)"
            ;;
        12)
            __progress="Editing (99%)"
            ;;
        13)
            __progress="Complete!"
            ;;
        esac

        if [ -n "$latest" ]; then
            success "$(printf "The most recent Dragonball Abridged episode is \""${Colour_Bold}%s${Colour_Off} "$latest")\"."

            if [ -n "$__progress" ]; then
                success "$(printf "\tProgress on next Dragonball Abridged episode: ${Colour_Bold}%s${Colour_Off}" "$__progress")"
            fi
            unset __progress
        else
            error "Unable to get Team FourStar episode listings..."
        fi
    }

fi # end curl check
