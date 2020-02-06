
This file contains reminders for transferring files across a network.

# nc

The `nc` command can be very useful for straightforward file transfers on a trusted network.

`nc` reads from standard input, so the basic transfer example below can be expanded upon on either end of the connection using piped commends. (e.g. `pv`, `gzip`, `gunzip`)

## Basic File Transfer

On the server receiving the file, to listen on TCP/5555:

```bash
nc -l 5555 > dst_file.dat
```

On the client sending the file to the above server (assuming an IP address of 10.20.30.40):

```bash
nc 10.20.30.40 5555 < src_file.dat
```

## Directory Transfer

On the server receiving the file, to listen on TCP/4444:

```bash
nc -l 4444 | tar x
```

On the client sending the directory to the above server (assuming an IP address of 10.20.30.40):

```bash
tar c . | nc 10.20.30.40 4444
```

# rsync

Basic `rsync`, using the `-a` switch to include a number of common switches:

```bash
rsync -a src/ dest/
```

Switches packaged in by the `-a` switch:

* `-r`: recurse into directories
* `-l`: copy symlinks as symlinks
* `-p`: preserve permissions
* `-t`: preserve modification times
* `-g`: preserve groups
* `-o`: preserve owner
* `-D`: preserve device files (super-user only), and preserve special files

Switches that cannot be used with `-a`:

* `-H`: preserve hard links
* `-A`: preserve ACLs
* `-X`: preserve extended attributes

Add the `--progress` switch to include a handy visual indicator for rsync jobs that you may want to observe: 

## File Paths

A reminder that `rsync` is particular about the trailing '/' in the source path. For comparison:

Syncing a source of `source/` and a destination of `dest/` will copy the contents of `source/` directly into `dest/` (e.g. `source/file.doc` becomes `dest/file.doc`):

```bash
rsync -av sourceFolder/ server:destinationFolder/
```

Syncing a source of `source` and a destination of `dest/` will create a copy of contents of source in `dest/` (e.g. `source/file.doc` becomes `dest/source/file.doc`).

```bash
rsync -av sourceFolder server:destinationFolder/
```

## Other Options

### Compression

To add compression to the trans, use the `--compress` or `-z` switch (these are synonymous).
