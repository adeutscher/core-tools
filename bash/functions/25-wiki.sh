
# Functions for rendering MediaWiki pages
#   mwlib seems to be broken at the moment, so falling back to a convenient function for mw-render.

if type mw-render 2> /dev/null >&2; then

    wiki-pdf(){
        if [ -z "$1" ]; then
            echo "No page given..."
            return
        fi

        # Crude check to axe troublesome unicode characters.
        chars=$(python -c 'print u"\u0091\u0092\u00a0\u200E".encode("utf8")')
        page=$(echo $1 | sed 's/['"$chars"']//g')

        mw-render --config "https://wiki.domain.lan/w" --writer rl --output "$page.pdf" "$page"
    }
    
fi
