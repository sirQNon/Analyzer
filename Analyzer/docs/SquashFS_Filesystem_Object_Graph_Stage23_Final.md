# Stage 23 - SquashFS filesystem object graph

## Status

Stage 23 provides an immutable, bytes-path SquashFS graph ready for commit
after the documented regression gates pass.

## Public surface

Models: `SquashFSFilesystem`, `SquashFSInodeIdentity`, path-node subclasses,
`SquashFSDirectoryListing`, and `SquashFSFilesystemIndex`.  APIs are
`open_filesystem`, `get_root`, `list_children`, `lookup_path`,
`walk_filesystem`, `build_filesystem_index`, `node_for_path`,
`paths_for_inode`, `read_node_bytes`, `read_node_symlink`, and
`read_node_xattrs`.

Only absolute `bytes` paths are accepted.  The layer rejects normalization
forms, text, NUL, dot components, repeated slashes, and trailing slashes.
Listings preserve on-disk raw names and duplicate evidence.  Lookup rejects a
duplicate component; traversal/index reject duplicate absolute paths.  Every
path has its own frozen node, while hard links share an inode identity and are
grouped by the reverse index.  Walk is depth-first preorder in on-disk order;
an active ancestor stack detects directory cycles without treating completed
directories or non-directory hard links as cycles.

Content helpers delegate to established basic/extended readers and preserve
their failures as graph-content causes.  Symlink targets are explicitly read
but not followed.  XAttrs delegate to `read_inode_xattrs`; semantic decoding
continues to use the established `read_and_decode_xattr` API, avoiding a
redundant wrapper.

## Errors and deferred scope

Graph errors distinguish root/read/type, directory read/child/entry, malformed
or missing paths, not-directory, duplicate names, cycles, index failures, and
node-content failures.  No special inode parsers, symlink following, host
paths, extraction, ACL/SELinux decoding, mutable cache, or CLI is included.

## Evidence

Focused Stage 23B--D classes cover root/lazy listing, path validation,
traversal and cycles, index/hard links, content dispatch, and ROOTFS facts.
The ROOTFS report records final production measurements and `/bin/ping`
capability evidence.

## Final audit

### Scope, models, and APIs

Stage 23 is the immutable object graph over the existing SquashFS readers. It
covers opening a directory root, raw-byte lookup, lazy listings, explicit
preorder traversal, cycle detection, immutable indexes, hard-link grouping,
and explicit content/XAttr access. Frozen models are `SquashFSNodeType`,
`SquashFSInodeIdentity`, `SquashFSFilesystem`, `SquashFSPathNode` and its
directory/regular/symlink/unsupported subclasses, `SquashFSDirectoryListing`,
and `SquashFSFilesystemIndex`.

The public surface is `open_filesystem`, `get_root`, `list_children`,
`lookup_path`, `walk_filesystem`, `build_filesystem_index`, `node_for_path`,
`paths_for_inode`, `read_node_bytes`, `read_node_symlink`, and
`read_node_xattrs`. Paths are absolute on-image `bytes`; no host path
normalization, text conversion, hidden cache, or symlink following occurs.
Hard-link path nodes remain distinct while sharing inode identity. Content and
XAttr I/O are explicit only.

### Layering and errors

Stages 18--20 provide XAttr IDs, lists, and OOL values; Stage 21 decodes Linux
capabilities; Stage 22 dispatches semantic XAttrs; Stage 23 consumes those
layers without reverse dependencies. Graph construction does not read content
or XAttrs, semantic decoding does not transport values, the index is built from
traversal, and lookup does not build an index.

Public errors are `SquashFSFilesystemGraphError`, `SquashFSRootError`,
`SquashFSGraphReadError`, `SquashFSNodeTypeError`,
`SquashFSDirectoryReadError`, `SquashFSChildInodeError`,
`SquashFSDirectoryEntryError`, `SquashFSPathError`,
`SquashFSPathNotFoundError`, `SquashFSNotDirectoryError`,
`SquashFSDuplicateNameError`, `SquashFSDirectoryCycleError`,
`SquashFSFilesystemIndexError`, and `SquashFSNodeContentError`; public
boundaries preserve lower causes.

### Acceptance and ROOTFS

Focused classes contain 11 root, 23 listing, 8 lookup, 11 traversal, 9 index,
27 content, and 1 ROOTFS test: 90 static Stage 23 tests. All root, 52/52
listing, lookup, traversal/cycle, index/hard-link, 62/62 content/XAttr, and
ROOTFS matrices are covered.

The supplied ROOTFS has 43,433 graph nodes including root, 43,432 directory
entries, 5,329 directories, 35,952 regular files, 2,152 symlinks, zero
unsupported nodes, maximum depth 17, 43,427 identities, and five repeated
identities. There are no duplicate paths, cycles, invalid UTF-8 paths, or
unresolved children. `/bin/ping` has inline `security.capability` bytes
`0100000200200000000000000000000000000000`, decoded as revision 2,
effective `True`, mask `0x2000`, capability 13 (`CAP_NET_RAW`), empty
inheritable set, and `root_id=None`.

### Corrections, limitations, and handoff

Confirmed corrections wrap root-opening `OSError`; reject non-directory
listing nodes; wrap lower directory `KeyError`/`IndexError`; validate index
mapping consistency; and wrap invalid supplied-XAttr-table `AttributeError` as
`SquashFSNodeContentError`. Regression tests cover each.

Deferred: special-inode parsers, symlink following, text paths, extraction,
ACL/SELinux semantic decoding, mutable caches, and CLI. Checked: APIs,
matrices, immutability, and ROOTFS evidence. Do not know: directory hard-link
format constraints and unsupported special-inode layouts. A suitable Stage 24
is special-inode parsing or a separately scoped extraction layer.

Commit checklist: include `squashfs.py`, `test_squashfs.py`, this final report,
the architecture report, and the ROOTFS validation report; exclude unrelated
inode/metadata docs and `stage19_*.patch` files.
