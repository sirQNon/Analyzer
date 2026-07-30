# SquashFS XAttr ID table

Stage 18 reads only the xattr-ID infrastructure; it deliberately does not
parse xattr names or values.

`xattr_id_table_start` is `SQUASHFS_INVALID_BLK` when the optional table is
absent.  Otherwise it addresses `squashfs_xattr_id_table` (`<QII`): the
absolute xattr data-stream start, zero-based ID count, and an unused reserved
field.  A header is followed by an uncompressed `<Q` index of metadata-block
offsets ending exactly at `bytes_used`.

Each lazy `squashfs_xattr_id` record is `<QII`: an encoded metadata reference,
entry count, and list size.  Its reference decodes as `block = value >> 16`
and `offset = value & 0xffff`; physical metadata starts at
`xattr_table_start + block`.

Records are 16 bytes and metadata blocks are 8192 bytes.  Because 8192 is a
multiple of 16, records at offset 8176 end at the block boundary and the next
record starts in the next metadata block; no record crosses it.

The reader validates header/index bounds against `bytes_used`, exact index
size, strictly increasing metadata offsets and their permitted distances.
`SquashFSXAttrTableError` covers malformed table data and
`SquashFSXAttrIDError` covers explicit ID lookup/read errors; metadata failures
are preserved as `__cause__`.

Extended directory, regular, and symlink inodes retain their raw `xattr`
field and expose `xattr_id`: `0xffffffff` maps to `None`, while zero remains a
valid first ID.  Xattr lists are not read during inode parsing.

The immutable UDM Pro ROOTFS has a table: `xattr_id_table_start=609067212`,
`bytes_used=609067236`, data-stream start `609067154`, one ID, reserved value
115, and index offset `609067194`.  Names and values are deferred to Stage 19.
