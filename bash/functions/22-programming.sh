
__add_to_lib /usr/local/lib

# Only do make aliases for Linux systems.
# This is because MobaXterm is a jerk, and OSX does not have lscpu.
if __is_unix && ! __is_mac && qtype make lscpu; then
    # Detect the number of CPUs in the machine.
    __num_cores=$(lscpu | grep -m1 '^CPU(s):' | awk '{print $2}')

    # Construct a make alias that uses the maximum number of CPUs.
    alias make-max="make -j$__num_cores"
    # Construct a make alias that uses the half of our available number of CPUs.
    if [ $__num_cores -gt 1 ]; then
        alias make-medium="make -j$(($__num_cores/2))"
    else
        # Keep the alias available, even if we only have one core.
        alias make-medium=make
    fi
fi

alias format-code="format-code.sh .c .cpp .h .hpp"
