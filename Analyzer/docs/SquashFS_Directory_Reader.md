# SquashFS v4 directory reader

## Research facts

Linux `squashfs_readdir()` reads a `squashfs_dir_header`, computes
`dir_count = le32_to_cpu(dirh.count) + 1`, then reads exactly that many
`squashfs_dir_entry` structures. For each entry it computes the final inode
number as:

```c
le32_to_cpu(dirh.inode_number) +
    ((short) le16_to_cpu(dire->inode_number))
```

After the entries in one header group, the next bytes are another directory
header. The reader repeats this while its logical directory position is less
than the directory VFS `i_size`.

Linux does not store `.` and `..` in directory metadata. It synthesizes them
and starts the logical directory position at `3`: one byte for `.` and two
bytes for `..`. The directory inode's `file_size` is assigned to VFS `i_size`.
Consequently, the physical on-disk bytes to parse are:

```text
basic_directory_inode.file_size - 3
```

The reader must stop when it has consumed exactly this quantity. It must not
read bytes that follow the directory stream in the same metadata block.

## UDM Pro rootfs verification

Root basic directory inode values:

```text
start_block = 395215
offset      = 3260
file_size   = 226
```

The physical root directory stream therefore occupies `226 - 3 = 223` bytes.
It starts at directory-table metadata location `<0x607CF, 3260>` and ends at
decompressed offset `3483`. The next three bytes are not parsed as directory
records.

The real root stream contains seven directory headers and 13 records:

```text
bin, data, etc, home, lib, lib64, media, mnt, opt, root, sbin, usr, var
```

The first record is:

```text
header base inode = 1
entry delta       = 0
entry type        = 1
name              = b"bin"
offset            = 3958
absolute inode    = 1
```

The final record is `b"var"`, absolute inode `40888`, type `1`, offset `2251`.
The parser cursor finishes at `3483`, equal to the physical end of the stream.

## Architecture

`read_directory(metadata_stream, basic_directory_inode)` is the only Stage 7
public API. It creates a metadata reference from `start_block` and `offset`,
reads exactly the physical directory-stream length through the existing
`SquashFSMetadataStream`, and parses its local byte cursor with the existing
directory header and entry parsers.

Each record is an immutable `SquashFSDirectoryRecord`:

```text
inode_number, inode_type, name, offset
```

Names remain `bytes`. The function does not resolve an inode, traverse paths,
iterate recursively, or read another directory.

## Sources

- Linux `dir.c`, `squashfs_readdir()`:
  <https://codebrowser.dev/linux/linux/fs/squashfs/dir.c.html>
- Linux `squashfs_fs.h`, directory structures:
  <https://codebrowser.dev/linux/linux/fs/squashfs/squashfs_fs.h.html>
- Linux documentation, *Squashfs 4.0 Filesystem*, directory metadata model:
  <https://www.kernel.org/doc/html/latest/filesystems/squashfs.html>
