#!/bin/bash

cd "$(dirname "${0}")"
../system/update_dotfile.py -d "$(pwd)" -c blocks/block-config.json
