# SquashFS XAttr Entry List ROOTFS Validation

## ROOTFS source

The repository resolves the real fixture as `ROOT / "Extracted" / "rootfs"`
in `Analyzer/test_squashfs.py`; in this checkout it is
`E:\UDM_PRO\Extracted\rootfs`. The file exists and is 609071104 bytes.
No additional firmware image was added.

## Commands executed

```powershell
& .\.tools\python312\python.exe -c "... SquashFSImage(...); read_xattr_id_table(...); read_xattr_id(...); read_xattr_list(...) ..."
where.exe unsquashfs
where.exe sqfscat
wsl.exe sh -lc 'command -v unsquashfs; unsquashfs -version'
& .\.tools\python312\python.exe -m unittest discover -s Analyzer -p 'test_squashfs.py' -k SquashFSXAttrEntryListRootFSIntegrationTest -v
& .\.tools\python312\python.exe -m unittest discover -s Analyzer -p 'test_squashfs.py' -k SquashFSXAttr -v
```

The Analyzer investigation command exited 0. `where.exe unsquashfs` and
`where.exe sqfscat` each exited 1 (not found). The WSL command exited 1 because
no Linux distribution is installed. Consequently no independent
squashfs-tools comparison is technically available in this checkout.

## Checked image metadata

| Field | Measured value |
|---|---:|
| Magic | `0x73717368` |
| File size | 609071104 |
| `bytes_used` | 609067236 |
| Compression ID | 6 (ZSTD) |
| `xattr_id_table_start` | 609067212 |
| XAttr table present | yes |
| XAttr data start | 609067154 |
| XAttr ID records | 1 |
| ID metadata offsets | `(609067194,)` |

## Entry-list measurements

All ID records were read through `read_xattr_id()` and then parsed through
`read_xattr_list()`.

| Measure | Result |
|---|---:|
| IDs successfully parsed | `0` (one record) |
| Failed IDs | none |
| Total entries | 1 |
| User / trusted / security / unknown | 0 / 0 / 1 / 0 |
| Inline / OOL | 1 / 0 |
| Zero-length names / values | 0 / 0 |
| Declared list count, min / max | 1 / 1 |
| Declared list size, min / max | 40 / 40 |
| Consumed entry bytes | 38 |

The only entry is `security.capability`: type 2, name `capability`, inline
value size 20, value bytes
`01 00 00 02 00 20 00 00 00 00 00 00 00 00 00 00 00 00 00 00`.
Its inline representation is unambiguous: `out_of_line=False`, the value is
those exact 20 bytes, and `out_of_line_reference=None`.

## Boundary and padding observation

The XAttr data metadata block starts at 609067154, is uncompressed, has a
38-byte payload, and ends at 609067194. The sole list, entry, name, and value
are wholly inside that one physical metadata block; no real-image boundary
crossing was observed. No malformed or unsupported representation was
encountered.

The ID record declares size 40 although the one parsed entry consumes 38 bytes.
The remaining two bytes are zero alignment padding. This exposed an Analyzer
defect: Stage 19 previously required `consumed_size == declared_size`. The
reader now accepts only up to three zero bytes when the declared size is
four-byte aligned, while retaining rejection of non-zero, excessive, or
misaligned trailing bytes. A synthetic regression test covers this rule.

There is only one ID record, so duplicate IDs referencing one location and
duplicate entries across distinct lists are not applicable to this image.

## Inode association

Production inode lookup found one extended inode with XAttr ID 0 and resolved
it through `read_inode_xattrs()` to `security.capability`. Inodes without an
XAttr ID returned `None`; an extended inode with the Stage 18
`0xffffffff` sentinel was not resolved as ID 0.

## Automated ROOTFS tests

`SquashFSXAttrEntryListRootFSIntegrationTest` uses the real fixture and skips
only when that fixture is absent. It verifies table loading, ID 0 parsing, all
available list records, the measured count/size/padding result, namespace and
representation, real inode resolution, no-XAttr inode behavior, and sentinel
behavior. The class passed 8 tests in this checkout.

## Independent comparison limitation

**Checked:** native `unsquashfs` and `sqfscat` are absent, and WSL has no
distribution. Therefore no independent tool can list the visible xattrs for
this image here. **Don't know:** whole-table equivalence with squashfs-tools
and a per-file external-tool sample. Analyzer output was not used as an
independent oracle.

## Stage 20 exclusions

This validation does not dereference OOL values and does not decode ACLs,
capabilities, or SELinux labels. It does not add extraction, CLI, repacking,
or host-xattr functionality.

## Checked / Know / Don't know

| Status | Statement |
|---|---|
| Checked | This ROOTFS has one XAttr ID, ID 0; it parses as one inline `security.capability` entry. |
| Checked | Declared list size 40 contains 38 entry bytes plus two zero alignment bytes. |
| Checked | No OOL entry or real metadata-boundary crossing occurs in this image's sole list. |
| Know | Stage 19C synthetic tests cover OOL and boundary semantics independently of this image. |
| Don't know | External squashfs-tools agreement and raw OOL target contents; tools are unavailable and Stage 20 excludes OOL dereference. |
