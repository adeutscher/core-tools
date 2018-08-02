
# A convenient place to put my getopts approach when operands are involved.
# Unlike other clipboard items, this will obviously need
#  a fair bit of customization per-implementation.

while [ -n "${1}" ]; do
  while getopts ":v" OPT $@; do
    # Handle switches up until we encounter a non-switch option.
    case "$OPT" in
      v)
        VERBOSE=1
        ;;
    esac
  done # getopts loop

  # Set ${1} to first operand, ${2} to second operands, etc.
  shift $((OPTIND - 1))
  while [ -n "${1}" ]; do
    # Break if the option began with a '-', going back to getopts phase.
    grep -q "^\-[^$]" <<< "${1}" && break

    # Do script-specific operand stuff here.

    shift # Shift to next variable.
  done # Operand ${1} loop.
done # Outer ${1} loop.
