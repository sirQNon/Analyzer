# SquashFS extended directory inode

Stage 15 adds SquashFS v4 extended-directory (`SQUASHFS_LDIR_TYPE`, type 8)
support.  The format is defined by Linux `fs/squashfs/squashfs_fs.h`; inode
reading follows `inode.c`, sequential directory listing follows `dir.c`, and
name indexes are used by lookup code in `namei.c`.

The fixed inode is little-endian and is 40 bytes including the 16-byte base
inode.  Its 24-byte body is `<IIIIHHI>`: `nlink`, `file_size`, `start_block`,
`parent_inode`, `i_count`, `offset`, and `xattr`.  `start_block` and `offset`
locate the directory-table metadata stream. `file_size` includes the three
directory-position bytes, so the sequential reader consumes `file_size - 3`.
`xattr` is preserved without reading the xattr table.

Immediately after the fixed inode are `i_count` directory-index records. Each
record begins `<III>` (`index`, `start_block`, `size`) followed by `size + 1`
raw name bytes.  Indexes support lookup positioning; sequential listing reads
the ordinary directory stream and does not require them.

`read_directory()` is the common public listing API for basic and extended
directory inode objects. `read_directory_indexes()` separately returns typed
index records and the metadata position after the index area. Metadata reads
are boundary-safe through `SquashFSMetadataStream`.

Errors remain in the existing directory hierarchy: malformed indexes raise
`SquashFSDirectoryIndexError`; malformed stream locations and directory data
raise directory reader errors. Basic directory behavior remains unchanged.

Limitations: Stage 15 does not decode xattrs, implement extended symlinks, or
redesign path resolution/extraction. Directory indexes are parsed, but are not
needed for sequential directory listing.
