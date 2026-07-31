# Linux `security.capability` decoder architecture - Stage 21A

## Scope

Research and architecture only. Stage 21 consumes opaque inline values from
Stage 19 or OOL bytes returned by Stage 20; it does not alter SquashFS metadata
traversal, entries, or resolution.

## Authoritative sources inspected

- Linux UAPI [`include/uapi/linux/capability.h`](https://github.com/torvalds/linux/blob/master/include/uapi/linux/capability.h)
- Linux [`security/commoncap.c`](https://github.com/torvalds/linux/blob/master/security/commoncap.c)

## Known from Linux format

`VFS_CAP_REVISION_MASK=0xff000000`; revisions 1, 2, and 3 are respectively
`0x01000000`, `0x02000000`, and `0x03000000`. `VFS_CAP_FLAGS_MASK=0x00ffffff`;
`VFS_CAP_FLAGS_EFFECTIVE=0x000001`. `VFS_CAP_U32_1=1`, `VFS_CAP_U32_2=2`.
`XATTR_CAPS_SZ_1=12`, `XATTR_CAPS_SZ_2=20`, and `XATTR_CAPS_SZ_3=24` bytes.

All fields are little-endian u32. `struct vfs_cap_data` is `magic_etc` followed
by `data[]`, where each element is `permitted`, then `inheritable`. Revision 1
has one element (12 bytes); revision 2 has two (20 bytes). `struct
vfs_ns_cap_data` is revision-2 layout plus `rootid` (24 bytes) for revision 3.
Words zero and one encode bits 0-31 and 32-63; the effective set is derived
from the effective flag, not stored as a third bitset. Ambient and bounding sets
are not fields in this XAttr. Kernel code reads `rootid` with `le32_to_cpu` and
maps it through filesystem/user namespaces; a raw decoder must preserve it as
an unsigned numeric root ID and must not claim host-namespace meaning.

Extract revision with `magic_etc & VFS_CAP_REVISION_MASK`; flags are
`magic_etc & VFS_CAP_FLAGS_MASK`. Stage 21B should reject unknown revisions and
unknown flag bits rather than silently discard them. Revision/length pairs must
match exactly; empty, short, trailing, or revision-mismatched input is rejected.
Capability bits above Analyzer's fixed, source-confirmed name table are retained
numerically. Parsing must not depend on host headers or host `CAP_LAST_CAP`.

## Proposed models and API

Stage 21B implements frozen dataclasses: `LinuxCapabilitySet(raw_mask,
capability_numbers)` and `LinuxFileCapabilities(revision,
effective, permitted, inheritable, root_id, raw_magic_etc, raw_value)`. A small
integer-backed `LinuxCapabilityRevision` enum is appropriate. Preserve all raw
fields and represent revision-1 sets as 64-bit masks with the high word zero.

Public decoder: `decode_linux_file_capabilities(value: bytes) ->
LinuxFileCapabilities`. Stage 21 should expose this raw-byte semantic decoder
only. A SquashFS-entry helper is deferred to a later generic XAttr export stage:
it would otherwise couple namespace/name and OOL acquisition policy to semantic
decoding.

Use stable `LinuxCapabilityError` as the public base, with type, size,
revision, and flags subclasses only where callers benefit. Lower-level unpack
errors must be chained; direct semantic validation errors need no cause.

## Checked: UDM Pro ROOTFS

Production Stage 18/19 APIs read `security.capability` as 20 bytes:
`01 00 00 02 00 20 00 00 00 00 00 00 00 00 00 00 00 00 00 00`.
Little-endian u32 words are `0x02000001`, `0x00002000`, `0x00000000`,
`0x00000000`, `0x00000000`. Thus format bits indicate revision 2; flags are
`0x000001`; permitted words are `0x00002000`, `0x00000000`; inheritable words
are zero. There is no rootid in revision 2. This observation records raw facts,
not semantic capability-name interpretation.

## Test architecture and stages

## Stage 21C1 implementation-final mapping policy

Analyzer embeds an immutable authoritative mapping for capability numbers 0
through 40, with `LINUX_CAP_LAST_KNOWN = 40` and highest name
`CAP_CHECKPOINT_RESTORE`. It does not consult host capability state. The final
`LinuxCapabilitySet` fields are `raw_mask`, `capability_numbers`,
`known_names`, and `unknown_numbers`. Numbers are all set bits in ascending
order; names follow the same known-number order; unknown future bits are kept
numerically in `unknown_numbers` rather than rejected. Direct construction
strictly requires every tuple to equal the values derived from `raw_mask` and
the embedded mapping. Stage 21C1 ends at raw classification; XAttr integration
and any further semantic export remain deferred.

Stage 21B: constants, frozen models, raw decoder. Stage 21C1: revision/size/
flags and malformed inputs. Stage 21C2: fixed capability-number/name table,
high/unknown bits. Stage 21C3: optional XAttr integration decision revisit.
Stage 21D: ROOTFS regression using documented bytes without requiring ROOTFS.
Stage 21E: audit and commit.

## Checked / Known / Do not know

| Status | Item |
|---|---|
| Checked | ROOTFS has a 20-byte revision-2 raw value shown above. |
| Known | Linux layout, masks, sizes, word ordering, and namespace-sensitive rootid handling. |
| Do not know | Whether another UDM image contains revision 1 or 3 values; no host namespace can be inferred from raw rootid alone. |
