# Semantic XAttr dispatch - Stage 22 final audit

## 1. Scope

Stage 22 adds a narrow semantic layer for one already-parsed SquashFS XAttr.
It does not change metadata parsing, add an inode-wide API, interpret security
policy, or add ACL or SELinux decoders.

## 2. Architecture

The accepted dependency direction is Stage 18 XAttr ID/list transport, Stage
19 entry transport, Stage 20 OOL value transport, Stage 21 Linux capability
decoding, then Stage 22 dispatch. Each layer depends only on the one below it:
there is no cyclic dependency.

## 3. Public APIs

`decode_xattr_semantic(entry, raw_value)` accepts a `SquashFSXAttrEntry` and a
bytes-like value, copies the value to `bytes`, and returns `DecodedXAttr`.
Invalid entry, raw-value, and full-name types raise `XAttrSemanticTypeError`.

`read_and_decode_xattr(image, entry, table=None)` accepts a `SquashFSImage`,
a `SquashFSXAttrEntry`, and optionally `SquashFSXAttrIDTable`. It validates
these arguments, obtains only that entry's value, and calls the pure API.

## 4. Registry

`XATTR_SEMANTIC_DECODERS` is source-defined `MappingProxyType`. Its sole key
is `b"security.capability"`; its frozen descriptor has decoder ID
`linux.security.capability`, kind `LINUX_FILE_CAPABILITIES`, and decoder
`decode_linux_file_capabilities`. There is no runtime registration or host
lookup.

## 5. Dispatcher

The dispatcher performs byte-exact, case-sensitive `full_name` lookup. Known
values become immutable known `DecodedXAttr` results. All other names,
including `None`, wrong case, suffixes, and binary names, succeed as immutable
`UNKNOWN` results containing `UnknownXAttrSemanticValue` and exact raw
provenance. It never accepts an image or reads metadata, XAttr lists, inodes,
or host state.

## 6. Wrapper

For an inline entry the wrapper requires `value` to be `bytes` and no OOL
reference, then dispatches that value directly. It does not inspect the table
or perform metadata, list, inode, or OOL access. For an OOL entry it requires
`value is None` and a reference, calls the Stage 20 resolver exactly once, and
dispatches the returned opaque bytes. Results and all input models are frozen;
repeated calls compare equal and do not mutate entries or a supplied table.

## 7. Transport separation

Stage 20 alone resolves OOL data through the metadata stream. The Stage 22
wrapper performs no list lookup, inode traversal, reference decoding, or
metadata-stream operation of its own. The dispatcher and Stage 21 decoder do
not perform transport.

## 8. Semantic separation

The wrapper does not interpret capability bytes. It delegates exactly once to
the dispatcher, which selects the Stage 21 decoder only after raw bytes have
already been acquired. Thus inline and OOL known values have the same semantic
result path.

## 9. ROOTFS validation

The available UDM Pro embedded ROOTFS has XAttr ID 0 with inline
`b"security.capability"`. Its 20-byte value is
`0100000200200000000000000000000000000000`. The wrapper returns a known
`DecodedXAttr` with decoder ID `linux.security.capability`; it equals direct
pure dispatch of the inline value. The decoded value is revision 2, effective,
permitted mask `0x2000`, capability number `(13,)`, known name
`('CAP_NET_RAW',)`, empty inheritable set, and no root ID. The live inline
path was checked with the OOL resolver patched to fail and made zero calls.

## 10. Synthetic validation

Synthetic physical images cover OOL capability and unknown values, supplied
and omitted tables, metadata-stream traversal, exact-name matching, malformed
inline/OOL states, repeat equality, and immutable snapshots.

## 11. Error model

Invalid public arguments raise `XAttrSemanticTypeError`. Malformed entry
transport state and a Stage 20 `SquashFSXAttrValueError` raise
`XAttrSemanticValueResolutionError`; the latter is retained as `__cause__`.
Stage 21 `LinuxCapabilityError` becomes `XAttrSemanticDecoderError` with the
original error as `__cause__`. Existing decoder errors are not rewrapped.
Unknown XAttrs are successful `UNKNOWN` results, never transport or semantic
errors.

## 12. Regression history

No Stage 22 production defect was found. One Stage 22D test initially used an
invalid payload, so it exercised semantic decoding instead of transport
failure. The regression was corrected to patch the public Stage 20 resolver
with `SquashFSXAttrValueError`; the preserved
`test_transport_failure_chain` now verifies the intended cause chain.

## 13. Checked

- Public signatures, validation, immutable models, immutable registry, exact
  key lookup, and no-runtime-registration behavior.
- Inline laziness, OOL single delegation, table pass-through, separation of
  metadata transport from semantic decoding, and error causes.
- Stage 22B (9 tests), Stage 22C2 (10 tests), and Stage 22D (10 tests): 29
  Stage 22 tests total.
- The Stage 21 classes and the full repository suite.

## 14. Known

The only current semantic decoder is the Linux `security.capability` decoder.
Its result models and raw provenance are immutable. The tested ROOTFS XAttr is
inline and has the revision-2 `CAP_NET_RAW` value stated above.

## 15. Unknown

The available ROOTFS did not establish a deterministic filesystem path for the
XAttr-bearing inode. It also did not provide a real OOL XAttr, a real unknown
XAttr, revisions 1 or 3, a root-ID value, or unknown future capability bits.

## 16. Limitations

Stage 22 intentionally does not decode ACL or SELinux values, expose runtime
decoder registration, resolve all XAttrs of an inode, or infer Linux capability
enforcement semantics. Real OOL coverage is synthetic because the available
ROOTFS entry is inline.
