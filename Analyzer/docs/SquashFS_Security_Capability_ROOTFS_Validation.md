# security.capability ROOTFS validation - Stage 21D

## Scope and environment

Checked against `E:\UDM_PRO\Extracted\rootfs` using the repository Python
interpreter and existing Stage 18/19 XAttr APIs, followed by the pure Stage 21
decoder. No capability enforcement or namespace interpretation was performed.

## Checked ROOTFS transport and decode

The XAttr table has ID 0 and its list contains the inline `security.capability`
entry (`namespace=security`, raw name `capability`, full name
`security.capability`). Its raw value is 20 bytes:
`0100000200200000000000000000000000000000`.

Decoding yields revision 2, effective true, raw magic `0x02000001`, raw flags
`0x000001`, permitted mask `0x2000`, permitted number `(13,)`, known name
`CAP_NET_RAW`, no unknown permitted numbers, empty inheritable set, and no root
ID. Raw bytes are preserved and repeated decode is equal.

## Deterministic evidence

The same raw bytes are embedded in `LinuxFileCapabilitiesRootFSStage21DTest`.
They were observed from the accepted UDM Pro ROOTFS during Stage 21A/21D, so
semantic regression does not require the image. Revisions 1 and 3, root IDs,
and future unknown bits remain synthetic-only coverage.

## Independent comparison

Not available: no independent capability tool is assumed available in this
environment, and no external tool result is claimed.

## Checked / Known / Do not know

| Status | Item |
|---|---|
| Checked | The documented inline revision-2 value and its deterministic decode. |
| Known | Revision-3 root IDs need namespace context outside this raw decoder. |
| Do not know | The deterministic filesystem path of the sole XAttr-bearing inode was not established by this validation. |
