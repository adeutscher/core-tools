#!/bin/bash

# A lazy wrapper with some parameter checks around a simple TCP relay using nc.

do_forwarding(){
  local _bindPort="$1"
  local _destAddress="$2"
  local _destPort="$3"

  if ! type nc 2> /dev/null >&2; then
    printf  "nc is not installed.\n" >&2
    local _err="$((${_err:-0}+1))"
  fi

  if [ -z "$3" ]; then
    printf "Insufficient arguments."
    hexit 1
  fi

  if ! grep -Pq '^[0-9]+$' <<< "$_bindPort"; then
    printf "Invalid bind port: %s\n" "$_bindPort" >&2
    local _err="$((${_err:-0}+1))"
  fi

  if ! grep -Pq '^[0-9]+$' <<< "$_destPort"; then
    printf "Invalid destination port: %s\n" "$_bindPort" >&2
    local _err="$((${_err:-0}+1))"
  fi

  if ! grep -Pq '^(([0-9]){1,3}\.){3}([0-9]{1,3})$' <<< "${_destAddress}" && ! host "${_destAddress}" 2> /dev/null >&2; then
    printf "Invalid destination address: %s\n" "${_destAddress}"
    local _err="$((${_err:-0}+1))"
  fi

  (( ${_err:-0} )) && hexit 1

  printf "Relaying from TCP/%d to TCP/%d on %s\n" "${_bindPort}" "${_destPort}" "${_destAddress}"
  nc -lk -p "${_bindPort}" -c "nc \"${_destAddress}\" \"${_destPort}\""
}

hexit(){
    printf "Usage: %s bind-port dest-address dest-port\n" "$(basename "$(readlink -f "$0")")" >&2
    exit ${1:-0}
}

do_forwarding $@
