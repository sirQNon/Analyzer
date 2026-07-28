# SquashFS v4 directory header and entry

## Scope

Stage 6 implements byte-only parsers for one `squashfs_dir_header` and one
`squashfs_dir_entry`. It does not read directory metadata, iterate entries,
resolve an inode number, decode names to text, or build paths.

## Linux on-disk structures

Linux `fs/squashfs/squashfs_fs.h` defines:

```c
struct squashfs_dir_header {
    __le32 count;
    __le32 start_block;
    __le32 inode_number;
};

struct squashfs_dir_entry {
    __le16 offset;
    __le16 inode_number;
    __le16 type;
    __le16 size;
    char name[];
};
```

All fixed fields are little-endian. The directory header is `<III` and is
12 bytes. The fixed directory-entry prefix occupies 8 bytes.

| Structure | Offset | Field | On-disk type | Bytes |
| --- | ---: | --- | --- | ---: |
| header | 0 | `count` | `__le32` | 4 |
| header | 4 | `start_block` | `__le32` | 4 |
| header | 8 | `inode_number` | `__le32` | 4 |
| entry | 0 | `offset` | `__le16` | 2 |
| entry | 2 | `inode_number` | `__le16` | 2 |
| entry | 4 | `type` | `__le16` | 2 |
| entry | 6 | `size` | `__le16` | 2 |
| entry | 8 | `name` | `char[]` | variable |

## Confirmed semantics

Linux `dir.c` performs:

```c
dir_count = le32_to_cpu(dirh.count) + 1;
size = le16_to_cpu(dire->size) + 1;
inode_number = le32_to_cpu(dirh.inode_number) +
    ((short) le16_to_cpu(dire->inode_number));
```

Therefore:

- `count` is the number of entries in its header group **minus one**. The
  group contains `count + 1` entries; Linux rejects values yielding more than
  `SQUASHFS_DIR_COUNT` (256) entries.
- `size` is encoded name length **minus one**. The exact name length is
  `size + 1`; Linux rejects a resulting length greater than
  `SQUASHFS_NAME_LEN` (256).
- `inode_number` in the header is an unsigned `__le32` base inode number.
- entry `inode_number` has on-disk type `__le16`, but Linux casts the decoded
  value to `short` before adding it to the header base. Its semantic value is
  a signed 16-bit delta. The project parser consequently uses `<h` and stores
  `inode_number_delta: int`.
- `type` is an unsigned numeric directory entry type. Stage 6 stores it as
  `entry_type` without converting it to an enum or parser choice.
- `offset` is the entry inode's offset in the decompressed inode metadata
  block; it is not interpreted by Stage 6.
- the documented final inode-number formula is
  `header.inode_number + entry.inode_number_delta`. It is documented only;
  Stage 6 does not implement the resolver.
- the directory inode's `start_block` is relative to the directory-table
  start; its `offset` selects a position within a decompressed directory
  metadata block. The directory header's `start_block` is shared by entries
  in that header group and identifies their inode metadata block.

`encoded_size` is included in `SquashFSDirectoryEntry`: it equals fixed entry
size plus `len(name)`. This lets a later cursor advance without parsing the
entry again; it does not create a directory reader.

## Real `Extracted/rootfs` evidence

Stage 5 established root directory metadata values:

- directory-table start: `0x24467318`;
- root basic-directory `start_block`: `0x607CF` (`395215`);
- root basic-directory `offset`: `3260`.

The resulting directory metadata block is at `0x244C7AE7`; its stored Zstandard
payload is 1631 bytes and decompresses to 3483 bytes. At decompressed offset
3260, the first directory header is:

```text
01 00 00 00 00 00 00 00 01 00 00 00
```

| Bytes | Field | Value |
| --- | --- | ---: |
| `01 00 00 00` | `count` | 1 (two entries in this group) |
| `00 00 00 00` | `start_block` | 0 |
| `01 00 00 00` | `inode_number` | 1 |

The first directory entry is:

```text
76 0f 00 00 01 00 02 00 62 69 6e
```

| Bytes | Field | Value |
| --- | --- | --- |
| `76 0f` | `offset` | 3958 |
| `00 00` | inode-number delta | 0 |
| `01 00` | `type` | 1 |
| `02 00` | `size` | 2 |
| `62 69 6e` | `name` | `b"bin"`, length 3 |

The entry's encoded size is `8 + (2 + 1) = 11` bytes. Its documented final
inode number would be `1 + 0 = 1`; no resolver is implemented.

## Evidence separation

Linux source facts:

- both exact structures, their field types and `SQUASHFS_NAME_LEN=256`;
- `count + 1`, `size + 1`, the 256-entry/name limits, and signed delta cast.

Official documentation facts:

- directories are compressed metadata in the directory table;
- their locations use a metadata block plus decompressed-block offset; and
  directory headers group entries with a shared inode metadata start block.

UDM Pro rootfs facts:

- physical metadata location, compressed/decompressed sizes, header and entry
  dumps, and every decoded value above.

Project architecture decisions:

- parsers accept only `bytes`, return frozen dataclasses and perform no I/O;
- raw name bytes are not decoded;
- `encoded_size` records exactly the single parsed entry's on-disk size.

No disagreement was found among the Linux source, documentation and the
measured UDM Pro rootfs data.

## Sources

- Linux `squashfs_fs.h`, directory structures and limits:
  <https://codebrowser.dev/linux/linux/fs/squashfs/squashfs_fs.h.html>
- Linux `dir.c`, count/name-length/delta calculations:
  <https://codebrowser.dev/linux/linux/fs/squashfs/dir.c.html>
- Linux documentation, *Squashfs 4.0 Filesystem*, directory metadata design:
  <https://www.kernel.org/doc/html/latest/filesystems/squashfs.html>
