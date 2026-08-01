# Semantic XAttr dispatch ROOTFS validation - Stage 22D

## Scope

This validation exercises the Stage 22 semantic dispatcher and its lazy
single-entry wrapper against the embedded UDM Pro ROOTFS. It does not infer
capability enforcement, scan an inode path, or change the XAttr transport.

## Checked live value

The XAttr ID table's ID 0 list contains an inline entry with
`full_name == b"security.capability"`. Its exact 20-byte value is:

```
0100000200200000000000000000000000000000
```

`read_and_decode_xattr(image, entry, table)` returns a known `DecodedXAttr`
with kind `LINUX_FILE_CAPABILITIES` and decoder ID
`linux.security.capability`. Its semantic value is revision 2, effective true,
permitted raw mask `0x2000`, permitted numbers `(13,)`, known name
`('CAP_NET_RAW',)`, an empty inheritable set, and `root_id is None`.

## Dispatcher and lazy-wrapper evidence

The live wrapper result equals `decode_xattr_semantic(entry, entry.value)`.
With the public OOL resolver patched to fail, the live inline wrapper call
succeeds and makes zero resolver calls. The entry, table, raw value, and
decoded result remain immutable.

## Synthetic complement

`XAttrSemanticROOTFSStage22DTest` also uses physical synthetic SquashFS images
to exercise OOL capability and unknown values, exact-name matching, transport
and semantic cause chains, and repeated immutable snapshots. This complements
the real image, whose observed capability is inline.

## Not verified from this ROOTFS

- A deterministic filesystem path for the XAttr-bearing inode.
- A real OOL XAttr, unknown XAttr, capability revision 1 or 3 value, root-ID
  value, or unknown future capability bit.
- Independent external-tool decoding or host capability enforcement behavior.
