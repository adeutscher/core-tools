# Functions working with files.

###################
# File Encryption #
###################

## Password ##

# Encrypt piped data with a password.
# Also pipe through gzip to apply some compression.
alias aes-encrypt-password="gzip | openssl enc -aes-256-cbc -a -salt"

# Decrypt piped data that has that has been encrypted with a passwords.
# Assume that piped data was encrypted with counterpart aes-encrypt-password alias, and pipe openssl output through gunzip
alias aes-ecrypt-password="openssl enc -d -aes-256-cbc -a -salt | gunzip"

###################
# File Management #
###################

# Default options for shred
alias shred='ionice -c3 /usr/bin/shred -fuzv'

# zipf: quick alias to create a ZIP archive of a file or folder
zipf () { zip -r "$1".zip "$1" ; }

# find the 5 largest files in the current directory.
alias findbig="find . -type f -exec ls -s {} \; | sort -n -r | head -5"

# "Sort by size" to display in list the files in the current directory, sorted by their size on disk.
sbs() { du -b --max-depth 1 | sort -nr | perl -pe 's{([0-9]+)}{sprintf "%.1f%s", $1>=2**30? ($1/2**30, "G"): $1>=2**20? ($1/2**20, "M"): $1>=2**10? ($1/2**10, "K"): ($1, "")}e';}


# ex - archive extractor   # command line archive extractor, came with Manjaro
# usage: ex <file>
ex () {
    if [[ -f $1 ]] ; then
      case $1 in
        *.tar.bz2)   tar xjf $1     ;;
        *.tar.gz)    tar xzf $1     ;;
        *.tar.xz)    tar xJf $1     ;;
        *.bz2)       bunzip2 $1     ;;
        *.rar)       unrar e $1     ;;
        *.gz)        gunzip $1      ;;
        *.tar)       tar xf $1      ;;
        *.tbz2)      tar xjf $1     ;;
        *.tgz)       tar xzf $1     ;;
        *.zip)       unzip "$1"       ;;
        *.Z)         uncompress $1  ;;
        *.7z)        7z x $1        ;;
        *)     echo "'$1' cannot be extracted via ex()" ;;
         esac
     else
         echo "'$1' is not a valid file"
     fi
}

partsize(){
    # Some file transfer methods (e.g. transmission-cli)
    #     store information in files that are padded with null characters
    #     up to the size of the full file.
    # This lets them easily jump around and fill in information that doesn't
    #     necessarily build in a straight line from beginning to end, but it also
    #     meddles with our ability to use commands like ls/du to tell how much information has been downloaded.
    if [ -z "$1" ]; then
        error "No file paths provided."
        return 1
    fi

    while [ -n "$1" ]; do
        local __file="$1"
        if [ ! -f "$1" ]; then
            error "$(printf "File \"${Colour_FilePath}%s${Colour_Off}\" does not exist or is not a file." "$1")"
            local return_num=$((${return_num:-0}+1))
        else
            local __real_size="$(tr -d '\000' < "$__file" | wc -c)"
            local __target_size="$(stat --printf="%s" "$__file")"
            # Get the percentage and lop off the last 2 digits.
            # This function keeps its options open about how to go about getting the percentage.
            if qtype bc; then
                local __percent="$(bc <<< "scale=4; ($__real_size / $__target_size) * 100" | grep -Po "^\d*\.\d{0,2}")"
            elif qtype perl; then
                local __percent="$(perl <<< "printf (($__real_size/$__target_size)*100)" 2> /dev/null | grep -Po "^\d*\.\d{0,2}")"
            elif qtype python; then
                local __percent="$(python -c "print((float($__real_size)/float($__target_size)) * 100)" 2> /dev/null | grep -Po "^\d*\.\d{0,2}")"
            fi

            if [ -n "$__percent" ]; then
                notice "$(printf "Non-null characters in ${Colour_FilePath}%s${Colour_Off}: ${Colour_Bold}%d${Colour_Off} / ${Colour_Bold}%d${Colour_Off} (${Colour_Bold}%s%%${Colour_Off})" "$__file" "$__real_size" "$__target_size" "$__percent")"
            else
                notice "$(printf "Non-null characters in ${Colour_FilePath}%s${Colour_Off}: ${Colour_Bold}%d${Colour_Off} / ${Colour_Bold}%d${Colour_Off}" "$__file" "$__real_size" "$__target_size")"
            fi
        fi
        shift
    done

    return ${return_num:-0}
}

deadlinks(){
    if [ -z "$1" ]; then
        error "No directories provided."
        return 1
    fi

    while [ -n "$1" ]; do
        if [ -d "$1" ]; then
            notice "$(printf "Checking in $Colour_FilePath%s$Colour_Off for dead symbolic links..."  "$1")"
            find "$1" -xtype l | xargs-i printf "    {}\n"
        else
            error "$(printf "$Colour_FilePath%s$Colour_Off does not seem to be a directory..." "$1")"
        fi

        shift
    done
}
