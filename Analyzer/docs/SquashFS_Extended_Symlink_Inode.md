# SquashFS extended symlink inode

Stage 16 supports Linux SquashFS v4 `SQUASHFS_LSYMLINK_TYPE` (type 10), as
defined by `fs/squashfs/squashfs_fs.h` and read by `inode.c`/`symlink.c`.
The little-endian fixed inode is 28 bytes: the 16-byte base inode followed by
`<III>`: `nlink`, `symlink_size`, and `xattr`. The raw target begins immediately
after that fixed body; `xattr` is therefore before target bytes and is retained
without reading the xattr table.

The target is exactly `symlink_size` metadata bytes, has no format-added
trailing NUL, and may cross metadata-block boundaries. The reader retains the
existing UTF-8 string policy: malformed UTF-8 and truncated metadata raise
typed symlink errors. `read_basic_symlink()` and `read_extended_symlink()` use
one helper for the common target read/decode path.

No path resolver changes are required for this inode-reader stage. Tests cover
dispatch, fixed/body metadata-boundary reads, raw-length preservation, xattr
preservation, and basic-reader regression.
