# SquashFS v4 basic regular-file reader

## Scope

Stage 10 reads the contents of a `SQUASHFS_REG_TYPE` (type `2`) inode when it
has no fragment.  It returns `bytes` and does not add path resolution,
directory traversal, fragment-table handling, extended regular inodes, or an
extraction API.

## Confirmed on-disk layout

Linux `struct squashfs_reg_inode` places these four little-endian `__le32`
fields after the existing 16-byte `squashfs_base_inode`:

| Offset in inode | Field | Size |
| ---: | --- | ---: |
| 16 | `start_block` | 4 |
| 20 | `fragment` | 4 |
| 24 | `offset` | 4 |
| 28 | `file_size` | 4 |
| 32 | `block_list[]` | 4 per entry |

The Linux file reader reads every `block_list` item as `__le32`; therefore the
Stage 10 entry struct is `<I`, not a metadata reference.  Each entry is a
physical stored size: bit 24 (`SQUASHFS_COMPRESSED_BIT_BLOCK`) means the data
block is uncompressed, and bits 0--23 give the stored byte count.  Bits
25--31 are rejected.  The Linux reader treats an encoded size of zero as a
sparse data block; Stage 10 implements that behavior as `logical_size` zero
bytes and does not advance the physical data offset.

`SQUASHFS_INVALID_FRAG` is `0xffffffff`.  With that value, the block list has
`ceil(file_size / superblock.block_size)` entries.  With a valid fragment,
the list covers only the complete data blocks, and the tail belongs to the
fragment table.  Stage 10 raises `SquashFSFragmentFileUnsupportedError` before
returning any bytes for this case.

## Reader architecture

`read_inode()` remains a typed inode dispatcher.  It reads neither the
block-size list nor file data.  `read_basic_regular_file(image,
metadata_stream, inode)` receives its `SquashFSInode` result, verifies that
the body is `SquashFSBasicRegularInode`, and reads the list beginning exactly
after the 32-byte fixed inode.

`SquashFSMetadataStream.advance_reference()` advances in decompressed metadata
bytes and returns a normalized metadata reference.  It is required because a
fixed inode or its block list can end at a metadata-block boundary.  The
existing `MetadataStream.read()` then reads the complete contiguous list,
including across metadata blocks.

For every descriptor, the reader reads `stored_size` bytes from the absolute
image offset `inode.start_block`.  The next offset is previous offset plus
`stored_size`; no metadata header is included.  Uncompressed data is used
directly.  Compressed data is decoded with the existing Zstandard library
path, and the decoded result must equal the computed logical block size.  The
last ordinary block uses the remaining `file_size` bytes, not always the
superblock block size.

## Errors

* `SquashFSMalformedBlockListError` — short entry or reserved size bits.
* `SquashFSDataBlockTruncatedError` — a physical block reaches past the image.
* `SquashFSDataBlockDecompressionError` — Zstandard rejects a compressed block.
* `SquashFSDataBlockSizeError` — decoded or uncompressed size differs from the
  expected logical size.
* `SquashFSFragmentFileUnsupportedError` — a fragment-backed regular file.

## UDM Pro integration facts

The existing Stage 8 directory API resolves `/bin`, then its `bash` record.
Stage 9 `read_inode()` identifies that inode as basic regular.  Its confirmed
fields are `file_size=1269664`, `fragment=0xffffffff`, and `start_block=96`.
Stage 10 reads exactly `1269664` bytes and the first four bytes are
`7f 45 4c 46`, the ELF signature.  The integration test checks those facts;
it does not assert byte equality for the complete executable.

## Sources

* Linux `fs/squashfs/squashfs_fs.h`: `SQUASHFS_INVALID_FRAG`,
  `SQUASHFS_COMPRESSED_BIT_BLOCK`, `SQUASHFS_COMPRESSED_SIZE_BLOCK`, and
  `struct squashfs_reg_inode`.
  <https://codebrowser.dev/linux/linux/fs/squashfs/squashfs_fs.h.html>
* Linux `fs/squashfs/file.c`: `read_indexes()` reads `__le32` list entries,
  `read_blocklist()` decodes their stored sizes, and a zero result selects the
  sparse-page path.
  <https://codebrowser.dev/linux/linux/fs/squashfs/file.c.html>
* Linux SquashFS 4.0 documentation: regular files are contiguous compressed
  blocks and/or a fragment, with compressed sizes stored in the inode block
  list.
  <https://www.kernel.org/doc/html/latest/filesystems/squashfs.html>
