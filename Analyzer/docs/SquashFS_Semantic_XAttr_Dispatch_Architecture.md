# Generic semantic XAttr dispatch architecture - Stage 22A

## 1. Scope

Stage 22A is research and architecture only.  It defines a lazy semantic
dispatch layer over the accepted Stage 18--21 transport and raw capability
decoder APIs.  It neither changes SquashFS metadata parsing nor interprets the
security consequences of a capability.

Stage 22B implements the pure half of this design: frozen models, the
immutable registry, and `decode_xattr_semantic`.  Stage 22C2 implements the
single-entry I/O convenience wrapper; neither stage adds inode-wide decoding.

## 2. Accepted prerequisites

- Stage 18 supplies `SquashFSXAttrID`, `SquashFSXAttrIDTable`, and ID lookup.
- Stage 19 supplies `SquashFSXAttrEntry`, `SquashFSXAttrList`, and list reads.
- Stage 20 lazily resolves OOL values with `read_xattr_out_of_line_value`.
- Stage 21 decodes raw `security.capability` bytes into immutable
  `LinuxFileCapabilities`.

Linux UAPI defines the canonical names `security.capability`,
`security.selinux`, `system.posix_acl_access`, and
`system.posix_acl_default`; this stage uses that only for exact future registry
keys, not to decode ACL or SELinux value layouts.  See Linux
[`xattr.h`](https://github.com/torvalds/linux/blob/master/include/uapi/linux/xattr.h)
and [`capability.h`](https://github.com/torvalds/linux/blob/master/include/uapi/linux/capability.h).

## 3. Current transport contracts

`read_xattr_list(image, xattr_id, table=None)` requires a `SquashFSImage` and
`SquashFSXAttrID`; it reads the ID table when `table` is omitted and returns an
immutable `SquashFSXAttrList`.  Missing or invalid table/list data is reported
through `SquashFSXAttrError` subclasses.

`read_inode_xattrs(image, inode, table=None)` obtains the inode body's
`xattr_id`; it returns `None` when that field is absent, otherwise returns one
list.  It wraps transport failures as `SquashFSXAttrInodeError`.

`read_xattr_out_of_line_value(image, entry, table=None)` is the sole existing
OOL resolver.  It requires an OOL `SquashFSXAttrEntry` and a valid image; it
loads the table only when omitted, validates the XAttr metadata region, and
returns opaque `bytes`.  All its public failures are
`SquashFSXAttrValueError`, with underlying causes chained where applicable.

`decode_linux_file_capabilities(value)` accepts `bytes`, `bytearray`, or
`memoryview`, copies to immutable bytes, and returns `LinuxFileCapabilities`.
Its public errors are `LinuxCapabilityError` and the type, size, revision, and
flags subclasses.  It accesses no image or host XAttr state.

## 4. Current entry-model facts

`SquashFSXAttrNamespace` is frozen and has `raw_type: int`, `prefix: bytes |
None`, and `known: bool`.  `SquashFSXAttrEntry` is frozen and has:

- `raw_type`, `namespace`, `name: bytes`, and `full_name: bytes | None`;
- `value: bytes | None`, `value_size: int`, and `out_of_line: bool`;
- `out_of_line_reference: int | None`.

Known namespace prefixes are bytes (`b"user."`, `b"trusted."`, and
`b"security."`).  `full_name` is `prefix + name` for such a namespace and
`None` otherwise; no text decoding occurs.  Inline entries hold their raw
value in `value`, have no OOL reference, and `out_of_line` is false.  OOL
entries have `value is None`, an encoded integer reference, and require image
and optionally the ID table for resolution.  `SquashFSXAttrList` is frozen and
contains its ID record, an immutable entry tuple, and consumed size.  These
models provide deterministic dataclass equality and no mutable containers.

## 5. Dispatcher responsibility

The dispatcher may inspect an entry's full name, accept already acquired raw
bytes, select a decoder, and return a typed result retaining raw provenance.
It must not parse metadata, read an ID/list itself, resolve an OOL reference,
mutate an entry, eagerly decode inode lists, access host XAttrs, write files,
or parse ACL/SELinux values before their stages.

## 6. Pure versus I/O API separation

Adopt the two-layer API, with distinct roles:

```python
def decode_xattr_semantic(
    entry: SquashFSXAttrEntry, raw_value: bytes | bytearray | memoryview,
) -> DecodedXAttr: ...

def read_and_decode_xattr(
    image: SquashFSImage, entry: SquashFSXAttrEntry,
    table: SquashFSXAttrIDTable | None = None,
) -> DecodedXAttr: ...
```

The pure function is the primary semantic API.  Stage 22C2 implements
`read_and_decode_xattr` as a single lazy convenience wrapper: inline entries
require `entry.value` to be `bytes` and use it directly without image metadata
or table access; OOL entries require `value is None` and a reference, then call
the existing Stage 20 resolver exactly once.  It validates image, entry, and
optional table types before either path.  This does not introduce a
second generic `resolve_xattr_value` API: inline acquisition is trivial and a
separate public resolver would duplicate/blur Stage 20's responsibility.

## 7. Name-matching policy

Compare only `entry.full_name` to exact canonical bytes.  Stage 22B's first
key is `b"security.capability"`.  `None`, unknown namespace prefixes, wrong
case, suffixes, and near-matches are unsupported names; they are not decoded
as text or coerced to UTF-8.  Matching is byte-exact and case-sensitive.

## 8. Raw-value acquisition

The pure dispatcher requires bytes-like raw input and converts it to `bytes`
before constructing its result.  It never receives an image and therefore
cannot perform I/O.  The wrapper passes inline bytes directly or delegates OOL
acquisition exactly once to `read_xattr_out_of_line_value(image, entry, table)`.
It performs no list lookup, inode traversal, reference decoding, or metadata
stream work.  A supplied table is passed through unchanged; with `table=None`,
the existing Stage 20 resolver performs its normal lazy table lookup.  An
invalid inline/OOL state is rejected rather than repaired.

## 9. Registry design

Stage 22B uses an immutable source-defined mapping and frozen descriptor:

```python
@dataclass(frozen=True)
class XAttrSemanticDecoder:
    decoder_id: str
    kind: XAttrSemanticKind
    decode: object

XATTR_SEMANTIC_DECODERS = MappingProxyType({
    b"security.capability": XAttrSemanticDecoder(
        "linux.security.capability",
        XAttrSemanticKind.LINUX_FILE_CAPABILITIES,
        decode_linux_file_capabilities,
    ),
})
```

The descriptor requires a nonempty text ID, a non-`UNKNOWN` kind, and a
callable unary decoder.  No runtime registration, discovery, mutation, plugin,
or host lookup is permitted.  Future ACL names may map to the same descriptor
family; `security.selinux` may map to a different result type.

## 10. Unknown XAttr policy

Return an immutable typed unknown result, never raw bytes alone, `None`, or an
unsupported exception:

```python
@dataclass(frozen=True)
class UnknownXAttrSemanticValue:
    full_name: bytes | None
    raw_value: bytes
```

It preserves unknown binary values without falsely claiming semantic parsing.
The stable result shape remains valid when a later release adds a decoder.

## 11. Result models

Use explicit provenance:

```python
class XAttrSemanticKind(Enum):
    LINUX_FILE_CAPABILITIES = "linux_file_capabilities"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class DecodedXAttr:
    entry: SquashFSXAttrEntry
    raw_value: bytes
    kind: XAttrSemanticKind
    decoder_id: str | None
    known: bool
    semantic_value: object
```

For a known value, `decoder_id` is non-`None`, `known` is true, and the typed
value is the decoder's output.  For an unknown value, `decoder_id` is `None`,
`known` is false, and `semantic_value` is the unknown wrapper.  Stage 22B
validates these invariants in `__post_init__`: entries and raw values must be
`SquashFSXAttrEntry` and `bytes`; known results require a known kind, nonempty
ID, and non-unknown value; unknown results require the unknown kind, no ID,
an `UnknownXAttrSemanticValue`, and matching name/raw provenance.  Frozen
dataclasses and byte normalization preserve deterministic equality.

## 12. Error hierarchy and wrapping policy

Stage 22B introduces only these generic errors:

```text
XAttrSemanticError (ValueError)
|- XAttrSemanticTypeError
|- XAttrSemanticValueResolutionError
`- XAttrSemanticDecoderError
```

Invalid entry objects, full-name types, and bytes-like raw-value violations
raise `XAttrSemanticTypeError`.  `decode_xattr_semantic` catches only
`LinuxCapabilityError` and raises
`XAttrSemanticDecoderError` from it; this preserves decoder identity and its
cause while presenting one dispatch boundary.  The wrapper raises
`XAttrSemanticTypeError` for invalid wrapper arguments and
`XAttrSemanticValueResolutionError` for malformed entry transport state or a
Stage 20 `SquashFSXAttrValueError`; the latter is retained as `__cause__`.
It does not catch or rewrap `XAttrSemanticDecoderError`.  Unknown names are
successful unknown results, not errors.  No `XAttrSemanticUnsupportedError` is
needed.

## 13. Capability integration

For exact `b"security.capability"`, acquire raw bytes by the selected layer,
call `decode_linux_file_capabilities(raw_value)` once, and return a known
`DecodedXAttr`.  Inline and future OOL values share this exact decoder and
result path.  There is no ROOTFS path special case, capability re-parsing, or
host-state dependency.

## 14. ACL and SELinux extensibility

The immutable byte-key registry can map both
`b"system.posix_acl_access"` and `b"system.posix_acl_default"` to one future
ACL family/decoder ID, with their own typed result and error classes.  It can
also map `b"security.selinux"` to a future decoder whose result is bytes,
validated text, or a label dataclass.  `semantic_value` must consequently not
assume a common semantic model beyond the unknown wrapper in this stage.

## 15. Lazy semantics

Inode parsing does not call `read_inode_xattrs`; list reading does not resolve
OOL values; neither operation calls semantic dispatch.  Semantics run only on
an explicit pure-dispatch call or explicit convenience-wrapper call.  The
wrapper resolves precisely its requested OOL entry and does not traverse other
entries.

Stage 22C2 tests prove that the inline wrapper path neither invokes the OOL
resolver nor reads metadata, and that the OOL wrapper path does not call
`read_xattr_list` or `read_inode_xattrs`.

## 16. Test architecture

Stage 22 tests should cover immutable registry exactness; pure inline and
OOL-resolved capability dispatch; binary unknown values; wrong-case and
near-match unknowns; invalid entry/raw input; wrapped capability failures;
provenance, immutability, and repeat equality.  Wrapper tests should prove
inline no-I/O behavior, OOL delegation, table reuse and `None` lookup,
transport cause chaining, no mutation, and laziness.  Integration should use
the ROOTFS capability plus synthetic OOL capability and unknown entries.

## 17. Stage decomposition

- **22B:** frozen result/error models, immutable registry, pure dispatcher.
- **22C1:** exhaustive pure-dispatch, unknown, and error tests.
- **22C2:** lazy transport convenience wrapper and integration/error tests.
- **22D:** ROOTFS validation and deterministic synthetic OOL coverage.
- **22E:** final audit, documentation, and commit preparation.

## 18. Deferred scope

No Stage 22A code/tests; no ACL or SELinux binary decoder; no inode-wide
decode-all API; no registry plugins; no host state; and no security-policy
interpretation.

## 19. Checked / Known / Do not know

| Status | Fact |
|---|---|
| Checked | Current entry names and full names are `bytes`/`bytes | None`; current models are frozen. |
| Checked | Inline values are already bytes; OOL values are `None` until Stage 20 is explicitly called. |
| Checked | Stage 20 exposes the only required OOL resolver and Stage 21 exposes the unary raw capability decoder. |
| Known | Linux UAPI canonicalizes the future POSIX ACL, SELinux, and capability XAttr names. |
| Do not know | Whether the current ROOTFS contains an OOL `security.capability`; this architecture does not require it. |
| Do not know | Future ACL and SELinux result/error model details; their binary semantics are deliberately deferred. |
