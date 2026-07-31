# SquashFS Out-of-Line XAttr Value Resolution — Stage 20A

## Status and scope

Research and architecture only. Stage 19 remains unchanged: an OOL entry has
`out_of_line=True`, `value=None`, and a raw unsigned-64-bit reference. Stage
20 will resolve it without interpreting ACL, capability, or SELinux bytes.

## Linux format and reference encoding

Linux `fs/squashfs/squashfs_fs.h` defines:

```c
struct squashfs_xattr_val {
    __le32 vsize;
    char value[];
};
#define SQUASHFS_XATTR_VALUE_OOL 256
#define SQUASHFS_XATTR_PREFIX_MASK 0xff
#define SQUASHFS_XATTR_BLK(A)    ((unsigned int) ((A) >> 16))
#define SQUASHFS_XATTR_OFFSET(A) ((unsigned int) ((A) & 0xffff))
```

The OOL reference uses the same high-48/low-16 encoding as an XAttr ID
reference. Its high part is a physical metadata-block position relative to the
XAttr metadata-table start; its low part is an offset in that block's
decompressed data. It is not an absolute image offset and does not point to a
value payload.

Linux `fs/squashfs/xattr.c:squashfs_xattr_get()` reads the list-side value
header, then an `__le64` reference, and assigns:

```c
start = SQUASHFS_XATTR_BLK(xattr) + msblk->xattr_table;
offset = SQUASHFS_XATTR_OFFSET(xattr);
```

It then reads a new `struct squashfs_xattr_val` at that target and exactly its
`vsize` bytes. Thus the reference points to the beginning of target `vsize`.
The target is `<le32 vsize><value bytes>` only: it has no entry header, name,
namespace, or OOL flag, so recursive OOL is structurally impossible.

All reads use `squashfs_read_metadata()`. Target headers and values may cross
physical metadata blocks; the blocks may be compressed or uncompressed. Read
failures propagate as negative kernel errors.

## OOL validation and squashfs-tools comparison

The list-side `vsize` describes the reference representation and is 8. Linux
`squashfs_xattr_get()` fixed-reads an `__le64` but does not visibly compare the
list-side `vsize` to 8. squashfs-tools
`squashfs-tools/read_xattrs.c:get_xattr()` rejects
`val.vsize != sizeof(xattr)`. Stage 19's stricter `vsize == 8` policy remains
mandatory for Stage 20.

The target `vsize` is the actual little-endian u32 value length and can be
zero. `squashfs-tools/xattr.c` writes a target `squashfs_xattr_val` plus value,
then writes a list-side header with `vsize = XATTR_VALUE_OOL_SIZE` and the
little-endian reference. It deduplicates duplicate values, so multiple entries
may point to one target, and it permits inline/OOL entries in one list.
`XATTR_VALUE_OOL_SIZE` is `sizeof(long long)`; its `XATTR_TARGET_MAX` 65536 is
a writer policy, not an on-disk format maximum.

Tools cache decompressed XAttr metadata and resolve OOL while constructing a
returned list. Linux resolves only a selected named attribute. Both use the
same target layout; tools explicitly validate list-side reference size.

## Stage 20 architecture

### Public API recommendation

Add an explicit lazy resolver:

```python
read_xattr_out_of_line_value(
    image: SquashFSImage,
    entry: SquashFSXAttrEntry,
    table: SquashFSXAttrIDTable | None = None,
) -> bytes
```

It accepts only a Stage 19 OOL entry and returns raw target bytes. It must not
mutate the frozen entry or populate `entry.value`. An inline entry is a direct
`SquashFSXAttrValueError`. Lazy resolution preserves Stage 19 behavior, avoids
unrequested I/O, and permits a later caller-side cache keyed by
`(xattr_table_start, out_of_line_reference)`.

### Resolution flow

1. Validate `image`, `entry`, and optional table; load the Stage 18 table only
   if omitted.
2. Require OOL invariants: `out_of_line`, `value is None`, and a u64 reference.
3. Decode with existing `decode_xattr_reference()`. Build
   `SquashFSMetadataStream(image, table.xattr_table_start + reference.block)`
   at `reference.offset`.
4. Read the target value header, advance with `advance_reference()`, decode its
   u32 `vsize`, then read exactly that many raw bytes through the same stream.

No second metadata parser, owning-list reparse, eager inode change, or OOL
target interpretation is needed.

## Validation and error model

Require low offset `< METADATA_SIZE`, checked table-start addition, and target
physical start before `table.metadata_block_offsets[0]`, the first XAttr-ID
metadata block. Existing metadata-block reads then prove a readable block.
Reject outside-region references, malformed headers, invalid offsets, and
truncation.

Zero target length returns `b""`. For a large u32 target, Stage 20 must
preflight an exact bounded traversal ending before the XAttr-ID region with the
existing metadata-block API, then allocate/assemble only the proven bytes. It
must reject unrepresentable/truncated lengths rather than perform an unbounded
read. Compression and physical-boundary traversal remain supported.

Reuse `SquashFSXAttrValueError` for direct OOL invariants and target failures.
Wrap `SquashFSMetadataError`, `SquashFSMetadataStreamError`, and `struct.error`
with `raise ... from error`; exact lower-level types remain in `__cause__`.
No new list or inode error is required.

## ROOTFS observation

Investigation through current production APIs on
`E:\UDM_PRO\Extracted\rootfs` measured one ID, one inline entry, and **zero
OOL entries**. The available ROOTFS cannot exercise positive target resolution.
Stage 20 therefore needs synthetic physical fixtures for target layout,
compression, boundaries, duplicate references, and malformed references.

## Implementation plan and Stage 21 boundary

1. Add the lazy resolver and private bounded-target-read helper.
2. Add static tests for target header/value, zero/large values, malformed and
   duplicate references, compression, boundaries, and chained errors.
3. Preserve all Stage 19 list/inode behavior and prove OOL remains unresolved
   until the new API is called.
4. Reinvestigate ROOTFS; add a positive real-image test only if OOL exists.

Stage 21 may interpret resolved bytes by namespace. Stage 20 returns opaque
bytes only and adds no extraction, mutation, CLI, or repacking behavior.

## Checked / Know / Don't know

| Status | Statement |
|---|---|
| Checked | Linux `squashfs_xattr_get()` resolves an OOL reference to target `squashfs_xattr_val`. |
| Checked | The reference targets `vsize`, uses high-48/low-16 metadata encoding, and can traverse metadata blocks. |
| Checked | squashfs-tools writes deduplicated targets and validates list-side OOL size. |
| Checked | Current ROOTFS has no OOL entries. |
| Know | Stage 19 preserves sufficient list-side state for lazy resolution. |
| Don't know | Real OOL behavior in another UDM Pro image; this fixture cannot provide it. |
