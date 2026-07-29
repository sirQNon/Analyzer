# SquashFS v4 Fragment Table Reader

## Scope

Stage 12 reads SquashFS v4 fragment-table entries and their complete fragment
data blocks.  It does not connect fragment tails to `read_basic_regular_file()`;
that integration is reserved for Stage 13.

## Primary sources

The layout and formulas below are from Linux
`fs/squashfs/squashfs_fs.h` and the lookup algorithm is corroborated by
`fs/squashfs/fragment.c`.

* <https://codebrowser.dev/linux/linux/fs/squashfs/squashfs_fs.h.html>
* <https://codebrowser.dev/linux/linux/fs/squashfs/fragment.c.html>

## Fragment entry

One `struct squashfs_fragment_entry` is 16 bytes, little-endian `<QII>`:

| Offset | Field | Size | Meaning |
| ---: | --- | ---: | --- |
| 0 | `start_block` | 8 | Absolute image offset of the fragment data block. |
| 8 | `size` | 4 | Stored block size and compression flag. |
| 12 | `unused` | 4 | On-disk reserved field retained in the typed entry. |

`size` uses `SQUASHFS_COMPRESSED_BIT_BLOCK` (bit 24): set means the data block
is uncompressed. Bits 0--23 are the stored byte count. Bits 25--31 are invalid
for the block-size encoding.

## Fragment table index and metadata addressing

`superblock.fragment_table_start` points to the uncompressed index array, not
to the fragment-entry metadata data.  Each index item is an 8-byte little-endian
absolute image offset to one compressed-or-uncompressed SquashFS metadata block.

The kernel definitions give these formulas for `N` fragments:

```text
fragment_bytes = N * 16
index_count = ceil(fragment_bytes / 8192)
index_bytes = index_count * 8
entry_block = floor((entry_index * 16) / 8192)
entry_offset = (entry_index * 16) % 8192
```

Thus 512 entries fit in one 8192-byte decompressed metadata block.  The reader
uses the existing metadata-block reader and stream boundary handling; it does
not implement another metadata parser or decompressor.

## Fragment data blocks

For an entry, `start_block` addresses the physical payload directly.  The
stored-size part of `size` determines exactly how many bytes are read.  A set
bit 24 returns the payload unchanged; otherwise the common Zstandard payload
helper decompresses it with `superblock.block_size` as the maximum output size.

The decoded fragment block must be non-empty and no larger than the superblock
block size.  It is not required to equal the block size: a final or only packed
fragment block may be shorter.  The Stage 12 reader returns the complete decoded
fragment block without padding or slicing by an inode offset.

## Error model

Fragment data errors use `SquashFSFragmentError` subclasses.  The reader
distinguishes invalid entry indexes, truncated index tables, invalid metadata
pointers, malformed or truncated entries, truncated data blocks, decompression
failures, and decoded sizes outside the permitted range.

## Limitations

Stage 12 does not read file tails, extended regular inodes, extended symlinks,
hardlinks, export/lookup/xattr tables, path resolution, extraction changes, or
fragment-block caches.  Stage 13 will combine a regular inode's fragment index
and offset with this independent fragment-table reader.
