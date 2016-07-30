
Conky configuration found online, written by /u/bikes-n-math (magyar on Arch BBS). I especially like the To-Do list.

In order to implement the ToDo list on my system, I would probably need to also run separate conky instances like the author does, since it's become too easy to run out of real estate on my own conky on systems with a lower monitor resolution. *Maybe* if I only printed the top 5 to-do items?

Link to the full configuration in action: http://i.imgur.com/uSWHP93.jpg
Link to the author's Reddit post: https://www.reddit.com/r/Conkyporn/comments/3pccex/my_bash_driven_colorcoded_conky/
Link to the author's Arch BBS post: https://bbs.archlinux.org/viewtopic.php?pid=1571847#p1571847

Silly reminder: These scripts are expected to be in ~/.conky/

Reminder of configuration purposes location:

conky1.conf: Bottom-left display of OS information, disk layout, and processes
conky2.conf: Bottom-left-ish display of memory/file systems
conky5.conf: ToDo list

Missing from this configuration posting are the process/network-info and calendar configs (conky3.conf and conky4.conf). I don't think that it would be the end of the world to reproduce these if I wanted to. I think calendar section is probably a small filter over the output of the cal command, similar to my own tmux script being a cut/sed/perl wrapping over normal tmux output.
