
# Set LD_LIBRARY_PATH for compiled libraries.
if [ "$(__strlen "$LD_LIBRARY_PATH")" -gt 1 ] && \
  ! grep -q "\/usr\/local\/lib" <<< "$LD_LIBRARY_PATH"; then
    # Later note: I'm not sure why I used 'expr' instead of just [ -n ]. Will test later.
    # LD_LIBRARY_PATH has content.
    # Make sure that /usr/local/lib is not already in the path.
    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
else
    export LD_LIBRARY_PATH=/usr/local/lib
fi

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
