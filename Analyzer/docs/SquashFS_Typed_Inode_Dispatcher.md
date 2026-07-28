# SquashFS v4 typed inode dispatcher

## Confirmed inode type constants

Linux `fs/squashfs/squashfs_fs.h` defines these numeric type values.

| Value | Constant | Linux structure | Fixed bytes including base header | Stage 9 policy |
| ---: | --- | --- | ---: | --- |
| 1 | `SQUASHFS_DIR_TYPE` | `squashfs_dir_inode` | 32 | supported |
| 2 | `SQUASHFS_REG_TYPE` | `squashfs_reg_inode` | 32 | supported |
| 3 | `SQUASHFS_SYMLINK_TYPE` | `squashfs_symlink_inode` | 24 plus target | unsupported |
| 4 | `SQUASHFS_BLKDEV_TYPE` | `squashfs_dev_inode` | 24 | unsupported |
| 5 | `SQUASHFS_CHRDEV_TYPE` | `squashfs_dev_inode` | 24 | unsupported |
| 6 | `SQUASHFS_FIFO_TYPE` | `squashfs_ipc_inode` | 20 | unsupported |
| 7 | `SQUASHFS_SOCKET_TYPE` | `squashfs_ipc_inode` | 20 | unsupported |
| 8 | `SQUASHFS_LDIR_TYPE` | `squashfs_ldir_inode` | 40 plus indexes | unsupported |
| 9 | `SQUASHFS_LREG_TYPE` | `squashfs_lreg_inode` | 56 | unsupported |
| 10 | `SQUASHFS_LSYMLINK_TYPE` | `squashfs_lsymlink_inode` | 32 plus target | unsupported |
| 11 | `SQUASHFS_LBLKDEV_TYPE` | `squashfs_ldev_inode` | 32 | unsupported |
| 12 | `SQUASHFS_LCHRDEV_TYPE` | `squashfs_ldev_inode` | 32 | unsupported |
| 13 | `SQUASHFS_LFIFO_TYPE` | `squashfs_lipc_inode` | 28 | unsupported |
| 14 | `SQUASHFS_LSOCKET_TYPE` | `squashfs_lipc_inode` | 28 | unsupported |

All structures begin with the already implemented 16-byte
`squashfs_base_inode`. Basic directory has body
`start_block, nlink, file_size, offset, parent_inode` (`<IIHHI`); basic regular
has body `start_block, fragment, offset, file_size` (`<IIII`). No file data is
read by either parser.

## UDM Pro evidence

Stage 8 root records `bin`, `etc`, `usr`, and `var` have type 1. Reading their
inode references produces basic directory inodes whose generic inode number
and type equal their directory records. Reading only the `bin` directory gives
`bash` with type 2; its reference produces a basic regular inode. Root record
`lib64` has type 3 and remains a known unsupported symlink type.

## Metadata references

`SquashFSMetadataReference` is a frozen dataclass, but it does not validate
its fields in `__post_init__`. Existing invariants are distributed: packed
references are bounded by `decode_metadata_reference()`, Stage 8 validates
raw directory `start_block` and `offset`, and `SquashFSMetadataStream.read()`
checks a byte offset against the decoded metadata block. Stage 9 performs no
duplicate numeric-reference validation; it validates only its Python argument
types and delegates location reads to the existing stream.

## Dispatcher architecture

`read_inode(stream, reference)` reads exactly 16 bytes for the generic header,
uses `INODE_BODY_PARSERS` to select a fixed body parser, then reads exactly the
remaining body from `reference.byte_offset + 16`. The header bytes are not
read a second time. The result is an immutable container that keeps the source
location, common header, and selected typed body together:

```python
@dataclass(frozen=True)
class SquashFSInode:
    reference: SquashFSMetadataReference
    header: SquashFSInodeHeader
    body: SquashFSBasicDirectoryInode | SquashFSBasicRegularInode
```

Unsupported valid and unknown numeric types raise
`SquashFSUnsupportedInodeTypeError`, including the numeric type. Malformed or
truncated data continues to raise existing inode or metadata-stream errors.

## Stage boundary

Stage 9 does not traverse directories recursively, resolve paths, read file
contents, process fragments, resolve symlinks, parse extended inodes, or add a
filesystem facade.

## Sources

- Linux inode structures and `SQUASHFS_*_TYPE` constants:
  <https://codebrowser.dev/linux/linux/fs/squashfs/squashfs_fs.h.html>
- Linux SquashFS 4.0 format documentation:
  <https://www.kernel.org/doc/html/latest/filesystems/squashfs.html>
