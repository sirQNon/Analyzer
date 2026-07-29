# SquashFS extended regular inode

Stage 14 supports SquashFS v4 extended regular-file inodes (type `9`).  The
layout follows the Linux SquashFS on-disk format (`fs/squashfs/squashfs_fs.h`)
and the SquashFS filesystem specification.

After the 16-byte common inode header, the fixed extended body is 40 bytes:

| Field | Encoding |
| --- | --- |
| `start_block` | `u64` |
| `file_size` | `u64` |
| `sparse` | `u64` |
| `nlink` | `u32` |
| `fragment` | `u32` |
| `offset` | `u32` |
| `xattr` | `u32` |

The complete fixed inode is therefore 56 bytes.  The 32-bit regular-file
block-list begins immediately after byte 56, and can cross decoded metadata
block boundaries.  Its number of entries follows the same full-block and
fragment-tail rules as a basic regular inode.  A zero stored-size entry is a
sparse logical-zero block.  Bit 24 marks an uncompressed stored block; other
reserved high bits are rejected.

`fragment == 0xffffffff` means no fragment.  Otherwise a non-zero final tail
is sliced from the indexed fragment block at `offset`.  An extended inode with
a fragment but no tail is rejected.  `xattr` is parsed and retained as typed
metadata; Stage 14 does not read the xattr table.

`read_basic_regular_file()` and `read_extended_regular_file()` use one private
assembly helper.  The helper receives explicit regular-file fields and the
block-list metadata reference, reads compressed/uncompressed/sparse full
blocks, then appends an optional fragment tail.  It verifies the exact final
`file_size`.  Fragment-table failures are re-raised as typed tail errors with
their original cause retained.

Tests cover deterministic parsing (including metadata-boundary reads), all
block forms, fragment-only and mixed files, typed error chaining, basic-reader
regression, and a UDM Pro ROOTFS traversal that dynamically locates a type-9
inode and verifies its assembled length.

Limitations: only Zstandard-compressed images are supported by this reader,
consistent with the existing image implementation; xattr data is not decoded.
