# SquashFS inode lookup table

Linux calls this on-disk feature the inode lookup table. Export/NFS code uses
it to map an inode number to an on-disk inode reference; it is not a separate
export-entry format. The source is Linux `fs/squashfs/export.c`,
`squashfs_fs.h`, and `super.c`.

`lookup_table_start` is the superblock field. `SQUASHFS_INVALID_BLK` means the
optional table is absent. A logical entry is one little-endian `u64`; for inode
number `n`, its index is `n - 1`, and the value decodes as `block = value >>
16`, `offset = value & 0xffff`.

Logical entries are packed into compressed metadata blocks. The uncompressed
index at `lookup_table_start` contains absolute `u64` offsets to these blocks.
The block count is `ceil(inode_count * 8 / 8192)`. The reader validates the
index size against the ID-table boundary, ordered offsets, image bounds, and
the maximum metadata-block distance before lazily reading an individual entry.

Public APIs are `read_inode_lookup_table`, `read_inode_lookup_entry`, and
`resolve_inode_number`. The last delegates typed inode parsing to the existing
dispatcher. Absent lookup tables are valid for discovery; an explicit lookup
raises a typed error. This stage does not implement NFS, caching, xattrs, or
write support.

Because entries are eight bytes and SquashFS metadata blocks are 8192 bytes,
every entry is naturally aligned and no individual entry can physically cross
a metadata-block boundary. Tests cover first/middle/last entries, the first
entry in a later metadata block, range errors, table boundaries, immutable
results, and real ROOTFS lookup/resolution.
