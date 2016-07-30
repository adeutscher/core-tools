#!/bin/bash

IFS=$'\n'

for i in `seq 0 13`
do
    if [ $i -eq 0 ]
    then
        printf "\${color1}┏━━━━\${color2}$(date "+%A %d %B %Y")\${color1}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    else
        printf "\${color1}┏━━━━\${color0}$(date -d "$i day" "+%A %d %B %Y")\${color1}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    fi
    
    TODO="$(grep `date -d "$i day" +%m/%d/%y` ~/Dropbox/data.dropbox/conky/todo.txt | sort -k2,1n)"
    
    for WORD in $TODO
    do
        
    DATE="$(echo $WORD | awk '{print $1}')"
    TIME="$(echo $WORD | awk '{print $2}')"
    TASK="$(echo $WORD | cut -c21-57)"
    SECS="$(date -d "$DATE $TIME" +%s)"
    CURRENT="$(date +%s)"
    
    printf "\${color1}┣━"
    
    echo "$WORD" | grep -e 'test' -e 'exam' &> /dev/null
    if [ $? -eq 0 ]
    then
        TEST=1
    else
        TEST=0
    fi
    
    echo "$WORD" | grep 'bill' &> /dev/null
    if [ $? -eq 0 ]
    then
        BILL=1
    else
        BILL=0
    fi
    
    echo "$WORD" | grep 'hw' &> /dev/null
    if [ $? -eq 0 ]
    then
        HW=1
    else
        HW=0
    fi
    
    GAP=$(( $SECS - $CURRENT ))
    
    if [ $GAP -lt -900 ]
    then
        printf "\${color1}"
    elif [ $GAP -lt 600 ]
    then
        printf "\${color6}"
    elif [ $GAP -lt 1800 ]
    then
        printf "\${color5}"
    elif [ $GAP -lt 3600 ]
    then
        printf "\${color4}"
    elif [ $GAP -lt 5400 ]
    then
        printf "\${color3}"
    else
        printf "\${color2}"
    fi           

    printf "$(echo $WORD | awk '{print $2}') \${color1}- "
    
    if [ $HW -eq 1 ]
    then
        printf "\${color4}"
    fi    
    
    if [ $TEST -eq 1 ]
    then
        printf "\${color6}"
    fi
    
    if [ $BILL -eq 0 ]
    then
        :
    elif [ $i -le 1 ]
    then
        printf "\${color6}"
    elif [ $i -le 2 ]
    then
        printf "\${color5}"
    elif [ $i -le 4 ]
    then
        printf "\${color4}"
    fi
  
    printf "$TASK\n"
    
    done
    
    printf "\n\n"
done
