#!/bin/bash

# A lazy wrapper with some parameter checks around a simple UDP relay using nc.

do_forwarding(){
  local _bindPort="${1}"
  local _destAddress="${2}"
  local _destPort="${3}"

  if ! type nc 2> /dev/null >&2; then
    printf  "nc is not installed.\n" >&2
    local _err="$((${_err:-0}+1))"
  elif ! nc -h 2>&1 | grep -q nmap; then
    printf "Must use nmap-ncat for forwarding.\n" >&2
    local _err="$((${_err:-0}+1))"
  fi

  if [ -z "${3}" ]; then
    printf "Insufficient arguments.\n" >&2
    hexit 1
  fi

  if ! grep -Pq '^[0-9]+$' <<< "${_bindPort}"; then
    printf "Invalid bind port: %s\n" "${_bindPort}" >&2
    local _err="$((${_err:-0}+1))"
  fi

  if ! grep -Pq '^[0-9]+$' <<< "${_destPort}"; then
    printf "Invalid destination port: %s\n" "${_bindPort}" >&2
    local _err="$((${_err:-0}+1))"
  fi

  if ! grep -Pq '^(([0-9]){1,3}\.){3}([0-9]{1,3})$' <<< "${_destAddress}" && ! host "${_destAddress}" 2> /dev/null >&2; then
    printf "Invalid destination address: %s\n" "${_destAddress}"
    local _err="$((${_err:-0}+1))"
  fi

  (( ${_err:-0} )) && hexit 1

  printf "Relaying from UDP/%d to UDP/%d on %s\n" "${_bindPort}" "${_destPort}" "${_destAddress}"
  nc -luk -p "${_bindPort}" -c "nc -u \"${_destAddress}\" \"${_destPort}\""
}

hexit(){
    printf "Usage: %s bind-port dest-address dest-port\n" "$(basename "$(readlink -f "${0}")")" >&2
    exit ${1:-0}
}

do_forwarding ${@}
