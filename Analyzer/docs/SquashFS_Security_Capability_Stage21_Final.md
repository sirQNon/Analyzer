# Linux security.capability - Stage 21 final

## Status and scope

Stage 21 is accepted pending commit. It adds raw Linux file-capability decoding,
fixed deterministic classification, tests, and ROOTFS evidence. Deferred are
SquashFS-entry dispatch, ACL/SELinux decoding, capability enforcement, and user
namespace interpretation.

## Sources, format, and API

Linux UAPI `include/uapi/linux/capability.h` and `security/commoncap.c` define
the three little-endian layouts: Rev1 `<III>`/12 bytes, Rev2 `<IIIII>`/20 bytes,
and Rev3 `<IIIIII>`/24 bytes. Revision is `magic_etc & 0xff000000`; flags are
`magic_etc & 0x00ffffff`; only effective flag `0x1` is accepted. The API is
`decode_linux_file_capabilities(value)`. It normalizes bytes-like input once,
validates magic, revision, exact size, flags, then words; typed semantic errors
chain forced lower-level unpack failures.

Permitted/inheritable low words precede high words; high words shift by 32.
Effective is a flag-derived boolean. Rev3 root ID is preserved as raw u32.
Frozen models preserve masks, raw fields, immutable tuples, and raw bytes.

## Mapping and host independence

The immutable embedded mapping covers 0..40 (`CAP_CHOWN` through
`CAP_CHECKPOINT_RESTORE`). Known names follow ascending bit order; higher bits
remain numeric unknowns. No host headers, CAP_LAST_CAP, `/proc`, subprocess,
libcap, image, or filesystem access is used by the decoder.

## Evidence and tests

Focused inventory: Stage 21B has 12 tests, C1 has 5, and D has 2: 19 total.
Synthetic fixtures cover all revisions, malformed inputs, bit 63, unknown bits,
and root IDs. The real ROOTFS provides inline revision-2 bytes
`0100000200200000000000000000000000000000`: effective, permitted `0x2000`,
number 13, name `CAP_NET_RAW`, empty inheritable set, and no root ID.
Independent tools were unavailable (`where getcap`, `capsh`, `getfattr`, and
WSL checks).

## Defect history and handoff

One related invariant-defect family was corrected: direct `LinuxCapabilitySet`
construction initially accepted negative and inconsistent/unsorted/duplicate
derived fields. Strict derived-tuple validation now rejects them.

The next recommended step is Stage 21F/22A: generic semantic XAttr
dispatch/integration, keeping raw OOL acquisition separate from semantic decode.

## Checked / Known / Do not know

| Status | Item |
|---|---|
| Checked | Decoder, fixed mapping, deterministic fixtures, and current ROOTFS Rev2 value. |
| Known | Linux layouts and namespace-sensitive Rev3 root-ID handling. |
| Do not know | Real UDM examples for Rev1/Rev3 or an exact path for the XAttr-bearing inode. |
