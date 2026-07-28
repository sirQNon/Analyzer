# SquashFS v4 directory record inode reference

## Scope

Stage 8 gives every `SquashFSDirectoryRecord` the complete location of its
child inode in the inode metadata stream. It does not resolve inode bodies,
walk directories, resolve paths, read files, or add an inode dispatcher.

## Confirmed Linux format

Linux defines these on-disk fields in `fs/squashfs/squashfs_fs.h`:

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

`start_block` is an offset relative to the beginning of the inode table, not
the directory table and not an absolute image offset. `offset` selects bytes
within the decompressed inode metadata block selected by `start_block`.

The exact child-inode metadata reference is therefore:

```text
block_offset = directory_header.start_block
byte_offset  = directory_entry.offset
```

The absolute image location is obtained only when an inode metadata stream
uses that reference:

```text
image metadata block location = superblock.inode_table_start + block_offset
```

Linux `squashfs_readdir()` uses the same `start_block` and `offset` pair when
constructing a child inode. Its independent inode-number calculation is:

```text
directory_inode_number = directory_header.inode_number
                       + signed_16(directory_entry.inode_number)
```

## UDM Pro `Extracted/rootfs` verification

The image has `inode_table_start = 608226847`. The root directory was read
from the directory table; its records supplied the following inode-table
references. Each reference was then read through `SquashFSMetadataStream` and
decoded with `parse_inode_header()`.

| Name | `start_block` | `offset` | reference | record inode/type | decoded inode/type |
| --- | ---: | ---: | --- | --- | --- |
| `bin` | 0 | 3958 | `<0, 3958>` | `1 / 1` | `1 / 1` |
| `etc` | 16754 | 7421 | `<16754, 7421>` | `124 / 1` | `124 / 1` |
| `usr` | 347637 | 2505 | `<347637, 2505>` | `2976 / 1` | `2976 / 1` |
| `var` | 369128 | 2251 | `<369128, 2251>` | `40888 / 1` | `40888 / 1` |

The exact first 16 inode-header bytes, respectively, were:

```text
bin: 01 00 fd 01 00 00 00 00 cb d8 e5 64 01 00 00 00
etc: 01 00 fd 01 00 00 00 00 cb d8 e5 64 7c 00 00 00
usr: 01 00 fd 01 00 00 00 00 cb d8 e5 64 a0 0b 00 00
var: 01 00 ed 01 00 00 00 00 94 db e5 64 b8 9f 00 00
```

These observations confirm both the coordinate system and the formula for all
four requested records.

## Architecture

`SquashFSMetadataReference` already represents exactly the confirmed pair
`(block_offset, byte_offset)`. Stage 8 therefore uses the non-duplicating
representation:

```python
@dataclass(frozen=True)
class SquashFSDirectoryRecord:
    inode_number: int
    inode_type: int
    name: bytes
    inode_reference: SquashFSMetadataReference
```

`directory_entry_reference(header, entry)` is a pure helper that validates
the on-disk unsigned ranges (`__le32` for `start_block`, `__le16` for
`offset`) and constructs the reference. `read_directory()` uses it for every
record. No record also stores `start_block` or `offset`.

## Sources

- Linux source, directory structures: <https://codebrowser.dev/linux/linux/fs/squashfs/squashfs_fs.h.html>
- Linux source, `squashfs_readdir()`: <https://codebrowser.dev/linux/linux/fs/squashfs/dir.c.html>
- Linux documentation, Squashfs 4.0 directory and inode metadata:
  <https://www.kernel.org/doc/html/latest/filesystems/squashfs.html>
