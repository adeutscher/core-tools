
__toolCount=$((${__toolCount:-0}+1))

if [ ${__toolCount:-0} -gt 1 ]; then
    warning "It looks like core tools are installed twice on this system..."
fi
