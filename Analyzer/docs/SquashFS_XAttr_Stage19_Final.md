# SquashFS XAttr Entry List — Stage 19 Final Acceptance

## 1. Status

**Accepted.** Stage 19 parses SquashFS XAttr entry lists, exposes immutable
typed results, preserves Stage 18 lazy ID lookup, and has synthetic plus real
UDM Pro ROOTFS evidence. The final verification recorded 197 XAttr tests and
368 full-suite tests passing.

## 2. Scope and exclusions

Stage 19 covers entry-list parsing, namespaces, inline values, OOL list-side
references, list validation, and inode integration. It does not dereference an
OOL target, decode ACL/capability/SELinux payloads, extract host xattrs, add a
CLI, alter images, repack firmware, or sign firmware. Those interpretation and
dereference tasks are Stage 20 work.

## 3. Linux format facts audit

| Fact and source symbol | Stage 19 status |
|---|---|
| `squashfs_xattr_entry`: `__le16 type`, `__le16 size`, `char data[]` | Implemented as `<HH>` plus raw name bytes. |
| `squashfs_xattr_val`: `__le32 vsize`, `char value[]` | Implemented as `<I>` plus inline bytes or OOL representation. |
| `SQUASHFS_XATTR_PREFIX_MASK == 0xff` | Implemented. |
| `SQUASHFS_XATTR_VALUE_OOL == 0x100` | Implemented. |
| Namespace values user/trusted/security = 0/1/2 | Implemented as `user.`, `trusted.`, `security.`. |
| Unknown namespace | Preserved losslessly; no prefix is invented. |
| OOL list representation | `vsize == 8`, decoded as little-endian u64. |
| OOL target following in `xattr.c` | Deferred to Stage 20. |
| `squashfs_xattr_lookup` ID indexing | Implemented zero-based; ID 0 valid. |
| Extended inode `0xffffffff` XAttr sentinel | Implemented as `xattr_id is None`. |
| Metadata reads in `xattr.c` | Implemented through `SquashFSMetadataStream`. |
| Cross-block metadata traversal | Implemented through `advance_reference()`. |
| ID record list size | Entry bytes plus only valid zero alignment padding are accepted. |

Sources are Linux `fs/squashfs/squashfs_fs.h` (`squashfs_xattr_entry`,
`squashfs_xattr_val`, `SQUASHFS_XATTR_*`), `fs/squashfs/xattr.c`, and
`fs/squashfs/xattr_id.c`; source facts are distinct from Analyzer's strict
validation policy below.

## 4. Architecture and public API

Stable Stage 19 APIs:

- `decode_xattr_namespace(raw_type) -> SquashFSXAttrNamespace`
- `read_xattr_list(image, xattr_id, table=None) -> SquashFSXAttrList`
- `read_inode_xattrs(image, inode, table=None) -> SquashFSXAttrList | None`

`read_xattr_list()` obtains a Stage 18 table when omitted, validates the ID,
then reads fields through the metadata stream. `read_inode_xattrs()` returns
`None` without table access for an inode without an XAttr ID; ID 0 is resolved
normally. Stage 18 `read_xattr_id_table()` and `read_xattr_id()` remain the
table and ID APIs, not replacements for Stage 19 APIs.

## 5. Immutable models

`SquashFSXAttrNamespace`, `SquashFSXAttrEntry`, and `SquashFSXAttrList` are
frozen dataclasses. Their normal dataclass equality and representation are
therefore value-based and immutable. Names and inline values remain exact raw
`bytes`; list entries are a tuple. `SquashFSXAttrEntry.raw_type` preserves the
full on-disk type. `SquashFSXAttrNamespace.raw_type` is the decoded low-byte
namespace value used for mapping.

For inline entries, `out_of_line=False`, `value` is bytes, and
`out_of_line_reference=None`. For OOL entries, `out_of_line=True`, `value=None`,
and `out_of_line_reference` is an integer. `xattr_id.count` and `xattr_id.size`
preserve the declared values; `consumed_size` excludes permitted alignment
padding and counts only parsed entry bytes.

## 6. Errors and validation

`SquashFSXAttrListError` reports list-size and padding validation. Its
subclasses `SquashFSXAttrEntryError` and `SquashFSXAttrValueError` distinguish
entry/name from value/reference failure. `SquashFSXAttrInodeError` wraps any
Stage 18/19 XAttr error reached through `read_inode_xattrs()`. Stage 18
`SquashFSXAttrTableError` and `SquashFSXAttrIDError` remain visible at their
own public APIs and become the `__cause__` of an inode error when reached via
the inode API.

Metadata and unpack failures use `raise ... from error`; direct semantic
checks (OOL `vsize != 8`, non-zero/excessive/misaligned padding, range errors)
have no artificial cause. No broad programmer-error catch is used.

The parser rejects truncated headers/names/values/references, invalid IDs,
absent or empty tables for an ID request, count/size mismatches, malformed
following blocks, OOL values other than eight bytes, non-zero trailing bytes,
padding over three bytes, and padding with an unaligned declared size. It
accepts ID 0, a zero-entry zero-size list, zero-length/binary fields, exact
un-padded lists, valid one-to-three-byte zero padding, compressed metadata,
and physical metadata-boundary traversal.

## 7. Metadata, padding, and lazy inode behavior

Separate reads advance a `SquashFSMetadataReference` with
`SquashFSMetadataStream.advance_reference()`, so an entry header, name, value
header, inline value, or OOL reference may cross physical metadata blocks.

The real ROOTFS proves that `size` can include padding: declared 40 versus 38
consumed entry bytes, followed by two zero bytes. Analyzer accepts only
one-to-three zero bytes if the declared size is four-byte aligned.

Lazy behavior is proven by `test_list_parsing_is_lazy_until_requested`,
`test_physical_inode_parsing_is_lazy`,
`test_inode_without_xattr_id_performs_no_metadata_read`,
`test_read_inode_xattrs_accesses_list_when_requested`, and
`test_sentinel_is_never_resolved_as_table_id`.

## 8. Evidence matrix

| Claim | Evidence |
|---|---|
| Namespaces, unknown types, binary and zero-length fields | Synthetic only |
| Inline values, OOL representation, OOL rejection | Synthetic only |
| Compressed metadata and metadata-boundary crossing | Synthetic only |
| ID bounds, malformed tables/lists, strict count/size errors | Synthetic only |
| Lazy behavior and sentinel distinction | Both |
| ID 0, `security.capability`, inline 20-byte value | Real ROOTFS |
| Count 1, size 40, consumed 38, two zero padding bytes | Real ROOTFS |
| OOL or boundary crossing in this ROOTFS | Not observed |
| External implementation equivalence | Not verified |

## 9. Confirmed production defects and regressions

| Defect | Root cause and correction | Regression evidence |
|---|---|---|
| Post-boundary field reads failed | Logical offsets were reused as physical references; each field now advances the metadata reference. | Entry, inline, and OOL physical-boundary tests. |
| Value failures surfaced as entry errors | Value header/value/reference reads now raise `SquashFSXAttrValueError` and chain metadata causes. | Value truncation and cause tests. |
| OOL representation accepted non-8-byte `vsize` | Enforced `vsize == 8`. | `test_malformed_ool_representation_is_rejected`. |
| Inode API leaked lower-level errors | `read_inode_xattrs()` now raises `SquashFSXAttrInodeError` from the lower error. | Inode ID-table/list wrapping tests. |
| Valid ROOTFS padding was rejected | Accept bounded zero alignment padding without including it in `consumed_size`. | `test_zero_alignment_padding_is_accepted_without_changing_consumed_size` and real ROOTFS tests. |

The first four were synthetic-test discoveries; the padding defect was exposed
by real ROOTFS parsing.

## 10. Test inventory

| Class | Tests |
|---|---:|
| `SquashFSXAttrIDTableReaderTest` | 21 |
| `SquashFSXAttrIDReaderTest` | 20 |
| `SquashFSXAttrInodeIntegrationTest` | 14 |
| `SquashFSXAttrRootfsTest` | 2 |
| `SquashFSXAttrEntryListRootFSIntegrationTest` | 8 |
| `SquashFSXAttrNamespaceTest` | 9 |
| `SquashFSXAttrEntryReaderTest` | 19 |
| `SquashFSXAttrInlineValueTest` | 24 |
| `SquashFSXAttrOutOfLineDetectionTest` | 20 |
| `SquashFSXAttrListReaderTest` | 37 |
| `SquashFSXAttrInodeListIntegrationTest` | 20 |
| **Total XAttr tests** | **194** |

Three exact namespace-prefix duplicates were removed during the final audit;
the user, trusted, and security mapping assertions remain in the corresponding
namespace tests. Tests are statically declared. No dynamic test generation, no final-result
test fixture that bypasses production parsing, and no mock replacing the
metadata parser were found. Narrow spies only observe metadata access for
lazy-behavior tests.

## 11. ROOTFS and independent comparison

The fixture is `E:\UDM_PRO\Extracted\rootfs`, 609071104 bytes, with one
XAttr ID record. Native `where.exe unsquashfs` and `where.exe sqfscat` exited
1 because the tools were absent. `wsl.exe sh -lc 'command -v unsquashfs;
unsquashfs -version'` exited 1 because no WSL distribution is installed.
No independent agreement is claimed; this is an environment limitation, not
evidence of equivalence. The measured ROOTFS result remains valuable as a
production-path compatibility check.

## 12. Stage 20 handoff and final checklist

Stage 20 may follow an OOL reference and decode its second value header/value,
then consider namespace-specific ACL, capability, and SELinux interpretation.
It must retain Stage 19's raw list-side representation and validation.

| Status | Final statement |
|---|---|
| Checked | Format, APIs, models, errors, validation, laziness, ROOTFS path, and tests audited. |
| Checked | Stage 19 XAttr tests and full regression pass. |
| Know | Synthetic coverage exercises semantic cases absent from the real image. |
| Don't know | Independent squashfs-tools equivalence and OOL target contents. |
