
if qtype curl; then

    # Weather technique courtesy of http://askubuntu.com/questions/390329/weather-from-terminal
    __weather_core(){
        if [ -n "$2" ]; then
            curl -s -L "$1" | awk -F\' '/acm_RecentLocationsCarousel\.push/{print "Weather for '$2' ("$2"): "$14", " $12 "° C" }' | head -n1
        fi
    }

    # Example of the test that we are parsing in __weather_core:
    #   acm_RecentLocationsCarousel.push({name:"New York, NY", daypart:'night', href:'/en/us/new-york-ny/10017/weather-forecast/349727', icon:'http://vortex.accuweather.com/adc2010/images/icons-numbered/07-m.png', bg:'s', temp:'16',  realfeel:'17',text:'Cloudy'});
    # Output parsed from this in __weather_core would look like: "Weather for New York (night): Cloudy, 16° C"

    # Default to Home
    alias weather=weather-Home

    weather-all(){
        for __function in $(compgen -A function weather- | sed '/weather-all/d'); do
           $__function
        done
        unset __function
    }

    weather-Home(){
        __weather_core "http://www.accuweather.com/en/ca/Home/v9r/weather-forecast/47168" "Home"
    }

    weather-vancouver(){
        __weather_core "http://www.accuweather.com/en/ca/vancouver/v5y/weather-forecast/53286" "Vancouver"
    }

fi # end curl check
