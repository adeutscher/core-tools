#/bin/bash

link="https://downloads.raspberrypi.org/raspbian_lite_latest"

#set -x

if [ -t 1 ]; then
  Colour_Bold="\033[1m"
  Colour_BIGreen="\033[1;92m"
  Colour_Off="\033[0m"
fi


get_raspbian(){
  download_dir=$(readlink -f "${1:-$(pwd)}")
  if [ -z "${download_dir}" ]; then
    printf "No download directory specified."
    exit 1
  elif ! [ -d "${download_dir}" ]; then
    printf "Not a valid directory: ${Colour_BIGreen}%s/${Colour_Off}\n" "${download_dir}"
    exit 1
  fi

  cd "${download_dir}"

  # Get the direct link used to download the image.
  # The "raspbian_latest" link goes through two redirects before it gets to the actual image link.
  zip_link="$(curl "${link}" -s | grep images\/ | cut -d \" -f 2)"
  file_name="${zip_link##*/}"
  file_name_img="${file_name%.*}.img"

  # Check to see if this file already exists. Don't bother re-downloading if it does.
  if [ -f "${file_name}" ]; then
    printf "File has already been downloaded: ${Colour_BIGreen}%s${Colour_Off}\n" "${file_name}"
    exit 0
  elif [ -f "${file_name_img}" ]; then
    # Raspbian names the zips the same as it does the image.
    printf "Image file is already preseent: ${Colour_BIGreen}%s${Colour_Off}\n" "${file_name_img}"
    exit 0
  fi

  # If we are still here, then we have not downloaded this ZIP before. Let's fix that.

  printf "Source: ${Colour_BIGreen}%s${Colour_Off}\n" "${zip_link}"
  printf "Destination: ${Colour_BIGreen}%s/%s${Colour_Off}\n" "${download_dir}" "${file_name}"

  if [ -t 1 ]; then
    # If we have a terminal, then there is a person behind the command.
    # Sleep briefly to make sure that they haven't mistakenly called this script.
    local sleep_time=10
    printf "You have ${Colour_Bold}%d${Colour_Off} seconds to abort.\n" "${sleep_time}"
    sleep "${sleep_time}" || return
  fi

  curl -L -o "$file_name" "$zip_link"

  # If you wanted to, you could unzip the archive here.
  # I don't do this because the machine that downloads the ZIP file isn't necessarily
  #   machine that needs to write the image.
}

get_raspbian "${1}"

