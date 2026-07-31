# SquashFS XAttr Stage 20 final

## Objective and scope

Stage 20 adds lazy resolution of opaque SquashFS out-of-line XAttr values.
Included are the resolver, physical metadata validation, C1-C3 synthetic tests,
and D ROOTFS validation. Deferred are semantic ACL, capability, and SELinux
interpretation, caching, eager resolution, and a positive UDM Pro OOL sample.

## Format and production API

`read_xattr_out_of_line_value(image, entry, table=None) -> bytes` resolves a
Stage 19 OOL entry. Linux-format semantics used are `squashfs_xattr_val`:
little-endian u32 `vsize` followed immediately by opaque bytes. The u64
reference uses high-48 physical metadata position relative to the XAttr
metadata origin and low-16 logical uncompressed offset. It points to `vsize`;
duplicate references are valid and recursive OOL interpretation is not done.

The resolver validates entry state, u64 decoding, table/region bounds, header,
and payload before returning bytes only. It uses `SquashFSMetadataStream` for
compressed/uncompressed and boundary-crossing reads. Externally encoded offsets
at or above 8192 are invalid. An internal cursor at 8192 is valid only after
advancing through a valid block and continues at the next physical block.
Failures are `SquashFSXAttrValueError`, preserving causes for lower-level
failures. Entries, lists, inodes, and tables are not mutated; no cache exists.

## Tests and corrections

Stage 20C1-C3 provide validation, boundary/compression, and integration
fixtures; Stage 20D validates the real ROOTFS and documents it. The suite has
389 tests, including 27 focused Stage 20 tests.

Two defects were found and corrected. First, preflight rejected a payload that
began in the next metadata block after a header ended exactly at the previous
boundary. Second, the initial correction still rejected the internal transient
cursor with `byte_offset == METADATA_SIZE`; the resolver now permits that
internal cursor while rejecting external encoded offset 8192.

## ROOTFS and synthetic validation

The available ROOTFS has one inline `security.capability` XAttr and zero OOL
entries, so no positive real-image resolution was claimed. Synthetic physical
fixtures verify positive single/multi-block, compressed/mixed, duplicate,
zero-length, exact-boundary, and error paths. Independent comparison is not
available: `unsquashfs` and `sqfscat` were absent and WSL is unavailable.

## Commit scope and status

The Stage 20 commit includes `Analyzer/squashfs.py`,
`Analyzer/test_squashfs.py`, `Analyzer/docs/SquashFS_XAttr_OOL_Value_Architecture.md`,
`Analyzer/docs/SquashFS_XAttr_OOL_Value_ROOTFS_Validation.md`, and this file.
Stage 20 is ready to commit, subject to the known lack of a real OOL ROOTFS
sample.
