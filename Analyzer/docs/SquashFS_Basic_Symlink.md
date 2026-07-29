# SquashFS v4 Basic Symbolic Link Reader

## Scope

Stage 11 reads `SQUASHFS_SYMLINK_TYPE` (type `3`) inodes and returns their
targets as UTF-8 `str` values.  Extended symbolic-link inodes are not
supported.

## On-disk layout

The basic symbolic-link inode starts with the 16-byte common
`squashfs_base_inode`, followed by two little-endian `__le32` fields:

| Offset in inode | Field | Size |
| ---: | --- | ---: |
| 16 | `nlink` | 4 |
| 20 | `symlink_size` | 4 |
| 24 | `symlink[]` | `symlink_size` bytes |

`symlink[]` is stored immediately after the fixed 24-byte inode.  It is inode
metadata, not a file-data block and has no compression header of its own.

## Reader algorithm

`read_inode()` reads the common header and dispatches type `3` to the typed
basic-symlink body parser.  `read_basic_symlink(metadata_stream, inode)` then:

1. verifies that the typed inode is a basic symbolic link;
2. advances from the inode reference by the fixed 24-byte inode size in
   decompressed metadata-byte space;
3. reads exactly `symlink_size` target bytes, including across metadata blocks;
4. decodes the bytes as UTF-8 and returns the resulting `str`.

## Errors

`SquashFSSymlinkError` is raised when the target length cannot be read from the
metadata stream, the typed inode is not a basic symbolic link, or the target is
not valid UTF-8.  Fixed inode/header failures continue to use the existing
typed-inode and metadata-stream errors.

## Stage 11 limitations

This stage does not implement extended symlink inodes, fragments, hardlink
resolution, path traversal through symlinks, or recursive symlink resolution.

## Sources

* Linux `fs/squashfs/squashfs_fs.h`: `SQUASHFS_SYMLINK_TYPE` and
  `struct squashfs_symlink_inode`.
  <https://codebrowser.dev/linux/linux/fs/squashfs/squashfs_fs.h.html>
