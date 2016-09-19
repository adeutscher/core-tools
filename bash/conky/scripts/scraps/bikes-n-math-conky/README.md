# /u/bikes-n-math's Conky

Conky configuration found online, written by **/u/bikes-n-math** (**magyar** on Arch BBS). I especially like the To-Do list feature.

In order to implement the ToDo list on my system, I would probably need to also run separate conky instances like the author does, since it's become too easy to run out of real estate on my own configuration on systems with a lower monitor resolution. This would mean a revision of how my startup script manages things. Speculation: *Maybe* I could run it on the same configuration if I only printed the top 5 to-do items?

## Links

Useful links for this setup:

* [Screenshot of full configuration in action](http://i.imgur.com/uSWHP93.jpg)
* [Author's Reddit post](https://www.reddit.com/r/Conkyporn/comments/3pccex/my_bash_driven_colorcoded_conky/)
* [Author's Arch BBS post](https://bbs.archlinux.org/viewtopic.php?pid=1571847#p1571847)

## Files

Silly reminder: As-is, these scripts are expected to be in `~/.conky/`

Reminders of configuration purposes location:

* `conky1.conf`: Bottom-left display of OS information, disk layout, and processes
* `conky2.conf`: Bottom-left-ish display of memory/file systems
* `conky5.conf`: ToDo list feature

Missing from this configuration posting are the process/network-info and calendar configs (`conky3.conf` and `conky4.conf`). I don't think that it would be the end of the world to reproduce these if I wanted to. I think calendar section is probably a small filter over the output of the `cal` command, similar to my own `tmux` script being a `cut`/`sed`/`perl` wrapping over normal `tmux` output.
