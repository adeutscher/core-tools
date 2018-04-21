#!/bin/bash

####################################
# Task List Script                 #
# Original Author: /u/bikes-n-math #
####################################

# Default tasks file
CONKY_TASKS_FILE="${CONKY_TASKS_FILE:-${HOME}/tools/tasks.csv}"

IFS=$'\n'
CORNER="┏"
HAVE_TASKS=0

printf "\${color #FFA500}\${font Neuropolitical:size=16:bold}Tasks\${font}\${color}\${hr}\n"

# Abort if the target file does not exist.
if [ ! -f "${CONKY_TASKS_FILE}" ]; then
    printf "Taks file not found:\n  %s\n" "${CONKY_TASKS_FILE}"
    exit 0
fi

# Looking for tasks between two days ago and 15 days in the future.
for i in `seq -2 14`; do

  # Look for tasks matching this day, and sort by time (second column)
  TASK_CONTENTS="$(grep $(date -d "${i} day" +%y-%m-%d) "${CONKY_TASKS_FILE}" | sort -k2,1n)"

  if [ -z "${TASK_CONTENTS}" ]; then
    # Skip the listing of task-less days
    continue
  fi

  # HAVE_TASKS used to avoid printing the "no tasks" message after the days loop.
  HAVE_TASKS=1

  # Only print a header if a task was found.
  if [ ${i} -eq 0 ]; then
    # Current day
    DAY_COLOUR="color2"
  elif [ ${i} -gt 0 ]; then
    # Future
    if [ ${i} -lt 3 ]; then
    # Sometime in the next three days
      DAY_COLOUR="color4"
    else
      DAY_COLOUR="color0"
    fi
  else
    # ${i} -lt 0 -> Past
    DAY_COLOUR="color5"
  fi
  
  printf "\${color1}┏━━━━\${${DAY_COLOUR}}$(date -d "${i} day" "+%A, %B %d, %Y")\${color1}━━━━━━━━━━━━━━━━━━━━━━━\n"
  
  CORNER="┣"

  TASK_COUNT=$(wc -l <<< "${TASK_CONTENTS}")
  TASK_CURRENT=0

  while read WORD; do # Note: Loop input is at 'done'

    # Increment task
    TASK_CURRENT=$((TASK_CURRENT+1))

    # e.g. YYYY-MM-DD
    DATE="$(cut -d, -f 1 <<< "${WORD}")"
    # e.g. 01:22PM, 13:22
    TIME="$(date -d "$(cut -d, -f 2 <<< "${WORD}")" +"%I:%M%p")"
    # Task label
    TASK="$(cut -d, -f 3- <<< "${WORD}")"

    if [ -z "${TASK}" ]; then
      # No label text, incomplete line?
      continue
    fi

    # Unix timestamp of task
    SECS="$(date -d "${DATE} ${TIME}" +%s)"
    # Current Unix timestamp
    CURRENT="$(date +%s)"

    if [ "${TASK_CURRENT}" -eq "${TASK_COUNT}" ]; then
      CORNER="┗"
    fi

    printf "\${color1}${CORNER━}"

    TEST=0
    if grep -q -e 'test' -e 'exam' <<< "${TASK}"; then
      TEST=1
    fi

    BILL=0
    if grep -q 'bill' <<< "${TASK}"; then
      BILL=1
    fi

    HW=0
    if grep -q 'hw' <<< "${TASK}"; then
      HW=1
    fi

    GAP=$(( ${SECS} - ${CURRENT} ))

    # Determine time colouring.
    if [ ${GAP} -lt 600 ]; then
      # 600s = 10m
      printf "\${color6}"
    elif [ ${GAP} -lt 900 ]; then
      # 900s = 15m
      printf "\${color5}"
    elif [ ${GAP} -lt 1800 ]; then
      # 1800s = 30m
      printf "\${color4}"
    elif [ ${GAP} -lt 3600 ]; then
      # 3600s = 1h
      printf "\${color3}"
    else
      # >= 1hr
      printf "\${color2}"
    fi

    printf "%s \${color1}- " "${TIME}"
    #printf "$(echo ${WORD} | awk '{print ${2}}') \${color1}- "

    if [ ${HW} -eq 1 ]; then
        printf "\${color4}"
    fi

    if [ ${TEST} -eq 1 ]; then
        printf "\${color6}"
    fi

    # TODO: Consider re-thinking bill colouring logic
    if [ ${BILL} -eq 0 ]; then
        :
    elif [ ${i} -le 1 ]; then
      # Bill that is not the upcoming task, critical
      printf "\${color6}"
    elif [ ${i} -le 2 ]; then
      # Bill that is not the upcoming task, urgent
      printf "\${color5}"
    elif [ ${i} -le 4 ]; then
      # Bill on the near horizon, pressing
      printf "\${color4}"
    fi

    printf "${TASK}\n"
  done <<< "${TASK_CONTENTS}" # End TASK_CONTENTS loop.

  printf "${FILLER}\n"
  unset FILLER
done

if (( ! ${HAVE_TASKS} )); then
  printf "No upcoming tasks found.\n"
fi
