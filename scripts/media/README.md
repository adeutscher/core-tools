
# Media Scripts

Scripts for working with audio/pictures/etc.

## scudder.sh

Script to share images over the network. An extension of Python's SimpleHTTPServer module.

Arguments:

* `-a address/range`: Network address or range to whitelist.
* `-A allow-list-file`: File containing addresses or ranges to whitelist.
* `-d address/range`: Network address or range to blacklist. Blacklists override conflicting whitelists.
* `-D allow-list-file`: File containing addresses or ranges to blacklist. Blacklists override conflicting whitelists.
* `-b bind`: Network address to bind to (default: `0.0.0.0`).
* `-h`: Print a help menu and exit.
* `-p port`: Port to listen on (default: `8080`).
* `-r`: Display items in reverse order.
* `-t`: Sort items by modification time instead of alphabetically.
* `--user user`: Required username.
* `--password password`: Required password.
* `--prompt`: Password prompt text.

## simple-background-formatter.sh

This script was made because I had a sizable backlog of small images with uniform backgrounds that would make for fun backgrounds.

The basic steps to do this are:

1. Make a blank canvas with a uniform colour and made to the size of your desired resolution.
2. Resize your subject image if desired.
3. Place your resized image on top of your canvas.

I thought that the above steps were super-tedious, especially with positioning trial-and-error.
Because of this, I made this script to condense everything that I needed down to one line.

Usage:

    ./simple-background-formatter.sh -i in-file -o out-file [-c canvas/colour] [-C|-L|-R] [-D|-U] [-H] [-h canvas-height] [-w canvas-width] [-x pos-x] [-y pos-y]

Arguments:

* `-i input-file`: Input image to read from.
* `-o output-file`: Input image to write to.
* `-C`: Center the image horizontally.
* `-L`: Place the image horizontally on the left of the canvas.
* `-R`: Place the image horizontally on the right of the canvas.
* `-D`: Place the image vertically on the bottom of the canvas.
* `-U`: Place the image vertically on the top of the canvas.
* `-h canvas-height`: Height of canvas image.
* `-w canvas-width`: Width of canvas image.
* `-x pos-x`: X offset of image on the canvas.
* `-y pos-y`: Y offset of image on the canvas.
* `-c canvas`: Canvas colour/image. Can either be a hex code or another image.
  * If no canvas is provided, then the script will attempt to detect it from the corners of the input image.
* `-s scale`: Scale of input image (e.g. 50%)
