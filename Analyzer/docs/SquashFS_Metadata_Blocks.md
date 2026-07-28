# SquashFS metadata blocks

## Confirmed format

SquashFS v4 stores inode and directory metadata in blocks with a two-byte
little-endian header followed immediately by its payload. The lower 15 bits of
the header are the stored payload size. Bit 15 is the uncompressed flag: set
means the payload is stored as-is; clear means the payload is compressed.

The decompressed metadata block limit is 8192 bytes. The next block starts at
`offset + 2 + stored_size`; there is no alignment padding between blocks.

Sources:

- [Linux SquashFS 4.0 documentation](https://www.kernel.org/doc/html/latest/filesystems/squashfs.html): metadata is compressed in 8 KiB blocks and preceded by a two-byte length; the top bit marks an uncompressed block.
- [Linux `squashfs_fs.h`](https://codebrowser.dev/linux/linux/fs/squashfs/squashfs_fs.h.html): `SQUASHFS_METADATA_SIZE`, `SQUASHFS_COMPRESSED_BIT`, `SQUASHFS_COMPRESSED_SIZE`, and `SQUASHFS_COMPRESSED`.

The same metadata-block representation is used by the tables whose start
addresses are stored in the superblock, including the inode and directory
tables. A table address points to the metadata block header, not directly to
its decompressed bytes.

## Experiment: `Extracted/rootfs`

The root inode reference resolves to inode-table metadata block address
`0x24467007`. Its two-byte header is `0x030F` in little-endian form:

- stored payload size: `783` bytes;
- bit 15: clear, so the payload is compressed;
- next metadata-block address: `0x24467007 + 2 + 783 = 0x24467318`.

`0x24467318` equals `directory_table_start` from this image's SquashFS
superblock. This confirms the header-plus-payload layout on the extracted
image.

## Endianness

The superblock magic is `0x73717368` and the on-disk fields are read as
little-endian values. The metadata header is therefore decoded as unsigned
little-endian 16-bit data.

## Reader validation

The metadata reader must reject:

- non-integer or out-of-range offsets;
- a short two-byte header;
- a zero-length payload;
- a payload extending beyond the image;
- ZSTD decompression failures;
- decompressed output over 8192 bytes.

For uncompressed metadata blocks, the payload is returned unchanged. For
compressed blocks in this image, compression ID 6 is ZSTD; decompression uses
the external `zstandard` Python package. The package was absent from the
current environment before this stage and is declared in `requirements.txt`.
