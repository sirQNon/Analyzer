# SquashFS filesystem object graph - ROOTFS validation

## Scope and API path

Validation uses `E:\UDM_PRO\Extracted\rootfs` through `open_filesystem()`,
`get_root()`, `list_children()`, `lookup_path()`, `walk_filesystem()`, and
`build_filesystem_index()`.  No host-path interpretation, content read, or
XAttr read is performed by graph construction.

## Checked

The root is a basic directory with 13 children and its first on-disk child is
`b"/bin"`.  `lookup_path(fs, b"/bin/ping")` returns a regular-file node.
Traversal is depth-first preorder and the final index is immutable and ordered
like that traversal.  The measured graph has 43,433 nodes including root:
5,329 directories, 35,952 regular files, and 2,152 symlinks.  It has no
duplicate absolute paths, invalid UTF-8 names, unsupported parsed nodes, or
directory cycles; maximum depth is 17.  Five repeated inode identities are
retained as hard-link candidates rather than collapsed.

`read_node_xattrs(fs, ping)` finds `security.capability`; explicit
`read_and_decode_xattr()` decodes revision 2, effective capability mask
`0x2000`, capability 13 (`CAP_NET_RAW`), empty inheritable mask, and no root
ID.  The raw capability bytes are retained by the decoded value.

The Stage 23D helpers are explicit: `read_node_bytes` delegates to the
regular-file reader, `read_node_symlink` reads but never follows a target, and
`read_node_xattrs` delegates to the Stage 18--20 inode XAttr transport. These
operations are not invoked by opening, listing, lookup, traversal, or index
construction.

## Known limitations

Symlinks are leaf nodes and are never followed.  ACL/SELinux semantic decoding,
special inode parsing, extraction, text paths, and a CLI remain out of scope.

## Do not know

The format constraints for directory hard links and layouts of unsupported
special inode variants are intentionally not inferred by this layer.

## Final audit reconciliation

The final API measurements are 43,433 nodes, 43,432 directory entries, 5,329
directories, 35,952 regular files, 2,152 symlinks, depth 17, 43,427 identities,
and five repeated identities. `/bin/ping` has immutable inline capability bytes
`0100000200200000000000000000000000000000`, decoded as revision 2,
effective `True`, mask `0x2000`, `CAP_NET_RAW`, no inheritable capabilities,
and `root_id=None`.
