# SquashFS filesystem object graph - Stage 23A

## 1. Scope

Stage 23 is a path-aware immutable layer over existing readers. It does not
change metadata parsing, follow symlinks, use host paths, add extraction, or
implement ACL/SELinux semantics. This document is research only.

## 2. Accepted prerequisites

Stages 11--17 provide typed inode, directory, file, symlink, fragment and
lookup readers. Stages 18--22 provide XAttr transport and semantic dispatch.
The graph consumes these contracts without replacing them.

## 3. Current low-level API inventory

`SquashFSImage(image: Path | str)` owns a host `Path`, caches an optional
superblock, and `read_superblock() -> SquashFSSuperBlock`. Its `root_inode: int`
is an encoded inode metadata reference. `read_inode(stream, reference) ->
SquashFSInode` returns frozen `reference`, a header (`inode_type`, `mode`,
`uid`, `guid`, `mtime`, `inode_number`), and a typed body.

Bodies are `SquashFSBasicDirectoryInode(header, start_block, nlink, file_size,
offset, parent_inode)`, `SquashFSExtendedDirectoryInode(header, nlink,
file_size, start_block, parent_inode, i_count, offset, xattr)`,
`SquashFSBasicRegularInode(header, start_block, fragment, offset, file_size)`,
`SquashFSExtendedRegularInode(header, start_block, file_size, sparse, nlink,
fragment, offset, xattr)`, `SquashFSBasicSymlinkInode(header, nlink,
symlink_size)`, and `SquashFSExtendedSymlinkInode(header, nlink, symlink_size,
xattr)`. Other inode types raise `SquashFSUnsupportedInodeTypeError`.

`resolve_inode_number(image, inode_stream, table, inode_number) -> SquashFSInode`
uses the Stage 17 lookup table. `read_directory(metadata_stream,
directory_inode) -> list[SquashFSDirectoryRecord]` accepts both directory
bodies. A record contains `inode_number`, `inode_type`, raw `name: bytes`, and
`inode_reference`. `read_basic_regular_file(image, metadata_stream, inode) ->
bytes` and `read_extended_regular_file(image, metadata_stream, inode) -> bytes`
require their matching bodies. `read_basic_symlink(metadata_stream, inode) ->
str` and `read_extended_symlink(metadata_stream, inode) -> str` UTF-8 decode
targets. `read_inode_xattrs(image, inode, table=None) -> SquashFSXAttrList |
None`; `read_and_decode_xattr(image, entry, table=None) -> DecodedXAttr`.

## 4. Root inode resolution

Canonical opening: read the superblock, call
`decode_metadata_reference(superblock.root_inode)`, build an inode stream at
`superblock.inode_table_start`, then `read_inode()`. Its header gives the root
inode number. Require a basic or extended directory body; otherwise raise a
future typed root/not-directory error, preserving lower-level causes. No new
root parser is needed.

## 5. Directory traversal semantics

`read_directory()` reads the declared sequential stream through the metadata
stream, so it spans metadata blocks. It preserves on-disk order, raw byte
names, calculated inode number, on-disk type, and child reference. Basic and
extended directories already share this API. It does not decode UTF-8 or reject
duplicates/NUL; graph code must retain evidence and resolve a child with the
existing `read_inode(inode_stream, record.inode_reference)`.

## 6. Path representation

Canonical identity is a tuple of raw `bytes` components; root is `()`. Nodes
expose `raw_name: bytes | None` and absolute `bytes` paths joined only by `/`.
This preserves invalid UTF-8 and prevents Windows/host normalization.

## 7. Node and identity models

Stage 23B should use frozen non-recursive values:

```python
SquashFSInodeIdentity(reference, inode_number)
SquashFSPathNode(filesystem, identity, inode, raw_name, parent_path,
                 absolute_path, node_type)
SquashFSDirectoryNode / SquashFSRegularFileNode / SquashFSSymlinkNode
SquashFSUnsupportedNode
SquashFSDirectoryListing(directory_path, children)
```

The frozen filesystem owner is excluded from equality/repr. Path-node equality
is filesystem identity plus raw absolute path; inode identity is separate.
Nodes never contain recursive parent/child object references.

## 8. Hard-link policy

Directory-entry identity is `(parent path, raw name, occurrence)`; path identity
is raw absolute path; inode identity is `(metadata reference, inode number)`.
Two hard-link paths get distinct nodes sharing an inode identity. `nlink` is
evidence only: basic regular bodies lack it. Reference/number disagreement is a
typed malformed-graph error. Directory hard-link validity is not established.

## 9. Cycle detection

During walk/index construction track the active stack of directory inode
identities. A directory child already active raises
`SquashFSDirectoryCycleError` with path/reference. Do not use global visited as
cycle detection: another path to a completed directory remains enumerable, and
non-directory hard links are never cycles.

## 10. Symlink policy

Symlink nodes are leaves. An explicit future `readlink()` delegates to the
existing typed reader, retaining its UTF-8/error behavior. Tree construction and
ordinary lookup never follow targets or use the host filesystem.

## 11. Special inode policy

Current `INODE_BODY_PARSERS` supports only types 1, 2, 3, 8, 9, and 10.
Block/character devices, FIFO and socket layouts are not parsed. Stage 23 does
not invent parsers: retain a recognizable directory record as an
`SquashFSUnsupportedNode` only where possible; an unreadable child inode is a
typed graph-read failure chained from `read_inode()`.

## 12. Lazy/eager architecture

Choose hybrid lazy construction. Opening a filesystem/root reads one inode;
`list_children()` explicitly materializes one immutable tuple. `walk_filesystem`
and `build_index` are explicit eager operations with per-operation caches and
the active-stack cycle check. There is no hidden mutable global cache.

## 13. Public APIs

```python
open_filesystem(image: SquashFSImage) -> SquashFSFilesystem
get_root(filesystem: SquashFSFilesystem) -> SquashFSDirectoryNode
list_children(filesystem: SquashFSFilesystem, directory: SquashFSDirectoryNode)
    -> tuple[SquashFSPathNode, ...]
lookup_path(filesystem: SquashFSFilesystem, path: bytes) -> SquashFSPathNode
walk_filesystem(filesystem: SquashFSFilesystem) -> Iterator[SquashFSPathNode]
```

The initial stable lookup input is bytes absolute paths only; text convenience
is deferred. Symlinks are not followed.

## 14. Content/XAttr integration

Keep I/O in standalone dispatch helpers initially: select existing
basic/extended file readers, select existing symlink readers, use
`read_directory`, and expose XAttrs through `read_inode_xattrs` followed by
explicit `read_and_decode_xattr`. Frozen nodes retain context but need not gain
broad I/O methods in 23B.

## 15. Error hierarchy

Use `SquashFSFilesystemGraphError` with `SquashFSRootError`,
`SquashFSPathError`, `SquashFSPathNotFoundError`, `SquashFSNotDirectoryError`,
`SquashFSDirectoryCycleError`, `SquashFSDuplicateNameError`, and
`SquashFSGraphReadError`. Preserve lower-level causes; missing, not-directory,
duplicate, cycle, and malformed transport remain distinct.

## 16. Duplicate-name policy

Listings preserve every record in on-disk order. Lookup with more than one
matching raw component raises `SquashFSDuplicateNameError`; it never picks
first/last. Occurrence identity retains forensic evidence.

## 17. Path normalization/lookup rules

Accept only bytes absolute paths. `/` means root. Reject empty/relative paths,
NUL components, `.`, `..`, repeated `/`, and trailing `/` rather than
normalizing. Invalid UTF-8 is valid in bytes lookup. Missing components raise
path-not-found; regular-file or symlink intermediates raise not-directory.

## 18. Traversal ordering

Preserve `read_directory()` on-disk order. Do not sort decoded or raw names;
sorted views are a future explicit API.

## 19. ROOTFS research findings

Read-only traversal of `E:\UDM_PRO\Extracted\rootfs` found a basic-directory
root at `(369128, 2283)`, inode number 43427, with 13 root entries. It measured
43,432 directory entries, 43,427 unique inode references, five repeated
reference hard-link candidates, and maximum depth 17. Counts: 5,312 basic
directories, 17 extended directories, 35,940 basic regular files, 12 extended
regular files, and 2,152 basic symlinks. Invalid UTF-8 names, duplicate names,
cycles, unresolved children, and unsupported encountered types were all zero.
The deterministic discovered path for `security.capability` is `b"/bin/ping"`.

## 20. Test architecture

Future synthetic tests cover basic/extended/malformed/non-directory roots;
empty/nested/boundary-crossing directories and ordering; bytes lookup and every
rejected normalization case; invalid UTF-8 and duplicates; same inode at two
paths; reference/number mismatch; self/ancestor cycles; regular hard links;
all six supported bodies; unsupported children; file, symlink, XAttr and
semantic-XAttr access; immutable results; and cause chaining. ROOTFS tests
cover root lookup, traversal, and `/bin/ping` XAttr discovery.

## 21. Stage decomposition

- **23B:** frozen filesystem/identity/node models and root opening.
- **23C1:** lazy directory listings and path-node construction.
- **23C2:** bytes lookup, duplicate policy, and path errors.
- **23C3:** explicit traversal/index, hard links, cycles, and tests.
- **23D:** content/XAttr integration and ROOTFS validation.
- **23E:** audit, documentation, full regression, commit readiness.

## 22. Deferred scope

No special-inode parsers, symlink following, text paths, host normalization,
extraction, mutable global cache, ACL/SELinux decoding, or CLI.

## Stage 23B implementation facts

Stage 23B implements frozen `SquashFSInodeIdentity(reference, inode_number)`,
`SquashFSFilesystem(image, superblock, inode_stream, root_inode,
root_identity)`, and frozen path-node models with the exact shared fields
`filesystem`, `identity`, `inode`, `raw_name`, `parent_path`,
`absolute_path`, and `node_type`. The concrete node models are
`SquashFSDirectoryNode`, `SquashFSRegularFileNode`, `SquashFSSymlinkNode`, and
`SquashFSUnsupportedNode`; `SquashFSNodeType` has `DIRECTORY`,
`REGULAR_FILE`, `SYMLINK`, and `UNSUPPORTED`.

The Stage 23B errors are `SquashFSFilesystemGraphError`, `SquashFSRootError`,
`SquashFSGraphReadError`, and `SquashFSNodeTypeError`. Public root APIs are
`open_filesystem(image: SquashFSImage) -> SquashFSFilesystem` and
`get_root(filesystem: SquashFSFilesystem) -> SquashFSDirectoryNode`.
`open_filesystem()` reads only the superblock and root inode; it neither reads
directory entries, XAttrs, file payloads, nor symlink targets. The root node is
always `raw_name=None`, `parent_path=None`, `absolute_path=b"/"`, and directory
typed. Nodes validate filesystem, identity, inode, root/path, and body/type
invariants directly; no malformed model is repaired.

## Stage 23C1 implementation facts

`SquashFSDirectoryListing(directory_path, children)` is frozen and preserves an
ordered tuple of path nodes. `list_children(filesystem, directory)` reads the
existing directory reader once, resolves each record through `read_inode`,
validates record/inode identity, and creates path-specific directory, regular,
or symlink nodes without recursion. Child names remain raw bytes and reject
empty, slash, NUL, dot, and dot-dot entries. Duplicates and hard links are
preserved as separate path nodes; cycle detection remains deferred to 23C3.
Directory/read/entry failures use `SquashFSDirectoryReadError`,
`SquashFSChildInodeError`, and `SquashFSDirectoryEntryError` with low-level
causes retained. The operation does not read content, symlink targets, XAttrs,
semantic XAttrs, or use the inode-number lookup table.

## 23. Checked / Known / Do not know

| Status | Fact |
|---|---|
| Checked | Root uses the superblock metadata reference and current readers resolve it. |
| Checked | Directory names are bytes and records retain on-disk order. |
| Checked | The stated ROOTFS measurements and `/bin/ping` path were computed with current APIs. |
| Known | Current inode dispatch supports exactly the six listed directory/regular/symlink types. |
| Do not know | Directory hard-link constraints and special-inode layouts. |
| Do not know | Text-path policy; it is intentionally deferred. |

## Stage 23 final implementation

Stage 23C2--D implements `lookup_path`, `walk_filesystem`, immutable
`SquashFSFilesystemIndex`, `build_filesystem_index`, `node_for_path`,
`paths_for_inode`, `read_node_bytes`, `read_node_symlink`, and
`read_node_xattrs`. Lookup accepts only exact absolute raw-byte components;
it does not normalize, decode, follow symlinks, or invoke the inode-number
resolver. Traversal is depth-first preorder in directory-record order, with an
active inode-identity stack for structural directory-cycle detection. An index
preserves that order, maps every unique absolute path, and groups all paths for
each inode identity. It uses immutable mapping proxies and never reads payloads
or XAttrs. The content helpers are explicit delegations to the existing typed
file/symlink/XAttr readers; semantic XAttrs retain the existing
`read_and_decode_xattr` public operation.

## Stage 23D content boundary

`read_node_bytes(filesystem, node)` delegates only to the established basic or
extended regular-file reader. `read_node_symlink(filesystem, node)` similarly
delegates to the typed symlink reader and never follows the returned text.
`read_node_xattrs(filesystem, node, table=None)` delegates to
`read_inode_xattrs`; semantic dispatch remains the explicit
`read_and_decode_xattr(image, entry, table=None)` operation, so no redundant
node semantic wrapper is introduced. All graph construction operations leave
content, symlink targets, raw XAttrs, and semantic decoding lazy. Reader errors
are chained through `SquashFSNodeContentError` while node values remain frozen.

## Final audit reconciliation

The implemented graph follows the intended one-way layering: Stage 23 consumes
Stages 18--22, traversal builds the index, and lookup never constructs an
index.  Final graph construction has no content/XAttr reads, while explicit
node-content helpers delegate to existing readers and symlinks remain leaves.
