# SquashFS OOL XAttr value validation - Stage 20D

## Validation environment

Checked in `E:\UDM_PRO` with the repository Python 3.12 interpreter against
`Extracted/rootfs`. Production APIs used were `read_xattr_id_table`,
`read_xattr_id`, `read_xattr_list`, `read_inode_xattrs`, and
`read_xattr_out_of_line_value`.

## Checked: real ROOTFS

The superblock is SquashFS (`magic=0x73717368`), `bytes_used=609067236`,
compression ID `6`, and `xattr_id_table_start=609067212`. The XAttr ID table
exists: it has one ID, XAttr metadata starts at `609067154`, and its sole ID
metadata block is at `609067194`.

ID 0 declares one entry and size 40; production list parsing consumed 38 bytes
and accepted two zero alignment bytes. The only entry is namespace ID 2
(`security.`), name `capability`, an inline 20-byte value, and no OOL
reference. No real OOL entries or metadata-boundary crossings were observed.
Consequently, positive `read_xattr_out_of_line_value` resolution was not
exercised on this ROOTFS.

## Checked: synthetic physical fixtures

Stage 20C1-C3 fixtures exercise a valid superblock, XAttr target metadata,
inline and OOL entries, ID metadata/table, and an inode with XAttr ID 0 through
the public APIs. They verify uncompressed single-block values; exact header and
payload boundaries; multi-block values; mixed and compressed metadata; duplicate
references; zero-length values; exact-region-end values; and a one-byte overrun
that raises `SquashFSXAttrValueError` with a preserved cause.

Expected raw target bytes match returned bytes exactly. Entries, lists, inodes,
and tables remain unchanged; repeated resolution has identical results. Values
remain opaque: this validation does not interpret capability, ACL, or SELinux
content.

## Independent comparison

Not available / not observed. Attempts were `where unsquashfs`, `where sqfscat`,
and `wsl which unsquashfs`; neither native executable was found and WSL is not
installed. No software was installed.

## Known from Linux format

OOL references identify the target little-endian `vsize` header in XAttr
metadata; the resolver returns only the following opaque payload bytes.

## Status and limitations

Stage 20D is validated against the available real ROOTFS plus deterministic
physical fixtures. A positive real-image OOL sample is not available, so that
specific observation remains unverified on UDM Pro media.
