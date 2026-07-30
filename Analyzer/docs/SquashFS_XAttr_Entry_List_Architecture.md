# SquashFS XAttr Entry List Architecture

## Confirmed Linux Format Facts

Linux `fs/squashfs/squashfs_fs.h` defines `struct squashfs_xattr_entry` as
little-endian `<HH>`: `type`, then name `size`, followed immediately by that
many name bytes.  `struct squashfs_xattr_val` is little-endian `<I>` `vsize`,
followed by value bytes.  These are byte-packed; no alignment or terminator is
stored.  Consequently zero-length names and values are structurally valid.
The on-disk name length is an unsigned 16-bit value (maximum 65535) and value
length is unsigned 32-bit (maximum 4294967295); Analyzer must additionally
reject values that cannot be read within the declared list size or safely
represented by its metadata reader.

`SQUASHFS_XATTR_PREFIX_MASK` is `0xff`; known prefixes are
`SQUASHFS_XATTR_USER` (0), `SQUASHFS_XATTR_TRUSTED` (1), and
`SQUASHFS_XATTR_SECURITY` (2), mapped by `xattr.c` to `user.`, `trusted.`, and
`security.`.  `SQUASHFS_XATTR_VALUE_OOL` is bit `0x100`.  Unknown namespace
or other unrecognised type bits are ignored by Linux's `squashfs_xattr_handler`.

`squashfs_xattr_lookup` in `xattr_id.c` maps a zero-based inode ID into
`squashfs_xattr_id`: its xattr metadata reference, `count`, and `size`.
`xattr.c` iterates exactly `count` entries.  For every entry it reads header,
name, value header, and then `vsize` bytes.  Metadata reads are allowed to span
packed compressed or uncompressed 8K blocks.

For an inline type, those `vsize` bytes are the value.  For OOL, `xattr.c`
reads the list value header and then an eight-byte little-endian metadata
reference; it follows that reference and reads another value header and value.
Stage 19 will retain the list-side `vsize` and the raw u64 reference, but will
not dereference it.

Linux propagates failed metadata reads through negative error returns.  It
rejects an invalid ID with `-EINVAL`; missing table is `-EOPNOTSUPP`.  The ID
table reader rejects zero IDs and requires its computed index size to end
exactly at `bytes_used`.

Sources: Linux `fs/squashfs/squashfs_fs.h` symbols
`squashfs_xattr_entry`, `squashfs_xattr_val`, `SQUASHFS_XATTR_*`; Linux
`fs/squashfs/xattr.c` functions `squashfs_listxattr`, `squashfs_xattr_get`,
`squashfs_xattr_handler`; Linux `fs/squashfs/xattr_id.c`
`squashfs_xattr_lookup` and `squashfs_read_xattr_id_table`.

## Implemented Analyzer Contract

Stage 19 reuses `SquashFSMetadataStream`; it does not duplicate metadata
decompression or boundary traversal. It exposes frozen models:

- `SquashFSXAttrNamespace(raw_type, prefix, known)`;
- `SquashFSXAttrEntry(raw_type, namespace, name, full_name, value,
  value_size, out_of_line, out_of_line_reference)`;
- `SquashFSXAttrList(xattr_id, entries, consumed_size)`.

All names and values remain `bytes`.  A known namespace forms `full_name` by
concatenating its byte prefix with raw name.  Unknown types are represented
losslessly (`known=False`, `prefix=None`, `full_name=None`) rather than being
silently dropped.

The public API is `decode_xattr_namespace(raw_type)`,
`read_xattr_list(image, xattr_id, table=None)`, and
`read_inode_xattrs(image, inode, table=None)`. The latter returns `None` for
an inode whose Stage-18 `xattr_id` is `None`; parsing an inode remains lazy.

## Validation and Errors

The reader will require exactly `count` entries. `consumed_size` records the
exact entry bytes consumed. The Stage-18 ID `size` may additionally include up
to three zero bytes of four-byte alignment padding, as measured on the UDM Pro
ROOTFS (`consumed_size=38`, declared `size=40`). Non-zero, excessive, or
misaligned trailing bytes, short data, arithmetic overflow, and count/size
mismatch are errors. It will use typed
`SquashFSXAttrListError`, `SquashFSXAttrEntryError`, and
`SquashFSXAttrValueError`, chaining metadata failures with `raise ... from`.
OOL requires exactly an eight-byte reference and must expose no inline value.

## Test and ROOTFS Evidence

Tests will independently cover all three namespaces, unknown types, inline
and OOL entries, zero-length fields, binary names/values, exact count/size,
short/malformed fields, metadata boundaries, compressed/uncompressed blocks,
immutability, chaining, ID 0, non-zero IDs, absent IDs/table, and inode laziness.
ROOTFS investigation will record only stable list facts, without dumping full
possibly sensitive values.

## Deferred Stage 20 Scope

Stage 20 alone may dereference OOL value references and interpret ACL,
capability, SELinux, or other namespace-specific value semantics.  Stage 19
does not modify images, extract host xattrs, or add CLI output.
