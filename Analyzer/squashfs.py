"""SquashFS v4 superblock reader."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum, IntEnum
from types import MappingProxyType
from pathlib import Path

import zstandard


SQUASHFS_MAGIC = 0x73717368
SUPERBLOCK_FORMAT = "<IIIIIHHHHHHQQQQQQQQ"
SUPERBLOCK_SIZE = struct.calcsize(SUPERBLOCK_FORMAT)
METADATA_HEADER_SIZE = 2
METADATA_SIZE = 8192
METADATA_UNCOMPRESSED_BIT = 1 << 15
INODE_HEADER_STRUCT = struct.Struct("<HHHHII")
INODE_HEADER_SIZE = INODE_HEADER_STRUCT.size
BASIC_DIRECTORY_INODE_TYPE = 1
BASIC_DIRECTORY_INODE_BODY_STRUCT = struct.Struct("<IIHHI")
BASIC_DIRECTORY_INODE_BODY_SIZE = BASIC_DIRECTORY_INODE_BODY_STRUCT.size
BASIC_DIRECTORY_INODE_SIZE = INODE_HEADER_SIZE + BASIC_DIRECTORY_INODE_BODY_SIZE
BASIC_REGULAR_INODE_TYPE = 2
BASIC_REGULAR_INODE_BODY_STRUCT = struct.Struct("<IIII")
BASIC_REGULAR_INODE_BODY_SIZE = BASIC_REGULAR_INODE_BODY_STRUCT.size
BASIC_REGULAR_INODE_SIZE = INODE_HEADER_SIZE + BASIC_REGULAR_INODE_BODY_SIZE
BASIC_SYMLINK_INODE_TYPE = 3
BASIC_SYMLINK_INODE_BODY_STRUCT = struct.Struct("<II")
BASIC_SYMLINK_INODE_BODY_SIZE = BASIC_SYMLINK_INODE_BODY_STRUCT.size
BASIC_SYMLINK_INODE_SIZE = INODE_HEADER_SIZE + BASIC_SYMLINK_INODE_BODY_SIZE
EXTENDED_REGULAR_INODE_TYPE = 9
EXTENDED_REGULAR_INODE_BODY_STRUCT = struct.Struct("<QQQIIII")
EXTENDED_REGULAR_INODE_BODY_SIZE = EXTENDED_REGULAR_INODE_BODY_STRUCT.size
EXTENDED_REGULAR_INODE_SIZE = INODE_HEADER_SIZE + EXTENDED_REGULAR_INODE_BODY_SIZE
EXTENDED_DIRECTORY_INODE_TYPE = 8
EXTENDED_DIRECTORY_INODE_BODY_STRUCT = struct.Struct("<IIIIHHI")
EXTENDED_DIRECTORY_INODE_BODY_SIZE = EXTENDED_DIRECTORY_INODE_BODY_STRUCT.size
EXTENDED_DIRECTORY_INODE_SIZE = INODE_HEADER_SIZE + EXTENDED_DIRECTORY_INODE_BODY_SIZE
EXTENDED_SYMLINK_INODE_TYPE = 10
EXTENDED_SYMLINK_INODE_BODY_STRUCT = struct.Struct("<III")
EXTENDED_SYMLINK_INODE_BODY_SIZE = EXTENDED_SYMLINK_INODE_BODY_STRUCT.size
EXTENDED_SYMLINK_INODE_SIZE = INODE_HEADER_SIZE + EXTENDED_SYMLINK_INODE_BODY_SIZE
DIRECTORY_INDEX_STRUCT = struct.Struct("<III")
DIRECTORY_INDEX_SIZE = DIRECTORY_INDEX_STRUCT.size
REGULAR_FILE_BLOCK_SIZE_STRUCT = struct.Struct("<I")
REGULAR_FILE_BLOCK_SIZE_ENTRY_SIZE = REGULAR_FILE_BLOCK_SIZE_STRUCT.size
SQUASHFS_INVALID_FRAGMENT = 0xFFFFFFFF
SQUASHFS_DATA_UNCOMPRESSED_BIT = 1 << 24
SQUASHFS_DATA_SIZE_MASK = SQUASHFS_DATA_UNCOMPRESSED_BIT - 1
SQUASHFS_DATA_RESERVED_MASK = 0xFE000000
FRAGMENT_ENTRY_STRUCT = struct.Struct("<QII")
FRAGMENT_ENTRY_SIZE = FRAGMENT_ENTRY_STRUCT.size
FRAGMENT_ENTRIES_PER_METADATA_BLOCK = METADATA_SIZE // FRAGMENT_ENTRY_SIZE
FRAGMENT_INDEX_POINTER_STRUCT = struct.Struct("<Q")
FRAGMENT_INDEX_POINTER_SIZE = FRAGMENT_INDEX_POINTER_STRUCT.size
DIRECTORY_HEADER_STRUCT = struct.Struct("<III")
DIRECTORY_HEADER_SIZE = DIRECTORY_HEADER_STRUCT.size
DIRECTORY_ENTRY_STRUCT = struct.Struct("<HhHH")
DIRECTORY_ENTRY_SIZE = DIRECTORY_ENTRY_STRUCT.size
DIRECTORY_NAME_MAX = 256
DIRECTORY_POSITION_OFFSET = 3
SQUASHFS_INVALID_BLK = 0xFFFFFFFFFFFFFFFF
INODE_LOOKUP_ENTRY_STRUCT = struct.Struct("<Q")
INODE_LOOKUP_ENTRY_SIZE = INODE_LOOKUP_ENTRY_STRUCT.size
XATTR_ID_TABLE_STRUCT = struct.Struct("<QII")
XATTR_ID_STRUCT = struct.Struct("<QII")
XATTR_ID_SIZE = XATTR_ID_STRUCT.size
VFS_CAP_REVISION_MASK = 0xFF000000
VFS_CAP_REVISION_1 = 0x01000000
VFS_CAP_REVISION_2 = 0x02000000
VFS_CAP_REVISION_3 = 0x03000000
VFS_CAP_FLAGS_MASK = 0x00FFFFFF
VFS_CAP_FLAGS_EFFECTIVE = 0x000001
VFS_CAP_U32_1 = 1
VFS_CAP_U32_2 = 2
XATTR_CAPS_SZ_1 = 12
XATTR_CAPS_SZ_2 = 20
XATTR_CAPS_SZ_3 = 24
LINUX_CAP_LAST_KNOWN = 40
LINUX_CAPABILITY_NAMES = MappingProxyType(dict(enumerate((
    "CAP_CHOWN", "CAP_DAC_OVERRIDE", "CAP_DAC_READ_SEARCH", "CAP_FOWNER", "CAP_FSETID", "CAP_KILL", "CAP_SETGID", "CAP_SETUID", "CAP_SETPCAP", "CAP_LINUX_IMMUTABLE", "CAP_NET_BIND_SERVICE", "CAP_NET_BROADCAST", "CAP_NET_ADMIN", "CAP_NET_RAW", "CAP_IPC_LOCK", "CAP_IPC_OWNER", "CAP_SYS_MODULE", "CAP_SYS_RAWIO", "CAP_SYS_CHROOT", "CAP_SYS_PTRACE", "CAP_SYS_PACCT", "CAP_SYS_ADMIN", "CAP_SYS_BOOT", "CAP_SYS_NICE", "CAP_SYS_RESOURCE", "CAP_SYS_TIME", "CAP_SYS_TTY_CONFIG", "CAP_MKNOD", "CAP_LEASE", "CAP_AUDIT_WRITE", "CAP_AUDIT_CONTROL", "CAP_SETFCAP", "CAP_MAC_OVERRIDE", "CAP_MAC_ADMIN", "CAP_SYSLOG", "CAP_WAKE_ALARM", "CAP_BLOCK_SUSPEND", "CAP_AUDIT_READ", "CAP_PERFMON", "CAP_BPF", "CAP_CHECKPOINT_RESTORE",
))))


@dataclass(frozen=True)
class SquashFSSuperBlock:
    """On-disk SquashFS v4 superblock."""

    magic: int
    inode_count: int
    mkfs_time: int
    block_size: int
    fragment_count: int
    compression: int
    block_log: int
    flags: int
    id_count: int
    version_major: int
    version_minor: int
    root_inode: int
    bytes_used: int
    id_table_start: int
    xattr_id_table_start: int
    inode_table_start: int
    directory_table_start: int
    fragment_table_start: int
    lookup_table_start: int


@dataclass(frozen=True)
class SquashFSMetadataBlock:
    """One decoded SquashFS metadata block."""

    offset: int
    stored_size: int
    is_compressed: bool
    data: bytes
    next_offset: int


class LinuxCapabilityRevision(IntEnum):
    REVISION_1 = VFS_CAP_REVISION_1
    REVISION_2 = VFS_CAP_REVISION_2
    REVISION_3 = VFS_CAP_REVISION_3


@dataclass(frozen=True)
class LinuxCapabilitySet:
    raw_mask: int
    capability_numbers: tuple[int, ...]
    known_names: tuple[str, ...]
    unknown_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.raw_mask < 0:
            raise ValueError("Capability mask must not be negative")
        expected_numbers = tuple(bit for bit in range(max(1, self.raw_mask.bit_length())) if self.raw_mask & (1 << bit))
        expected_names = tuple(LINUX_CAPABILITY_NAMES[number] for number in expected_numbers if number in LINUX_CAPABILITY_NAMES)
        expected_unknown = tuple(number for number in expected_numbers if number not in LINUX_CAPABILITY_NAMES)
        if (self.capability_numbers, self.known_names, self.unknown_numbers) != (expected_numbers, expected_names, expected_unknown):
            raise ValueError("Capability numbers must be unique non-negative ascending tuple")


@dataclass(frozen=True)
class LinuxFileCapabilities:
    revision: LinuxCapabilityRevision
    effective: bool
    permitted: LinuxCapabilitySet
    inheritable: LinuxCapabilitySet
    root_id: int | None
    raw_magic_etc: int
    raw_flags: int
    raw_value: bytes


@dataclass(frozen=True)
class SquashFSMetadataReference:
    """A location in a decompressed SquashFS metadata stream."""

    block_offset: int
    byte_offset: int


@dataclass(frozen=True)
class SquashFSInodeReference:
    raw_value: int
    block: int
    offset: int


@dataclass(frozen=True)
class SquashFSInodeLookupTable:
    lookup_table_start: int
    inode_count: int
    metadata_block_offsets: tuple[int, ...]
    next_table: int


@dataclass(frozen=True)
class SquashFSXAttrReference:
    """Relative metadata reference stored by a SquashFS xattr ID."""
    block: int
    offset: int


@dataclass(frozen=True)
class SquashFSXAttrID:
    index: int
    encoded_reference: int
    count: int
    size: int
    reference: SquashFSXAttrReference


@dataclass(frozen=True)
class SquashFSXAttrIDTable:
    table_start: int
    xattr_table_start: int
    xattr_ids: int
    metadata_block_offsets: tuple[int, ...]
    unused: int


@dataclass(frozen=True)
class SquashFSXAttrNamespace:
    raw_type: int
    prefix: bytes | None
    known: bool


@dataclass(frozen=True)
class SquashFSXAttrEntry:
    raw_type: int
    namespace: SquashFSXAttrNamespace
    name: bytes
    full_name: bytes | None
    value: bytes | None
    value_size: int
    out_of_line: bool
    out_of_line_reference: int | None


class XAttrSemanticKind(Enum):
    UNKNOWN = "unknown"
    LINUX_FILE_CAPABILITIES = "linux_file_capabilities"


class XAttrSemanticError(ValueError):
    """An XAttr cannot be dispatched to a semantic decoder."""


class XAttrSemanticTypeError(XAttrSemanticError):
    """A semantic-dispatch API argument has an invalid type."""


class XAttrSemanticDecoderError(XAttrSemanticError):
    """A registered semantic decoder rejected an otherwise valid value."""


class XAttrSemanticValueResolutionError(XAttrSemanticError):
    """An XAttr value cannot be obtained through the transport layer."""


@dataclass(frozen=True)
class UnknownXAttrSemanticValue:
    full_name: bytes | None
    raw_value: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.full_name, (bytes, type(None))):
            raise ValueError("Unknown xattr full name must be bytes or None")
        if not isinstance(self.raw_value, bytes):
            raise ValueError("Unknown xattr raw value must be bytes")


@dataclass(frozen=True)
class XAttrSemanticDecoder:
    decoder_id: str
    kind: XAttrSemanticKind
    decode: object

    def __post_init__(self) -> None:
        if not isinstance(self.decoder_id, str) or not self.decoder_id:
            raise ValueError("Xattr semantic decoder ID must be non-empty text")
        if not isinstance(self.kind, XAttrSemanticKind) or self.kind is XAttrSemanticKind.UNKNOWN:
            raise ValueError("Xattr semantic decoder kind must be known")
        if not callable(self.decode):
            raise ValueError("Xattr semantic decoder must be callable")


@dataclass(frozen=True)
class DecodedXAttr:
    entry: SquashFSXAttrEntry
    raw_value: bytes
    kind: XAttrSemanticKind
    decoder_id: str | None
    known: bool
    semantic_value: object

    def __post_init__(self) -> None:
        if not isinstance(self.entry, SquashFSXAttrEntry):
            raise ValueError("Decoded xattr entry must be a SquashFSXAttrEntry")
        if not isinstance(self.raw_value, bytes):
            raise ValueError("Decoded xattr raw value must be bytes")
        if not isinstance(self.kind, XAttrSemanticKind):
            raise ValueError("Decoded xattr kind is invalid")
        if not isinstance(self.known, bool):
            raise ValueError("Decoded xattr known flag must be bool")
        if self.known:
            if self.kind is XAttrSemanticKind.UNKNOWN or not isinstance(self.decoder_id, str) or not self.decoder_id:
                raise ValueError("Known decoded xattr requires a known kind and decoder ID")
            if isinstance(self.semantic_value, UnknownXAttrSemanticValue):
                raise ValueError("Known decoded xattr cannot contain an unknown value")
        else:
            if self.kind is not XAttrSemanticKind.UNKNOWN or self.decoder_id is not None:
                raise ValueError("Unknown decoded xattr must have unknown kind and no decoder ID")
            if not isinstance(self.semantic_value, UnknownXAttrSemanticValue):
                raise ValueError("Unknown decoded xattr requires an unknown value")
            if (self.semantic_value.full_name, self.semantic_value.raw_value) != (self.entry.full_name, self.raw_value):
                raise ValueError("Unknown decoded xattr provenance does not match its entry")


@dataclass(frozen=True)
class SquashFSXAttrList:
    xattr_id: SquashFSXAttrID
    entries: tuple[SquashFSXAttrEntry, ...]
    consumed_size: int


@dataclass(frozen=True)
class SquashFSInodeHeader:
    """The common on-disk prefix of every SquashFS inode."""

    inode_type: int
    mode: int
    uid: int
    guid: int
    mtime: int
    inode_number: int


@dataclass(frozen=True)
class SquashFSBasicDirectoryInode:
    """The on-disk SquashFS v4 basic directory inode."""

    header: SquashFSInodeHeader
    start_block: int
    nlink: int
    file_size: int
    offset: int
    parent_inode: int


@dataclass(frozen=True)
class SquashFSBasicRegularInode:
    """The on-disk SquashFS v4 basic regular-file inode."""

    header: SquashFSInodeHeader
    start_block: int
    fragment: int
    offset: int
    file_size: int


@dataclass(frozen=True)
class SquashFSBasicSymlinkInode:
    """The on-disk SquashFS v4 basic symbolic-link inode."""

    header: SquashFSInodeHeader
    nlink: int
    symlink_size: int


@dataclass(frozen=True)
class SquashFSExtendedRegularInode:
    """The on-disk SquashFS v4 extended regular-file inode."""
    header: SquashFSInodeHeader
    start_block: int
    file_size: int
    sparse: int
    nlink: int
    fragment: int
    offset: int
    xattr: int
    @property
    def xattr_id(self) -> int | None:
        return None if self.xattr == 0xffffffff else self.xattr


@dataclass(frozen=True)
class SquashFSExtendedDirectoryInode:
    """The on-disk SquashFS v4 extended directory inode."""
    header: SquashFSInodeHeader
    nlink: int
    file_size: int
    start_block: int
    parent_inode: int
    i_count: int
    offset: int
    xattr: int
    @property
    def xattr_id(self) -> int | None:
        return None if self.xattr == 0xffffffff else self.xattr

@dataclass(frozen=True)
class SquashFSExtendedSymlinkInode:
    header: SquashFSInodeHeader
    nlink: int
    symlink_size: int
    xattr: int
    @property
    def xattr_id(self) -> int | None:
        return None if self.xattr == 0xffffffff else self.xattr


@dataclass(frozen=True)
class SquashFSDirectoryIndex:
    """One variable-length extended-directory index record."""
    index: int
    start_block: int
    name: bytes
    encoded_size: int


@dataclass(frozen=True)
class SquashFSFragmentEntry:
    """One on-disk SquashFS v4 fragment-table entry."""

    start_block: int
    size: int
    unused: int

    @property
    def stored_size(self) -> int:
        """Return the physical fragment payload size."""
        return self.size & SQUASHFS_DATA_SIZE_MASK

    @property
    def is_uncompressed(self) -> bool:
        """Whether the fragment payload is stored without compression."""
        return bool(self.size & SQUASHFS_DATA_UNCOMPRESSED_BIT)


@dataclass(frozen=True)
class SquashFSRegularFileBlock:
    """One decoded basic regular-file block-list entry."""

    stored_size: int
    is_uncompressed: bool
    logical_size: int
    is_sparse: bool


SquashFSInodeBody = (
    SquashFSBasicDirectoryInode
    | SquashFSBasicRegularInode
    | SquashFSBasicSymlinkInode
    | SquashFSExtendedRegularInode
    | SquashFSExtendedDirectoryInode
    | SquashFSExtendedSymlinkInode
)


@dataclass(frozen=True)
class SquashFSInode:
    """One typed inode together with its metadata location and common header."""

    reference: SquashFSMetadataReference
    header: SquashFSInodeHeader
    body: SquashFSInodeBody

@dataclass(frozen=True)
class SquashFSDirectoryHeader:
    """The fixed on-disk prefix shared by a directory entry group."""

    count: int
    start_block: int
    inode_number: int


@dataclass(frozen=True)
class SquashFSDirectoryEntry:
    """One on-disk directory entry, including its encoded name bytes."""

    offset: int
    inode_number_delta: int
    entry_type: int
    name: bytes
    encoded_size: int


@dataclass(frozen=True)
class SquashFSDirectoryRecord:
    """One resolved record in a single SquashFS directory stream."""

    inode_number: int
    inode_type: int
    name: bytes
    inode_reference: SquashFSMetadataReference


class SquashFSMetadataError(ValueError):
    """Invalid or unreadable SquashFS metadata block."""


class LinuxCapabilityError(ValueError):
    """Invalid raw Linux security.capability value."""


class LinuxCapabilityTypeError(LinuxCapabilityError): pass
class LinuxCapabilitySizeError(LinuxCapabilityError): pass
class LinuxCapabilityRevisionError(LinuxCapabilityError): pass
class LinuxCapabilityFlagsError(LinuxCapabilityError): pass


def _linux_capability_set(raw_mask: int, word_count: int) -> LinuxCapabilitySet:
    numbers = tuple(bit for bit in range(word_count * 32) if raw_mask & (1 << bit))
    return LinuxCapabilitySet(
        raw_mask,
        numbers,
        tuple(LINUX_CAPABILITY_NAMES[bit] for bit in numbers if bit in LINUX_CAPABILITY_NAMES),
        tuple(bit for bit in numbers if bit not in LINUX_CAPABILITY_NAMES),
    )


def decode_linux_file_capabilities(value) -> LinuxFileCapabilities:
    """Decode an opaque Linux security.capability XAttr without host state."""
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise LinuxCapabilityTypeError("Capability value must be bytes-like")
    raw_value = bytes(value)
    if len(raw_value) < 4:
        raise LinuxCapabilitySizeError("Capability value is shorter than magic_etc")
    try:
        magic_etc = struct.unpack_from("<I", raw_value)[0]
    except struct.error as error:
        raise LinuxCapabilitySizeError("Cannot decode capability magic_etc") from error
    revision_raw = magic_etc & VFS_CAP_REVISION_MASK
    try:
        revision = LinuxCapabilityRevision(revision_raw)
    except ValueError as error:
        raise LinuxCapabilityRevisionError(
            f"Unknown capability revision: {revision_raw:#x}"
        ) from error
    expected_size, words = {
        LinuxCapabilityRevision.REVISION_1: (XATTR_CAPS_SZ_1, VFS_CAP_U32_1),
        LinuxCapabilityRevision.REVISION_2: (XATTR_CAPS_SZ_2, VFS_CAP_U32_2),
        LinuxCapabilityRevision.REVISION_3: (XATTR_CAPS_SZ_3, VFS_CAP_U32_2),
    }[revision]
    if len(raw_value) != expected_size:
        raise LinuxCapabilitySizeError(
            f"Capability revision {revision.name} requires {expected_size} bytes"
        )
    flags = magic_etc & VFS_CAP_FLAGS_MASK
    if flags & ~VFS_CAP_FLAGS_EFFECTIVE:
        raise LinuxCapabilityFlagsError(f"Unknown capability flags: {flags:#x}")
    try:
        values = struct.unpack("<" + "I" * (len(raw_value) // 4), raw_value)
    except struct.error as error:
        raise LinuxCapabilitySizeError("Cannot decode capability value") from error
    permitted = values[1] | ((values[3] << 32) if words == 2 else 0)
    inheritable = values[2] | ((values[4] << 32) if words == 2 else 0)
    return LinuxFileCapabilities(
        revision, bool(flags & VFS_CAP_FLAGS_EFFECTIVE),
        _linux_capability_set(permitted, words), _linux_capability_set(inheritable, words),
        values[5] if revision is LinuxCapabilityRevision.REVISION_3 else None,
        magic_etc, flags, raw_value,
    )


XATTR_SEMANTIC_DECODERS = MappingProxyType({
    b"security.capability": XAttrSemanticDecoder(
        "linux.security.capability",
        XAttrSemanticKind.LINUX_FILE_CAPABILITIES,
        decode_linux_file_capabilities,
    ),
})


def decode_xattr_semantic(entry: SquashFSXAttrEntry, raw_value) -> DecodedXAttr:
    """Dispatch one already-resolved XAttr value without image or host access."""
    if not isinstance(entry, SquashFSXAttrEntry):
        raise XAttrSemanticTypeError("Xattr semantic entry has an invalid type")
    if not isinstance(raw_value, (bytes, bytearray, memoryview)):
        raise XAttrSemanticTypeError("Xattr semantic raw value must be bytes-like")
    if not isinstance(entry.full_name, (bytes, type(None))):
        raise XAttrSemanticTypeError("Xattr semantic full name must be bytes or None")
    raw_value = bytes(raw_value)
    descriptor = XATTR_SEMANTIC_DECODERS.get(entry.full_name)
    if descriptor is None:
        unknown = UnknownXAttrSemanticValue(entry.full_name, raw_value)
        return DecodedXAttr(
            entry, raw_value, XAttrSemanticKind.UNKNOWN, None, False, unknown
        )
    try:
        semantic_value = descriptor.decode(raw_value)
    except LinuxCapabilityError as error:
        raise XAttrSemanticDecoderError(
            f"Cannot decode semantic xattr {descriptor.decoder_id}"
        ) from error
    return DecodedXAttr(
        entry, raw_value, descriptor.kind, descriptor.decoder_id, True, semantic_value
    )


def read_and_decode_xattr(
    image: SquashFSImage,
    entry: SquashFSXAttrEntry,
    table: SquashFSXAttrIDTable | None = None,
) -> DecodedXAttr:
    """Lazily acquire one XAttr value, then dispatch its semantic decoder."""
    if not isinstance(image, SquashFSImage):
        raise XAttrSemanticTypeError("Xattr semantic image has an invalid type")
    if not isinstance(entry, SquashFSXAttrEntry):
        raise XAttrSemanticTypeError("Xattr semantic entry has an invalid type")
    if table is not None and not isinstance(table, SquashFSXAttrIDTable):
        raise XAttrSemanticTypeError("Xattr semantic table has an invalid type")
    if entry.out_of_line:
        if entry.value is not None:
            raise XAttrSemanticValueResolutionError(
                "Out-of-line xattr entry has an inline value"
            )
        if entry.out_of_line_reference is None:
            raise XAttrSemanticValueResolutionError(
                "Out-of-line xattr entry is missing its reference"
            )
        try:
            raw_value = read_xattr_out_of_line_value(image, entry, table)
        except SquashFSXAttrValueError as error:
            raise XAttrSemanticValueResolutionError(
                "Cannot resolve out-of-line xattr value"
            ) from error
    else:
        if not isinstance(entry.value, bytes):
            raise XAttrSemanticValueResolutionError(
                "Inline xattr entry is missing a bytes value"
            )
        if entry.out_of_line_reference is not None:
            raise XAttrSemanticValueResolutionError(
                "Inline xattr entry has an out-of-line reference"
            )
        raw_value = entry.value
    return decode_xattr_semantic(entry, raw_value)


class SquashFSMetadataStreamError(ValueError):
    """A requested range cannot be read from a SquashFS metadata stream."""


class SquashFSInodeError(ValueError):
    """Invalid or incomplete common SquashFS inode header."""


class SquashFSInodeLookupError(ValueError):
    """The SquashFS inode lookup/export infrastructure is invalid."""


class SquashFSInodeLookupTableError(SquashFSInodeLookupError):
    """The lookup table index is malformed or unavailable."""


class SquashFSInodeLookupIndexError(SquashFSInodeLookupError):
    """An inode number is outside the lookup-table range."""


class SquashFSInodeLookupEntryError(SquashFSInodeLookupError):
    """A logical lookup entry cannot be read or decoded."""


class SquashFSXAttrError(ValueError):
    """Invalid SquashFS xattr ID-table data."""


class SquashFSXAttrTableError(SquashFSXAttrError):
    """The xattr ID table header or index is invalid."""


class SquashFSXAttrIDError(SquashFSXAttrError):
    """An xattr ID is outside range or cannot be read."""


class SquashFSXAttrListError(SquashFSXAttrError):
    """An xattr entry list does not match its ID record."""


class SquashFSXAttrEntryError(SquashFSXAttrListError):
    """An xattr entry header or name cannot be read."""


class SquashFSXAttrValueError(SquashFSXAttrListError):
    """An xattr inline value or OOL reference cannot be read."""


class SquashFSXAttrInodeError(SquashFSXAttrError):
    """An inode's xattr ID cannot be resolved to an xattr list."""


class SquashFSUnsupportedInodeTypeError(SquashFSInodeError):
    """A valid SquashFS inode type has no Stage 9 typed parser."""


class SquashFSRegularFileError(ValueError):
    """A basic regular file cannot be decoded safely."""


class SquashFSMalformedBlockListError(SquashFSRegularFileError):
    """A regular-file block-list entry is not a valid SquashFS size."""


class SquashFSFragmentTailError(SquashFSRegularFileError):
    """A basic regular-file fragment tail is invalid or unavailable."""

class SquashFSDataBlockTruncatedError(SquashFSRegularFileError):
    """A regular-file data block exceeds the physical image."""


class SquashFSDataBlockDecompressionError(SquashFSRegularFileError):
    """A compressed regular-file data block cannot be decompressed."""


class SquashFSDataBlockSizeError(SquashFSRegularFileError):
    """A regular-file data block has an unexpected logical size."""


class SquashFSSymlinkError(Exception):
    """A basic symbolic-link inode or target cannot be read safely."""


class SquashFSFragmentError(Exception):
    """A SquashFS fragment table or data block cannot be read safely."""


class SquashFSFragmentIndexError(SquashFSFragmentError):
    """A fragment-table index or index pointer is invalid."""


class SquashFSFragmentEntryError(SquashFSFragmentError):
    """A fragment-table entry is malformed or unavailable."""


class SquashFSFragmentBlockError(SquashFSFragmentError):
    """A fragment data block is malformed, truncated, or cannot be decoded."""


def _decompress_zstd_payload(payload: bytes, expected_size: int) -> bytes:
    """Decompress a Zstandard payload to its expected logical size."""
    return zstandard.ZstdDecompressor().decompress(
        payload,
        max_output_size=expected_size,
    )


class SquashFSDirectoryError(ValueError):
    """Invalid or incomplete SquashFS directory structure."""


class SquashFSDirectoryReaderError(ValueError):
    """A directory inode cannot be read as a complete directory stream."""


class SquashFSDirectoryIndexError(SquashFSDirectoryError):
    """An extended-directory index record is malformed or incomplete."""


class SquashFSFilesystemGraphError(ValueError):
    """A filesystem object-graph model or operation is invalid."""


class SquashFSRootError(SquashFSFilesystemGraphError):
    """The SquashFS root cannot be opened as a supported directory."""


class SquashFSGraphReadError(SquashFSFilesystemGraphError):
    """A graph operation cannot read its required low-level object."""


class SquashFSNodeTypeError(SquashFSFilesystemGraphError):
    """A graph node's declared type disagrees with its typed inode."""

class SquashFSDirectoryReadError(SquashFSGraphReadError): pass
class SquashFSChildInodeError(SquashFSGraphReadError): pass
class SquashFSDirectoryEntryError(SquashFSFilesystemGraphError): pass
class SquashFSPathError(SquashFSFilesystemGraphError): pass
class SquashFSPathNotFoundError(SquashFSPathError): pass
class SquashFSNotDirectoryError(SquashFSPathError): pass
class SquashFSDuplicateNameError(SquashFSPathError): pass
class SquashFSDirectoryCycleError(SquashFSFilesystemGraphError): pass
class SquashFSFilesystemIndexError(SquashFSFilesystemGraphError): pass
class SquashFSNodeContentError(SquashFSGraphReadError): pass


class SquashFSNodeType(Enum):
    DIRECTORY = "directory"
    REGULAR_FILE = "regular_file"
    SYMLINK = "symlink"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class SquashFSInodeIdentity:
    reference: SquashFSMetadataReference
    inode_number: int

    def __post_init__(self) -> None:
        if not isinstance(self.reference, SquashFSMetadataReference):
            raise SquashFSFilesystemGraphError("Inode identity reference is invalid")
        if not isinstance(self.inode_number, int) or isinstance(self.inode_number, bool) or self.inode_number < 0:
            raise SquashFSFilesystemGraphError("Inode identity number must be non-negative")


@dataclass(frozen=True)
class SquashFSFilesystem:
    image: SquashFSImage
    superblock: SquashFSSuperBlock
    inode_stream: SquashFSMetadataStream
    root_inode: SquashFSInode
    root_identity: SquashFSInodeIdentity

    def __post_init__(self) -> None:
        if not isinstance(self.image, SquashFSImage) or not isinstance(self.superblock, SquashFSSuperBlock):
            raise SquashFSFilesystemGraphError("Filesystem image or superblock is invalid")
        if not isinstance(self.inode_stream, SquashFSMetadataStream) or self.inode_stream.image is not self.image:
            raise SquashFSFilesystemGraphError("Filesystem inode stream is invalid")
        if not isinstance(self.root_inode, SquashFSInode) or not isinstance(self.root_identity, SquashFSInodeIdentity):
            raise SquashFSFilesystemGraphError("Filesystem root is invalid")
        if (self.root_identity.reference, self.root_identity.inode_number) != (self.root_inode.reference, self.root_inode.header.inode_number):
            raise SquashFSFilesystemGraphError("Filesystem root identity does not match inode")


@dataclass(frozen=True)
class SquashFSPathNode:
    filesystem: SquashFSFilesystem
    identity: SquashFSInodeIdentity
    inode: SquashFSInode
    raw_name: bytes | None
    parent_path: bytes | None
    absolute_path: bytes
    node_type: SquashFSNodeType

    def __post_init__(self) -> None:
        if not isinstance(self.filesystem, SquashFSFilesystem) or not isinstance(self.identity, SquashFSInodeIdentity) or not isinstance(self.inode, SquashFSInode):
            raise SquashFSFilesystemGraphError("Path node has invalid filesystem, identity, or inode")
        if (self.identity.reference, self.identity.inode_number) != (self.inode.reference, self.inode.header.inode_number):
            raise SquashFSFilesystemGraphError("Path node identity does not match inode")
        if not isinstance(self.absolute_path, bytes) or not self.absolute_path.startswith(b"/"):
            raise SquashFSFilesystemGraphError("Path node absolute path must be absolute bytes")
        root = self.raw_name is None
        if root:
            if self.parent_path is not None or self.absolute_path != b"/":
                raise SquashFSFilesystemGraphError("Root node path fields are invalid")
        else:
            if not isinstance(self.raw_name, bytes) or not self.raw_name:
                raise SquashFSFilesystemGraphError("Non-root node name must be non-empty bytes")
            if not isinstance(self.parent_path, bytes) or not self.parent_path.startswith(b"/"):
                raise SquashFSFilesystemGraphError("Non-root node parent path must be absolute bytes")


@dataclass(frozen=True)
class SquashFSDirectoryNode(SquashFSPathNode):
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.node_type is not SquashFSNodeType.DIRECTORY or not isinstance(self.inode.body, (SquashFSBasicDirectoryInode, SquashFSExtendedDirectoryInode)):
            raise SquashFSNodeTypeError("Directory node does not wrap a directory inode")


@dataclass(frozen=True)
class SquashFSRegularFileNode(SquashFSPathNode):
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.node_type is not SquashFSNodeType.REGULAR_FILE or not isinstance(self.inode.body, (SquashFSBasicRegularInode, SquashFSExtendedRegularInode)):
            raise SquashFSNodeTypeError("Regular-file node does not wrap a regular inode")


@dataclass(frozen=True)
class SquashFSSymlinkNode(SquashFSPathNode):
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.node_type is not SquashFSNodeType.SYMLINK or not isinstance(self.inode.body, (SquashFSBasicSymlinkInode, SquashFSExtendedSymlinkInode)):
            raise SquashFSNodeTypeError("Symlink node does not wrap a symlink inode")


@dataclass(frozen=True)
class SquashFSUnsupportedNode(SquashFSPathNode):
    def __post_init__(self) -> None:
        super().__post_init__()
        if self.node_type is not SquashFSNodeType.UNSUPPORTED or isinstance(self.inode.body, (SquashFSBasicDirectoryInode, SquashFSExtendedDirectoryInode, SquashFSBasicRegularInode, SquashFSExtendedRegularInode, SquashFSBasicSymlinkInode, SquashFSExtendedSymlinkInode)):
            raise SquashFSNodeTypeError("Unsupported node wraps a supported inode")

@dataclass(frozen=True)
class SquashFSDirectoryListing:
    directory_path: bytes
    children: tuple[SquashFSPathNode, ...]
    def __post_init__(self) -> None:
        if not isinstance(self.directory_path, bytes) or not self.directory_path.startswith(b'/'):
            raise SquashFSFilesystemGraphError("Directory listing path must be absolute bytes")
        if not isinstance(self.children, tuple) or any(not isinstance(x, SquashFSPathNode) or x.parent_path != self.directory_path for x in self.children):
            raise SquashFSFilesystemGraphError("Directory listing children are invalid")


@dataclass(frozen=True)
class SquashFSFilesystemIndex:
    """Immutable, traversal-ordered view of one filesystem graph."""
    root: SquashFSDirectoryNode
    nodes: tuple[SquashFSPathNode, ...]
    paths: object
    inode_paths: object

    def __post_init__(self) -> None:
        if not isinstance(self.root, SquashFSDirectoryNode) or not isinstance(self.nodes, tuple):
            raise SquashFSFilesystemIndexError("Filesystem index model is invalid")
        if not isinstance(self.paths, MappingProxyType) or not isinstance(self.inode_paths, MappingProxyType):
            raise SquashFSFilesystemIndexError("Filesystem index mappings must be immutable")
        if not self.nodes or self.nodes[0] != self.root or self.root.absolute_path != b"/":
            raise SquashFSFilesystemIndexError("Filesystem index root is invalid")
        if any(not isinstance(node, SquashFSPathNode) or not isinstance(node.absolute_path, bytes) or not node.absolute_path.startswith(b"/") for node in self.nodes):
            raise SquashFSFilesystemIndexError("Filesystem index nodes are invalid")
        node_paths = tuple(node.absolute_path for node in self.nodes)
        if len(node_paths) != len(set(node_paths)):
            raise SquashFSFilesystemIndexError("Filesystem index contains duplicate paths")
        if set(self.paths) != set(node_paths) or any(self.paths[path] is not node for path, node in ((node.absolute_path, node) for node in self.nodes)):
            raise SquashFSFilesystemIndexError("Filesystem index path mapping is inconsistent")
        expected: dict[SquashFSInodeIdentity, tuple[bytes, ...]] = {}
        for node in self.nodes:
            expected[node.identity] = expected.get(node.identity, ()) + (node.absolute_path,)
        if set(self.inode_paths) != set(expected) or any(not isinstance(identity, SquashFSInodeIdentity) or paths != expected.get(identity) or not isinstance(paths, tuple) for identity, paths in self.inode_paths.items()):
            raise SquashFSFilesystemIndexError("Filesystem index inode mapping is inconsistent")


def decode_metadata_reference(reference: int) -> SquashFSMetadataReference:
    """Decode a 64-bit SquashFS inode metadata reference without I/O."""
    if not isinstance(reference, int) or isinstance(reference, bool):
        raise TypeError("Metadata reference must be an integer")

    if reference < 0 or reference > 0xFFFFFFFFFFFFFFFF:
        raise ValueError("Metadata reference is outside the unsigned 64-bit range")

    return SquashFSMetadataReference(
        block_offset=reference >> 16,
        byte_offset=reference & 0xFFFF,
    )


def _inode_lookup_block_count(inode_count: int) -> int:
    if not isinstance(inode_count, int) or isinstance(inode_count, bool) or inode_count <= 0:
        raise SquashFSInodeLookupTableError("Lookup table inode count must be positive")
    return (inode_count * INODE_LOOKUP_ENTRY_SIZE + METADATA_SIZE - 1) // METADATA_SIZE


def read_inode_lookup_table(image: SquashFSImage, next_table: int | None = None) -> SquashFSInodeLookupTable | None:
    """Read and validate the uncompressed index for the inode lookup table."""
    if not isinstance(image, SquashFSImage):
        raise TypeError("Lookup table image has an invalid type")
    superblock = image.superblock or image.read_superblock()
    start = superblock.lookup_table_start
    if start == SQUASHFS_INVALID_BLK:
        return None
    count = _inode_lookup_block_count(superblock.inode_count)
    index_size = count * INODE_LOOKUP_ENTRY_SIZE
    next_table = start + index_size if next_table is None else next_table
    image_size = image.image.stat().st_size
    if start < 0 or start > next_table or next_table - start != index_size or next_table > image_size:
        raise SquashFSInodeLookupTableError("Lookup table index bounds are invalid")
    with image.image.open("rb") as source:
        source.seek(start); data = source.read(index_size)
    if len(data) != index_size:
        raise SquashFSInodeLookupTableError("Lookup table index is truncated")
    offsets = tuple(INODE_LOOKUP_ENTRY_STRUCT.unpack_from(data, pos)[0] for pos in range(0, index_size, 8))
    previous = -1
    for offset in offsets:
        if offset >= image_size or offset <= previous or offset >= start or (previous >= 0 and offset - previous > METADATA_SIZE + METADATA_HEADER_SIZE):
            raise SquashFSInodeLookupTableError("Lookup metadata block offsets are invalid")
        previous = offset
    if start - previous > METADATA_SIZE + METADATA_HEADER_SIZE:
        raise SquashFSInodeLookupTableError("Final lookup metadata block distance is invalid")
    return SquashFSInodeLookupTable(start, superblock.inode_count, offsets, next_table)


def read_inode_lookup_entry(image: SquashFSImage, table: SquashFSInodeLookupTable | None, inode_number: int) -> SquashFSInodeReference:
    if table is None:
        raise SquashFSInodeLookupTableError("Inode lookup table is unavailable")
    if not isinstance(inode_number, int) or isinstance(inode_number, bool) or not 1 <= inode_number <= table.inode_count:
        raise SquashFSInodeLookupIndexError("Inode number is outside lookup table range")
    logical = inode_number - 1; byte_offset = logical * 8
    block_index, block_offset = divmod(byte_offset, METADATA_SIZE)
    try:
        data = SquashFSMetadataStream(image, table.metadata_block_offsets[block_index]).read(SquashFSMetadataReference(0, block_offset), 8)
        raw = INODE_LOOKUP_ENTRY_STRUCT.unpack(data)[0]
    except (SquashFSMetadataError, SquashFSMetadataStreamError, struct.error) as error:
        raise SquashFSInodeLookupEntryError("Cannot read inode lookup entry") from error
    return SquashFSInodeReference(raw, raw >> 16, raw & 0xffff)


def resolve_inode_number(image: SquashFSImage, inode_stream: SquashFSMetadataStream, table: SquashFSInodeLookupTable | None, inode_number: int) -> SquashFSInode:
    reference = read_inode_lookup_entry(image, table, inode_number)
    try:
        return read_inode(inode_stream, SquashFSMetadataReference(reference.block, reference.offset))
    except (SquashFSInodeError, SquashFSMetadataStreamError) as error:
        raise SquashFSInodeLookupEntryError("Lookup inode reference cannot be resolved") from error


def decode_xattr_reference(value: int) -> SquashFSXAttrReference:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 0xffffffffffffffff:
        raise TypeError("Xattr reference must be an unsigned 64-bit integer")
    return SquashFSXAttrReference(value >> 16, value & 0xffff)


def _xattr_index_count(xattr_ids: int) -> int:
    if not isinstance(xattr_ids, int) or isinstance(xattr_ids, bool) or xattr_ids <= 0:
        raise SquashFSXAttrTableError("Xattr ID count must be positive")
    # On-disk count is u32, nevertheless retain an explicit checked bound.
    if xattr_ids > 0xffffffff or xattr_ids > ((1 << 63) - 1) // XATTR_ID_SIZE:
        raise SquashFSXAttrTableError("Xattr ID count is unsafe")
    return (xattr_ids * XATTR_ID_SIZE + METADATA_SIZE - 1) // METADATA_SIZE


def read_xattr_id_table(image: SquashFSImage) -> SquashFSXAttrIDTable | None:
    """Read the xattr-ID header and its uncompressed metadata-block index."""
    if not isinstance(image, SquashFSImage):
        raise TypeError("Xattr table image has an invalid type")
    superblock = image.superblock or image.read_superblock()
    table_start = superblock.xattr_id_table_start
    if table_start == SQUASHFS_INVALID_BLK:
        return None
    image_size = image.image.stat().st_size
    filesystem_end = superblock.bytes_used
    if filesystem_end > image_size or table_start < 0 or table_start + XATTR_ID_TABLE_STRUCT.size > filesystem_end:
        raise SquashFSXAttrTableError("Xattr ID table header bounds are invalid")
    with image.image.open("rb") as source:
        source.seek(table_start)
        header = source.read(XATTR_ID_TABLE_STRUCT.size)
    if len(header) != XATTR_ID_TABLE_STRUCT.size:
        raise SquashFSXAttrTableError("Xattr ID table header is truncated")
    xattr_table_start, xattr_ids, unused = XATTR_ID_TABLE_STRUCT.unpack(header)
    count = _xattr_index_count(xattr_ids)
    index_start = table_start + XATTR_ID_TABLE_STRUCT.size
    index_size = count * 8
    if index_start + index_size != filesystem_end:
        raise SquashFSXAttrTableError("Xattr ID index size does not match filesystem end")
    with image.image.open("rb") as source:
        source.seek(index_start); data = source.read(index_size)
    if len(data) != index_size:
        raise SquashFSXAttrTableError("Xattr ID index is truncated")
    offsets = tuple(INODE_LOOKUP_ENTRY_STRUCT.unpack_from(data, p)[0] for p in range(0, index_size, 8))
    previous = -1
    for offset in offsets:
        if offset >= filesystem_end or offset <= previous or offset >= table_start or (previous >= 0 and offset - previous > METADATA_SIZE + METADATA_HEADER_SIZE):
            raise SquashFSXAttrTableError("Xattr ID metadata offsets are invalid")
        previous = offset
    if table_start - previous > METADATA_SIZE + METADATA_HEADER_SIZE or xattr_table_start >= offsets[0]:
        raise SquashFSXAttrTableError("Xattr ID table layout is invalid")
    return SquashFSXAttrIDTable(table_start, xattr_table_start, xattr_ids, offsets, unused)


def read_xattr_id(image: SquashFSImage, index: int, table: SquashFSXAttrIDTable | None = None) -> SquashFSXAttrID:
    """Lazily read one zero-based `squashfs_xattr_id` record."""
    if table is None:
        table = read_xattr_id_table(image)
    if table is None:
        raise SquashFSXAttrTableError("Xattr ID table is unavailable")
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < table.xattr_ids:
        raise SquashFSXAttrIDError("Xattr ID index is outside table range")
    byte_offset = index * XATTR_ID_SIZE
    block_index, block_offset = divmod(byte_offset, METADATA_SIZE)
    try:
        data = SquashFSMetadataStream(image, table.metadata_block_offsets[block_index]).read(SquashFSMetadataReference(0, block_offset), XATTR_ID_SIZE)
        encoded, count, size = XATTR_ID_STRUCT.unpack(data)
    except (SquashFSMetadataError, SquashFSMetadataStreamError, struct.error, IndexError) as error:
        raise SquashFSXAttrIDError("Cannot read xattr ID") from error
    return SquashFSXAttrID(index, encoded, count, size, decode_xattr_reference(encoded))


XATTR_ENTRY_STRUCT = struct.Struct("<HH")
XATTR_VALUE_STRUCT = struct.Struct("<I")
XATTR_VALUE_OOL_STRUCT = struct.Struct("<I")
XATTR_VALUE_OOL = 0x100
XATTR_PREFIX_MASK = 0xff
XATTR_PREFIXES = {0: b"user.", 1: b"trusted.", 2: b"security."}


def decode_xattr_namespace(raw_type: int) -> SquashFSXAttrNamespace:
    if not isinstance(raw_type, int) or isinstance(raw_type, bool) or not 0 <= raw_type <= 0xffff:
        raise TypeError("Xattr type must be an unsigned 16-bit integer")
    namespace = raw_type & XATTR_PREFIX_MASK
    prefix = XATTR_PREFIXES.get(namespace)
    return SquashFSXAttrNamespace(namespace, prefix, prefix is not None and not (raw_type & ~(XATTR_PREFIX_MASK | XATTR_VALUE_OOL)))


def read_xattr_list(image: SquashFSImage, xattr_id: SquashFSXAttrID, table: SquashFSXAttrIDTable | None = None) -> SquashFSXAttrList:
    if not isinstance(image, SquashFSImage) or not isinstance(xattr_id, SquashFSXAttrID):
        raise TypeError("Xattr list arguments have invalid types")
    table = read_xattr_id_table(image) if table is None else table
    if table is None:
        raise SquashFSXAttrTableError("Xattr ID table is unavailable")
    if not 0 <= xattr_id.index < table.xattr_ids:
        raise SquashFSXAttrIDError("Xattr ID index is outside table range")
    stream = SquashFSMetadataStream(
        image, table.xattr_table_start + xattr_id.reference.block
    )
    reference = SquashFSMetadataReference(0, xattr_id.reference.offset)
    consumed = 0
    entries: list[SquashFSXAttrEntry] = []

    def read_field(size: int) -> bytes:
        nonlocal consumed, reference
        data = stream.read(reference, size)
        reference = stream.advance_reference(reference, size)
        consumed += size
        return data

    for entry_index in range(xattr_id.count):
        try:
            raw_type, name_size = XATTR_ENTRY_STRUCT.unpack(
                read_field(XATTR_ENTRY_STRUCT.size)
            )
            name = read_field(name_size)
        except (SquashFSMetadataError, SquashFSMetadataStreamError, struct.error) as error:
            raise SquashFSXAttrEntryError(
                f"Cannot read xattr entry {entry_index}"
            ) from error

        try:
            value_size = XATTR_VALUE_STRUCT.unpack(
                read_field(XATTR_VALUE_STRUCT.size)
            )[0]
            namespace = decode_xattr_namespace(raw_type)
            out_of_line = bool(raw_type & XATTR_VALUE_OOL)
            if out_of_line:
                if value_size != 8:
                    raise SquashFSXAttrValueError(
                        "Out-of-line xattr value representation must be 8 bytes"
                    )
                out_of_line_reference = struct.unpack("<Q", read_field(8))[0]
                value = None
            else:
                value = read_field(value_size)
                out_of_line_reference = None
            entries.append(
                SquashFSXAttrEntry(
                    raw_type,
                    namespace,
                    name,
                    None if namespace.prefix is None else namespace.prefix + name,
                    value,
                    value_size,
                    out_of_line,
                    out_of_line_reference,
                )
            )
        except SquashFSXAttrValueError:
            raise
        except (SquashFSMetadataError, SquashFSMetadataStreamError, struct.error) as error:
            raise SquashFSXAttrValueError(
                f"Cannot read xattr value for entry {entry_index}"
            ) from error
    padding_size = xattr_id.size - consumed
    if padding_size < 0 or padding_size > 3 or (padding_size and xattr_id.size % 4):
        raise SquashFSXAttrListError("Xattr list size does not match ID record")
    if padding_size:
        try:
            padding = stream.read(reference, padding_size)
        except (SquashFSMetadataError, SquashFSMetadataStreamError) as error:
            raise SquashFSXAttrListError(
                "Cannot read xattr list alignment padding"
            ) from error
        if padding != b"\0" * padding_size:
            raise SquashFSXAttrListError("Xattr list size does not match ID record")
    return SquashFSXAttrList(xattr_id, tuple(entries), consumed)


def _validate_xattr_ool_metadata_range(
    stream: SquashFSMetadataStream,
    reference: SquashFSMetadataReference,
    size: int,
    region_end: int,
    truncated_message: str,
) -> None:
    """Prove a metadata range stays in the XAttr-value region before reading it."""
    if reference.byte_offset > METADATA_SIZE:
        raise SquashFSXAttrValueError("Invalid out-of-line xattr reference offset")
    if size == 0:
        return

    current_offset = stream.table_start + reference.block_offset
    current_byte_offset = reference.byte_offset
    remaining = size
    while remaining:
        if current_offset < stream.table_start or current_offset >= region_end:
            raise SquashFSXAttrValueError("Invalid out-of-line xattr reference")
        block = stream.image.read_metadata_block(current_offset)
        if current_byte_offset > len(block.data):
            raise SquashFSXAttrValueError("Invalid out-of-line xattr reference offset")
        available = len(block.data) - current_byte_offset
        if available == 0:
            if block.next_offset >= region_end:
                raise SquashFSXAttrValueError(truncated_message)
            current_offset = block.next_offset
            current_byte_offset = 0
            continue
        remaining -= min(remaining, available)
        if remaining and block.next_offset >= region_end:
            raise SquashFSXAttrValueError(truncated_message)
        current_offset = block.next_offset
        current_byte_offset = 0


def read_xattr_out_of_line_value(
    image: SquashFSImage,
    entry: SquashFSXAttrEntry,
    table: SquashFSXAttrIDTable | None = None,
) -> bytes:
    """Lazily resolve and return the opaque bytes of one OOL XAttr value."""
    if not isinstance(entry, SquashFSXAttrEntry):
        raise SquashFSXAttrValueError("Out-of-line xattr entry has an invalid type")
    if not entry.out_of_line:
        raise SquashFSXAttrValueError("Xattr entry is not out-of-line")
    if entry.value is not None:
        raise SquashFSXAttrValueError("Out-of-line xattr entry has an inline value")
    if entry.out_of_line_reference is None:
        raise SquashFSXAttrValueError("Out-of-line xattr entry is missing its reference")
    if not isinstance(image, SquashFSImage):
        raise SquashFSXAttrValueError("Out-of-line xattr image has an invalid type")

    try:
        # The decoded entry is self-contained, but the table supplies the XAttr
        # metadata-table origin and the boundary before the ID metadata region.
        table = read_xattr_id_table(image) if table is None else table
        if not isinstance(table, SquashFSXAttrIDTable):
            raise SquashFSXAttrValueError("Xattr ID table is unavailable")
        if not table.metadata_block_offsets:
            raise SquashFSXAttrValueError("Xattr ID table has no metadata boundary")
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in (
            table.xattr_table_start, table.table_start, table.metadata_block_offsets[0]
        )):
            raise SquashFSXAttrValueError("Xattr ID table has invalid metadata bounds")
        superblock = image.superblock or image.read_superblock()
        image_size = image.image.stat().st_size
        region_end = table.metadata_block_offsets[0]
        if (
            superblock.bytes_used > image_size
            or table.xattr_table_start < 0
            or region_end <= table.xattr_table_start
            or region_end > table.table_start
            or table.table_start > superblock.bytes_used
        ):
            raise SquashFSXAttrValueError("Xattr ID table has invalid metadata bounds")

        try:
            reference = decode_xattr_reference(entry.out_of_line_reference)
        except (TypeError, ValueError, OverflowError) as error:
            raise SquashFSXAttrValueError("Invalid out-of-line xattr reference") from error
        target_start = table.xattr_table_start + reference.block
        if target_start < table.xattr_table_start or target_start >= region_end:
            raise SquashFSXAttrValueError("Invalid out-of-line xattr reference")
        if reference.offset >= METADATA_SIZE:
            raise SquashFSXAttrValueError("Invalid out-of-line xattr reference offset")
        stream = SquashFSMetadataStream(image, target_start)
        target = SquashFSMetadataReference(0, reference.offset)

        try:
            _validate_xattr_ool_metadata_range(
                stream, target, XATTR_VALUE_OOL_STRUCT.size, region_end,
                "Truncated out-of-line xattr target header",
            )
            header = stream.read(target, XATTR_VALUE_OOL_STRUCT.size)
            value_size = XATTR_VALUE_OOL_STRUCT.unpack(header)[0]
            value_reference = stream.advance_reference(target, XATTR_VALUE_OOL_STRUCT.size)
        except SquashFSXAttrValueError:
            raise
        except (SquashFSMetadataError, SquashFSMetadataStreamError, struct.error,
                IndexError, OverflowError, OSError, TypeError, ValueError) as error:
            raise SquashFSXAttrValueError(
                "Truncated out-of-line xattr target header"
            ) from error

        # Preflight first: a u32 value is format-valid, but must fit in the
        # physically bounded XAttr metadata region before it is assembled.
        try:
            _validate_xattr_ool_metadata_range(
                stream, value_reference, value_size, region_end,
                "Impossible declared out-of-line xattr value size",
            )
            return stream.read(value_reference, value_size)
        except SquashFSXAttrValueError:
            raise
        except (SquashFSMetadataError, SquashFSMetadataStreamError, struct.error,
                IndexError, OverflowError, OSError, TypeError, ValueError) as error:
            raise SquashFSXAttrValueError(
                "Truncated out-of-line xattr target value"
            ) from error
    except SquashFSXAttrValueError:
        raise
    except (SquashFSXAttrError, SquashFSMetadataError, SquashFSMetadataStreamError,
            struct.error, AttributeError, IndexError, OverflowError, OSError, TypeError, ValueError) as error:
        raise SquashFSXAttrValueError(
            "Invalid or truncated out-of-line xattr value"
        ) from error


def read_inode_xattrs(image: SquashFSImage, inode: SquashFSInode, table: SquashFSXAttrIDTable | None = None) -> SquashFSXAttrList | None:
    if not isinstance(inode, SquashFSInode):
        raise TypeError("Xattr inode has an invalid type")
    xattr_id = getattr(inode.body, "xattr_id", None)
    if xattr_id is None:
        return None
    try:
        return read_xattr_list(image, read_xattr_id(image, xattr_id, table), table)
    except SquashFSXAttrError as error:
        raise SquashFSXAttrInodeError(
            f"Cannot read xattrs for inode ID {xattr_id}"
        ) from error


def parse_inode_header(data: bytes) -> SquashFSInodeHeader:
    """Decode the fixed common inode header without reading an image."""
    if not isinstance(data, bytes):
        raise TypeError("Inode header data must be bytes")

    if len(data) < INODE_HEADER_SIZE:
        raise SquashFSInodeError(
            f"Inode header is shorter than {INODE_HEADER_SIZE} bytes"
        )

    try:
        fields = INODE_HEADER_STRUCT.unpack_from(data)
    except struct.error as error:
        raise SquashFSInodeError("Cannot unpack inode header") from error

    return SquashFSInodeHeader(*fields)


def parse_basic_directory_inode(data: bytes) -> SquashFSBasicDirectoryInode:
    """Decode only a basic directory inode from its on-disk bytes."""
    if not isinstance(data, bytes):
        raise TypeError("Basic directory inode data must be bytes")

    if len(data) < BASIC_DIRECTORY_INODE_SIZE:
        raise SquashFSInodeError(
            "Basic directory inode is shorter than "
            f"{BASIC_DIRECTORY_INODE_SIZE} bytes: got {len(data)}"
        )

    header = parse_inode_header(data)
    if header.inode_type != BASIC_DIRECTORY_INODE_TYPE:
        raise SquashFSInodeError(
            "Basic directory inode type mismatch: "
            f"expected {BASIC_DIRECTORY_INODE_TYPE}, got {header.inode_type}"
        )

    return parse_basic_directory_inode_body(header, data[INODE_HEADER_SIZE:])


def parse_basic_directory_inode_body(
    header: SquashFSInodeHeader,
    data: bytes,
) -> SquashFSBasicDirectoryInode:
    """Decode the basic-directory body immediately following ``header``."""
    if not isinstance(header, SquashFSInodeHeader):
        raise TypeError("Basic directory inode header has an invalid type")

    if not isinstance(data, bytes):
        raise TypeError("Basic directory inode body data must be bytes")

    if len(data) < BASIC_DIRECTORY_INODE_BODY_SIZE:
        raise SquashFSInodeError(
            "Basic directory inode body is shorter than "
            f"{BASIC_DIRECTORY_INODE_BODY_SIZE} bytes: got {len(data)}"
        )

    if header.inode_type != BASIC_DIRECTORY_INODE_TYPE:
        raise SquashFSInodeError(
            "Basic directory inode type mismatch: "
            f"expected {BASIC_DIRECTORY_INODE_TYPE}, got {header.inode_type}"
        )

    try:
        body = BASIC_DIRECTORY_INODE_BODY_STRUCT.unpack_from(data)
    except struct.error as error:
        raise SquashFSInodeError("Cannot unpack basic directory inode body") from error

    return SquashFSBasicDirectoryInode(header, *body)


def parse_basic_regular_inode_body(
    header: SquashFSInodeHeader,
    data: bytes,
) -> SquashFSBasicRegularInode:
    """Decode the basic regular-file body immediately following ``header``."""
    if not isinstance(header, SquashFSInodeHeader):
        raise TypeError("Basic regular inode header has an invalid type")

    if not isinstance(data, bytes):
        raise TypeError("Basic regular inode body data must be bytes")

    if len(data) < BASIC_REGULAR_INODE_BODY_SIZE:
        raise SquashFSInodeError(
            "Basic regular inode body is shorter than "
            f"{BASIC_REGULAR_INODE_BODY_SIZE} bytes: got {len(data)}"
        )

    if header.inode_type != BASIC_REGULAR_INODE_TYPE:
        raise SquashFSInodeError(
            "Basic regular inode type mismatch: "
            f"expected {BASIC_REGULAR_INODE_TYPE}, got {header.inode_type}"
        )

    try:
        body = BASIC_REGULAR_INODE_BODY_STRUCT.unpack_from(data)
    except struct.error as error:
        raise SquashFSInodeError("Cannot unpack basic regular inode body") from error

    return SquashFSBasicRegularInode(header, *body)


def parse_basic_symlink_inode(data: bytes) -> SquashFSBasicSymlinkInode:
    """Decode only a basic symbolic-link inode from its on-disk bytes."""
    if not isinstance(data, bytes):
        raise TypeError("Basic symlink inode data must be bytes")

    if len(data) < BASIC_SYMLINK_INODE_SIZE:
        raise SquashFSInodeError(
            "Basic symlink inode is shorter than "
            f"{BASIC_SYMLINK_INODE_SIZE} bytes: got {len(data)}"
        )

    header = parse_inode_header(data)
    return parse_basic_symlink_inode_body(header, data[INODE_HEADER_SIZE:])


def parse_basic_symlink_inode_body(
    header: SquashFSInodeHeader,
    data: bytes,
) -> SquashFSBasicSymlinkInode:
    """Decode the basic symlink body immediately following ``header``."""
    if not isinstance(header, SquashFSInodeHeader):
        raise TypeError("Basic symlink inode header has an invalid type")
    if not isinstance(data, bytes):
        raise TypeError("Basic symlink inode body data must be bytes")
    if len(data) < BASIC_SYMLINK_INODE_BODY_SIZE:
        raise SquashFSInodeError(
            "Basic symlink inode body is shorter than "
            f"{BASIC_SYMLINK_INODE_BODY_SIZE} bytes: got {len(data)}"
        )
    if header.inode_type != BASIC_SYMLINK_INODE_TYPE:
        raise SquashFSInodeError(
            "Basic symlink inode type mismatch: "
            f"expected {BASIC_SYMLINK_INODE_TYPE}, got {header.inode_type}"
        )

    try:
        body = BASIC_SYMLINK_INODE_BODY_STRUCT.unpack_from(data)
    except struct.error as error:
        raise SquashFSInodeError("Cannot unpack basic symlink inode body") from error

    return SquashFSBasicSymlinkInode(header, *body)


def parse_extended_regular_inode(data: bytes) -> SquashFSExtendedRegularInode:
    """Decode one complete extended regular-file inode without I/O."""
    if not isinstance(data, bytes):
        raise TypeError("Extended regular inode data must be bytes")
    if len(data) < EXTENDED_REGULAR_INODE_SIZE:
        raise SquashFSInodeError(
            "Extended regular inode is shorter than "
            f"{EXTENDED_REGULAR_INODE_SIZE} bytes: got {len(data)}"
        )
    header = parse_inode_header(data)
    return parse_extended_regular_inode_body(header, data[INODE_HEADER_SIZE:])


def parse_extended_regular_inode_body(
    header: SquashFSInodeHeader,
    data: bytes,
) -> SquashFSExtendedRegularInode:
    """Decode the extended regular-file body immediately following ``header``."""
    if not isinstance(header, SquashFSInodeHeader):
        raise TypeError("Extended regular inode header has an invalid type")
    if not isinstance(data, bytes):
        raise TypeError("Extended regular inode body data must be bytes")
    if len(data) < EXTENDED_REGULAR_INODE_BODY_SIZE:
        raise SquashFSInodeError(
            "Extended regular inode body is shorter than "
            f"{EXTENDED_REGULAR_INODE_BODY_SIZE} bytes: got {len(data)}"
        )
    if header.inode_type != EXTENDED_REGULAR_INODE_TYPE:
        raise SquashFSInodeError("Extended regular inode type mismatch")
    try:
        body = EXTENDED_REGULAR_INODE_BODY_STRUCT.unpack_from(data)
    except struct.error as error:
        raise SquashFSInodeError("Cannot unpack extended regular inode body") from error
    return SquashFSExtendedRegularInode(header, *body)


def parse_extended_directory_inode_body(header: SquashFSInodeHeader, data: bytes) -> SquashFSExtendedDirectoryInode:
    if not isinstance(header, SquashFSInodeHeader):
        raise TypeError("Extended directory inode header has an invalid type")
    if not isinstance(data, bytes):
        raise TypeError("Extended directory inode body data must be bytes")
    if len(data) < EXTENDED_DIRECTORY_INODE_BODY_SIZE:
        raise SquashFSInodeError("Extended directory inode body is truncated")
    if header.inode_type != EXTENDED_DIRECTORY_INODE_TYPE:
        raise SquashFSInodeError("Extended directory inode type mismatch")
    try:
        return SquashFSExtendedDirectoryInode(header, *EXTENDED_DIRECTORY_INODE_BODY_STRUCT.unpack_from(data))
    except struct.error as error:
        raise SquashFSInodeError("Cannot unpack extended directory inode body") from error


def parse_extended_symlink_inode_body(header: SquashFSInodeHeader, data: bytes) -> SquashFSExtendedSymlinkInode:
    if not isinstance(header, SquashFSInodeHeader) or not isinstance(data, bytes):
        raise TypeError("Extended symlink inode has invalid arguments")
    if len(data) < EXTENDED_SYMLINK_INODE_BODY_SIZE:
        raise SquashFSInodeError("Extended symlink inode body is truncated")
    if header.inode_type != EXTENDED_SYMLINK_INODE_TYPE:
        raise SquashFSInodeError("Extended symlink inode type mismatch")
    try:
        return SquashFSExtendedSymlinkInode(header, *EXTENDED_SYMLINK_INODE_BODY_STRUCT.unpack_from(data))
    except struct.error as error:
        raise SquashFSInodeError("Cannot unpack extended symlink inode body") from error


def parse_directory_index(data: bytes) -> SquashFSDirectoryIndex:
    """Decode exactly one extended-directory index record without I/O."""
    if not isinstance(data, bytes):
        raise TypeError("Directory index data must be bytes")
    if len(data) < DIRECTORY_INDEX_SIZE:
        raise SquashFSDirectoryIndexError("Directory index header is truncated")
    try:
        index, start_block, size = DIRECTORY_INDEX_STRUCT.unpack_from(data)
    except struct.error as error:
        raise SquashFSDirectoryIndexError("Cannot unpack directory index header") from error
    name_size = size + 1
    if name_size > DIRECTORY_NAME_MAX:
        raise SquashFSDirectoryIndexError("Directory index name exceeds maximum length")
    encoded_size = DIRECTORY_INDEX_SIZE + name_size
    if len(data) < encoded_size:
        raise SquashFSDirectoryIndexError("Directory index name is truncated")
    return SquashFSDirectoryIndex(index, start_block, data[DIRECTORY_INDEX_SIZE:encoded_size], encoded_size)


def basic_regular_file_block_count(
    file_size: int,
    block_size: int,
    fragment: int,
) -> int:
    """Return the number of block-list entries required by a regular file."""
    for name, value in (("file size", file_size), ("block size", block_size), ("fragment", fragment)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Basic regular inode {name} must be an integer")

    if file_size < 0:
        raise ValueError("Basic regular inode file size must not be negative")
    if block_size <= 0:
        raise ValueError("SquashFS block size must be positive")
    if not 0 <= fragment <= 0xFFFFFFFF:
        raise ValueError("Basic regular inode fragment is outside the unsigned 32-bit range")

    complete_blocks, remainder = divmod(file_size, block_size)
    if fragment == SQUASHFS_INVALID_FRAGMENT and remainder:
        return complete_blocks + 1
    return complete_blocks


def parse_regular_file_block_size_entry(
    data: bytes,
    logical_size: int,
) -> SquashFSRegularFileBlock:
    """Decode one 32-bit basic regular-file block-list entry without I/O."""
    if not isinstance(data, bytes):
        raise TypeError("Regular-file block-list entry must be bytes")
    if not isinstance(logical_size, int) or isinstance(logical_size, bool):
        raise TypeError("Regular-file block logical size must be an integer")
    if logical_size <= 0:
        raise ValueError("Regular-file block logical size must be positive")
    if len(data) < REGULAR_FILE_BLOCK_SIZE_ENTRY_SIZE:
        raise SquashFSMalformedBlockListError(
            "Regular-file block-list entry is shorter than "
            f"{REGULAR_FILE_BLOCK_SIZE_ENTRY_SIZE} bytes"
        )

    try:
        encoded_size = REGULAR_FILE_BLOCK_SIZE_STRUCT.unpack_from(data)[0]
    except struct.error as error:
        raise SquashFSMalformedBlockListError(
            "Cannot unpack regular-file block-list entry"
        ) from error

    if encoded_size & SQUASHFS_DATA_RESERVED_MASK:
        raise SquashFSMalformedBlockListError(
            f"Regular-file block-list entry has reserved bits: {encoded_size:#010x}"
        )

    stored_size = encoded_size & SQUASHFS_DATA_SIZE_MASK
    return SquashFSRegularFileBlock(
        stored_size=stored_size,
        is_uncompressed=bool(encoded_size & SQUASHFS_DATA_UNCOMPRESSED_BIT),
        logical_size=logical_size,
        is_sparse=stored_size == 0,
    )


def fragment_index_count(fragment_count: int) -> int:
    """Return the number of fragment-table index pointers for ``fragment_count``."""
    if not isinstance(fragment_count, int) or isinstance(fragment_count, bool):
        raise TypeError("Fragment count must be an integer")
    if not 0 <= fragment_count <= 0xFFFFFFFF:
        raise SquashFSFragmentIndexError("Fragment count is outside the unsigned 32-bit range")
    return (fragment_count + FRAGMENT_ENTRIES_PER_METADATA_BLOCK - 1) // FRAGMENT_ENTRIES_PER_METADATA_BLOCK


def parse_fragment_entry(data: bytes) -> SquashFSFragmentEntry:
    """Decode one 16-byte fragment-table entry without I/O."""
    if not isinstance(data, bytes):
        raise TypeError("Fragment entry data must be bytes")
    if len(data) < FRAGMENT_ENTRY_SIZE:
        raise SquashFSFragmentEntryError(
            f"Fragment entry requires {FRAGMENT_ENTRY_SIZE} bytes: got {len(data)}"
        )
    try:
        entry = SquashFSFragmentEntry(*FRAGMENT_ENTRY_STRUCT.unpack_from(data))
    except struct.error as error:
        raise SquashFSFragmentEntryError("Cannot unpack fragment entry") from error
    if entry.size & SQUASHFS_DATA_RESERVED_MASK:
        raise SquashFSFragmentEntryError(
            f"Fragment entry has reserved size bits: {entry.size:#010x}"
        )
    return entry


INODE_BODY_PARSERS = {
    EXTENDED_SYMLINK_INODE_TYPE: (EXTENDED_SYMLINK_INODE_BODY_SIZE, parse_extended_symlink_inode_body),
    EXTENDED_DIRECTORY_INODE_TYPE: (EXTENDED_DIRECTORY_INODE_BODY_SIZE, parse_extended_directory_inode_body),
    BASIC_DIRECTORY_INODE_TYPE: (
        BASIC_DIRECTORY_INODE_BODY_SIZE,
        parse_basic_directory_inode_body,
    ),
    BASIC_REGULAR_INODE_TYPE: (
        BASIC_REGULAR_INODE_BODY_SIZE,
        parse_basic_regular_inode_body,
    ),
    BASIC_SYMLINK_INODE_TYPE: (
        BASIC_SYMLINK_INODE_BODY_SIZE,
        parse_basic_symlink_inode_body,
    ),
    EXTENDED_REGULAR_INODE_TYPE: (
        EXTENDED_REGULAR_INODE_BODY_SIZE,
        parse_extended_regular_inode_body,
    ),
}


def read_inode(
    stream: SquashFSMetadataStream,
    reference: SquashFSMetadataReference,
) -> SquashFSInode:
    """Read one supported typed inode without reading file contents."""
    if not isinstance(stream, SquashFSMetadataStream):
        raise TypeError("Inode metadata stream has an invalid type")

    if not isinstance(reference, SquashFSMetadataReference):
        raise TypeError("Inode metadata reference has an invalid type")

    header = parse_inode_header(stream.read(reference, INODE_HEADER_SIZE))
    parser_entry = INODE_BODY_PARSERS.get(header.inode_type)
    if parser_entry is None:
        raise SquashFSUnsupportedInodeTypeError(
            f"Unsupported SquashFS inode type: {header.inode_type}"
        )

    body_size, parser = parser_entry
    body_reference = stream.advance_reference(reference, INODE_HEADER_SIZE)
    body = parser(header, stream.read(body_reference, body_size))
    return SquashFSInode(reference=reference, header=header, body=body)


def parse_directory_header(data: bytes) -> SquashFSDirectoryHeader:
    """Decode one fixed-size directory header without I/O."""
    if not isinstance(data, bytes):
        raise TypeError("Directory header data must be bytes")

    if len(data) < DIRECTORY_HEADER_SIZE:
        raise SquashFSDirectoryError(
            f"Directory header requires {DIRECTORY_HEADER_SIZE} bytes: got {len(data)}"
        )

    try:
        fields = DIRECTORY_HEADER_STRUCT.unpack_from(data)
    except struct.error as error:
        raise SquashFSDirectoryError("Cannot unpack directory header") from error

    return SquashFSDirectoryHeader(*fields)


def parse_directory_entry(data: bytes) -> SquashFSDirectoryEntry:
    """Decode exactly one variable-size directory entry without I/O."""
    if not isinstance(data, bytes):
        raise TypeError("Directory entry data must be bytes")

    if len(data) < DIRECTORY_ENTRY_SIZE:
        raise SquashFSDirectoryError(
            f"Directory entry requires {DIRECTORY_ENTRY_SIZE} bytes: got {len(data)}"
        )

    try:
        offset, inode_number_delta, entry_type, size = DIRECTORY_ENTRY_STRUCT.unpack_from(
            data
        )
    except struct.error as error:
        raise SquashFSDirectoryError("Cannot unpack directory entry") from error

    name_length = size + 1
    if name_length > DIRECTORY_NAME_MAX:
        raise SquashFSDirectoryError(
            "Directory entry name length exceeds "
            f"{DIRECTORY_NAME_MAX}: declared {name_length}"
        )

    encoded_size = DIRECTORY_ENTRY_SIZE + name_length
    if len(data) < encoded_size:
        raise SquashFSDirectoryError(
            "Directory entry name is truncated: "
            f"declared {name_length} bytes, available {len(data) - DIRECTORY_ENTRY_SIZE}"
        )

    return SquashFSDirectoryEntry(
        offset=offset,
        inode_number_delta=inode_number_delta,
        entry_type=entry_type,
        name=data[DIRECTORY_ENTRY_SIZE:encoded_size],
        encoded_size=encoded_size,
    )


def directory_entry_reference(
    header: SquashFSDirectoryHeader,
    entry: SquashFSDirectoryEntry,
) -> SquashFSMetadataReference:
    """Build an inode-table metadata reference from one directory entry group."""
    if not isinstance(header, SquashFSDirectoryHeader):
        raise TypeError("Directory header has an invalid type")

    if not isinstance(entry, SquashFSDirectoryEntry):
        raise TypeError("Directory entry has an invalid type")

    if (
        not isinstance(header.start_block, int)
        or isinstance(header.start_block, bool)
        or not 0 <= header.start_block <= 0xFFFFFFFF
    ):
        raise SquashFSDirectoryError(
            "Directory header start block is outside the unsigned 32-bit range"
        )

    if (
        not isinstance(entry.offset, int)
        or isinstance(entry.offset, bool)
        or not 0 <= entry.offset <= 0xFFFF
    ):
        raise SquashFSDirectoryError(
            "Directory entry offset is outside the unsigned 16-bit range"
        )

    return SquashFSMetadataReference(
        block_offset=header.start_block,
        byte_offset=entry.offset,
    )


def read_directory_indexes(
    metadata_stream: SquashFSMetadataStream,
    inode: SquashFSInode,
) -> tuple[list[SquashFSDirectoryIndex], SquashFSMetadataReference]:
    """Read the index area following one extended directory inode."""
    if not isinstance(metadata_stream, SquashFSMetadataStream) or not isinstance(inode, SquashFSInode):
        raise TypeError("Directory index arguments have invalid types")
    if not isinstance(inode.body, SquashFSExtendedDirectoryInode):
        raise SquashFSDirectoryIndexError("Typed inode is not an extended directory")
    reference = metadata_stream.advance_reference(inode.reference, EXTENDED_DIRECTORY_INODE_SIZE)
    indexes = []
    for _ in range(inode.body.i_count):
        try:
            header = metadata_stream.read(reference, DIRECTORY_INDEX_SIZE)
            _, _, size = DIRECTORY_INDEX_STRUCT.unpack(header)
            record = parse_directory_index(metadata_stream.read(reference, DIRECTORY_INDEX_SIZE + size + 1))
        except (SquashFSMetadataStreamError, struct.error) as error:
            raise SquashFSDirectoryIndexError("Cannot read directory index") from error
        indexes.append(record)
        reference = metadata_stream.advance_reference(reference, record.encoded_size)
    return indexes, reference


def read_directory(
    metadata_stream: SquashFSMetadataStream,
    directory_inode: SquashFSBasicDirectoryInode | SquashFSExtendedDirectoryInode,
) -> list[SquashFSDirectoryRecord]:
    """Read one basic or extended directory's sequential table records."""
    if not isinstance(metadata_stream, SquashFSMetadataStream):
        raise TypeError("Directory metadata stream has an invalid type")

    if not isinstance(directory_inode, (SquashFSBasicDirectoryInode, SquashFSExtendedDirectoryInode)):
        raise TypeError("Directory inode has an invalid type")

    if directory_inode.file_size < DIRECTORY_POSITION_OFFSET:
        raise SquashFSDirectoryReaderError(
            "Directory inode file size is smaller than the directory position offset: "
            f"size {directory_inode.file_size}, "
            f"offset {DIRECTORY_POSITION_OFFSET}"
        )

    stream_size = directory_inode.file_size - DIRECTORY_POSITION_OFFSET
    if stream_size == 0:
        return []

    reference = SquashFSMetadataReference(
        block_offset=directory_inode.start_block,
        byte_offset=directory_inode.offset,
    )
    data = metadata_stream.read(reference, stream_size)
    cursor = 0
    records: list[SquashFSDirectoryRecord] = []

    while cursor < len(data):
        header = parse_directory_header(data[cursor:])
        cursor += DIRECTORY_HEADER_SIZE
        entry_count = header.count + 1

        for _ in range(entry_count):
            entry = parse_directory_entry(data[cursor:])
            cursor += entry.encoded_size
            records.append(
                SquashFSDirectoryRecord(
                    inode_number=header.inode_number + entry.inode_number_delta,
                    inode_type=entry.entry_type,
                    name=entry.name,
                    inode_reference=directory_entry_reference(header, entry),
                )
            )

    if cursor != stream_size:
        raise SquashFSDirectoryReaderError(
            "Directory parser did not stop at the declared stream size: "
            f"cursor {cursor}, size {stream_size}"
        )

    return records


class SquashFSImage:
    """Open a SquashFS image and read its superblock."""

    def __init__(self, image: Path | str):
        self.image = Path(image)
        self.superblock: SquashFSSuperBlock | None = None

    def read_superblock(self) -> SquashFSSuperBlock:
        """Read and validate the fixed 96-byte SquashFS v4 superblock."""
        with self.image.open("rb") as source:
            data = source.read(SUPERBLOCK_SIZE)

        if len(data) != SUPERBLOCK_SIZE:
            raise ValueError("Image is smaller than a SquashFS superblock")

        superblock = SquashFSSuperBlock(*struct.unpack(SUPERBLOCK_FORMAT, data))

        if superblock.magic != SQUASHFS_MAGIC:
            raise ValueError(f"Not SquashFS: magic={superblock.magic:#010x}")

        self.superblock = superblock
        return superblock

    def read_metadata_block(self, offset: int) -> SquashFSMetadataBlock:
        """Read and decode one metadata block at an absolute image offset."""
        if not isinstance(offset, int) or isinstance(offset, bool):
            raise TypeError("Metadata offset must be an integer")

        image_size = self.image.stat().st_size

        if offset < 0 or offset >= image_size:
            raise SquashFSMetadataError(f"Metadata offset out of range: {offset:#x}")

        with self.image.open("rb") as source:
            source.seek(offset)
            header_data = source.read(METADATA_HEADER_SIZE)

            if len(header_data) != METADATA_HEADER_SIZE:
                raise SquashFSMetadataError(f"Short metadata header at {offset:#x}")

            header = struct.unpack("<H", header_data)[0]
            stored_size = header & ~METADATA_UNCOMPRESSED_BIT
            next_offset = offset + METADATA_HEADER_SIZE + stored_size

            if stored_size == 0:
                raise SquashFSMetadataError(f"Empty metadata payload at {offset:#x}")

            if next_offset > image_size:
                raise SquashFSMetadataError(
                    f"Metadata payload exceeds image at {offset:#x}"
                )

            payload = source.read(stored_size)

        if len(payload) != stored_size:
            raise SquashFSMetadataError(f"Short metadata payload at {offset:#x}")

        is_compressed = not bool(header & METADATA_UNCOMPRESSED_BIT)

        if is_compressed:
            try:
                data = _decompress_zstd_payload(payload, METADATA_SIZE)
            except zstandard.ZstdError as error:
                raise SquashFSMetadataError(
                    f"Invalid ZSTD metadata payload at {offset:#x}"
                ) from error
        else:
            data = payload

        if len(data) > METADATA_SIZE:
            raise SquashFSMetadataError(
                f"Metadata block exceeds {METADATA_SIZE} bytes at {offset:#x}"
            )

        return SquashFSMetadataBlock(
            offset=offset,
            stored_size=stored_size,
            is_compressed=is_compressed,
            data=data,
            next_offset=next_offset,
        )

    def read_regular_data_block(
        self,
        offset: int,
        block: SquashFSRegularFileBlock,
    ) -> bytes:
        """Read one ordinary regular-file data block at an absolute image offset."""
        if not isinstance(offset, int) or isinstance(offset, bool):
            raise TypeError("Regular-file data offset must be an integer")
        if not isinstance(block, SquashFSRegularFileBlock):
            raise TypeError("Regular-file block descriptor has an invalid type")
        if offset < 0:
            raise SquashFSDataBlockTruncatedError(
                f"Regular-file data offset must not be negative: {offset}"
            )
        if block.is_sparse:
            return b"\x00" * block.logical_size

        image_size = self.image.stat().st_size
        end_offset = offset + block.stored_size
        if end_offset > image_size:
            raise SquashFSDataBlockTruncatedError(
                "Regular-file data block exceeds image: "
                f"offset {offset:#x}, stored size {block.stored_size}"
            )

        with self.image.open("rb") as source:
            source.seek(offset)
            payload = source.read(block.stored_size)

        if len(payload) != block.stored_size:
            raise SquashFSDataBlockTruncatedError(
                "Regular-file data block is truncated: "
                f"expected {block.stored_size} bytes, got {len(payload)}"
            )

        if block.is_uncompressed:
            data = payload
        else:
            try:
                data = _decompress_zstd_payload(payload, block.logical_size)
            except zstandard.ZstdError as error:
                raise SquashFSDataBlockDecompressionError(
                    f"Invalid ZSTD regular-file data block at {offset:#x}"
                ) from error

        if len(data) != block.logical_size:
            raise SquashFSDataBlockSizeError(
                "Regular-file data block logical size mismatch: "
                f"expected {block.logical_size}, got {len(data)}"
            )
        return data

    def read_fragment_block(self, entry: SquashFSFragmentEntry) -> bytes:
        """Read and decode one complete fragment data block."""
        if not isinstance(entry, SquashFSFragmentEntry):
            raise TypeError("Fragment entry has an invalid type")
        superblock = self.superblock or self.read_superblock()
        image_size = self.image.stat().st_size
        stored_size = entry.stored_size
        end_offset = entry.start_block + stored_size
        if stored_size == 0 or end_offset > image_size:
            raise SquashFSFragmentBlockError(
                "Fragment data block exceeds image: "
                f"offset {entry.start_block:#x}, stored size {stored_size}"
            )

        with self.image.open("rb") as source:
            source.seek(entry.start_block)
            payload = source.read(stored_size)
        if len(payload) != stored_size:
            raise SquashFSFragmentBlockError(
                "Fragment data block is truncated: "
                f"expected {stored_size} bytes, got {len(payload)}"
            )

        if entry.is_uncompressed:
            data = payload
        else:
            try:
                data = _decompress_zstd_payload(payload, superblock.block_size)
            except zstandard.ZstdError as error:
                raise SquashFSFragmentBlockError(
                    f"Invalid ZSTD fragment payload at {entry.start_block:#x}"
                ) from error

        if not 0 < len(data) <= superblock.block_size:
            raise SquashFSFragmentBlockError(
                "Fragment data block decoded size is outside the permitted range: "
                f"{len(data)}"
            )
        return data


class SquashFSFragmentTable:
    """Look up SquashFS fragment entries using the fragment-table index."""

    def __init__(self, image: SquashFSImage):
        if not isinstance(image, SquashFSImage):
            raise TypeError("Fragment table image has an invalid type")
        self.image = image

    def _index_pointers(self) -> tuple[int, ...]:
        superblock = self.image.superblock or self.image.read_superblock()
        count = fragment_index_count(superblock.fragment_count)
        if count == 0:
            return ()

        index_size = count * FRAGMENT_INDEX_POINTER_SIZE
        image_size = self.image.image.stat().st_size
        index_end = superblock.fragment_table_start + index_size
        if index_end > image_size:
            raise SquashFSFragmentIndexError("Fragment table index exceeds image")

        with self.image.image.open("rb") as source:
            source.seek(superblock.fragment_table_start)
            data = source.read(index_size)
        if len(data) != index_size:
            raise SquashFSFragmentIndexError("Fragment table index is truncated")

        pointers = tuple(
            FRAGMENT_INDEX_POINTER_STRUCT.unpack_from(data, offset)[0]
            for offset in range(0, index_size, FRAGMENT_INDEX_POINTER_SIZE)
        )
        for pointer in pointers:
            if pointer >= superblock.fragment_table_start or pointer >= image_size:
                raise SquashFSFragmentIndexError(
                    f"Fragment metadata pointer is invalid: {pointer:#x}"
                )
        return pointers

    def read_entry(self, index: int) -> SquashFSFragmentEntry:
        """Return the typed fragment entry at ``index``."""
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError("Fragment index must be an integer")
        superblock = self.image.superblock or self.image.read_superblock()
        if index < 0 or index >= superblock.fragment_count:
            raise SquashFSFragmentIndexError(f"Fragment index out of range: {index}")

        block_index, entry_index = divmod(index, FRAGMENT_ENTRIES_PER_METADATA_BLOCK)
        pointers = self._index_pointers()
        try:
            metadata_start = pointers[block_index]
        except IndexError as error:
            raise SquashFSFragmentIndexError(
                f"Fragment index pointer is unavailable: {block_index}"
            ) from error

        stream = SquashFSMetadataStream(self.image, metadata_start)
        try:
            data = stream.read(
                SquashFSMetadataReference(0, entry_index * FRAGMENT_ENTRY_SIZE),
                FRAGMENT_ENTRY_SIZE,
            )
        except (SquashFSMetadataError, SquashFSMetadataStreamError) as error:
            raise SquashFSFragmentEntryError(
                f"Cannot read fragment entry {index}"
            ) from error
        return parse_fragment_entry(data)

    def read_block(self, index: int) -> bytes:
        """Read the complete decoded fragment data block at ``index``."""
        return self.image.read_fragment_block(self.read_entry(index))


class SquashFSMetadataStream:
    """Read ranges from a table's decompressed metadata blocks."""

    def __init__(self, image: SquashFSImage, table_start: int):
        if not isinstance(table_start, int) or isinstance(table_start, bool):
            raise TypeError("Metadata table start must be an integer")

        if table_start < 0:
            raise ValueError("Metadata table start must not be negative")

        self.image = image
        self.table_start = table_start

    def read(self, reference: SquashFSMetadataReference, size: int) -> bytes:
        """Read exactly ``size`` decompressed metadata bytes from ``reference``."""
        if not isinstance(reference, SquashFSMetadataReference):
            raise TypeError("Metadata stream reference has an invalid type")

        if not isinstance(size, int) or isinstance(size, bool):
            raise TypeError("Metadata stream size must be an integer")

        if size < 0:
            raise ValueError("Metadata stream size must not be negative")

        if size == 0:
            return b""

        current_offset = self.table_start + reference.block_offset
        current_byte_offset = reference.byte_offset
        remaining = size
        parts: list[bytes] = []

        while remaining:
            try:
                block = self.image.read_metadata_block(current_offset)
            except SquashFSMetadataError as error:
                raise SquashFSMetadataStreamError(
                    f"Cannot read metadata block at {current_offset:#x}"
                ) from error

            if current_byte_offset > len(block.data):
                raise SquashFSMetadataStreamError(
                    f"Metadata byte offset {current_byte_offset} exceeds block at "
                    f"{current_offset:#x}"
                )

            if current_byte_offset == len(block.data):
                current_offset = block.next_offset
                current_byte_offset = 0
                continue

            available = len(block.data) - current_byte_offset
            count = min(remaining, available)
            parts.append(block.data[current_byte_offset:current_byte_offset + count])
            remaining -= count
            current_offset = block.next_offset
            current_byte_offset = 0

        return b"".join(parts)

    def advance_reference(
        self,
        reference: SquashFSMetadataReference,
        delta: int,
    ) -> SquashFSMetadataReference:
        """Advance in decompressed metadata bytes, not physical block offsets."""
        if not isinstance(reference, SquashFSMetadataReference):
            raise TypeError("Metadata stream reference has an invalid type")
        if not isinstance(delta, int) or isinstance(delta, bool):
            raise TypeError("Metadata stream delta must be an integer")
        if delta < 0:
            raise ValueError("Metadata stream delta must not be negative")

        current_offset = self.table_start + reference.block_offset
        current_byte_offset = reference.byte_offset
        remaining = delta

        while True:
            try:
                block = self.image.read_metadata_block(current_offset)
            except SquashFSMetadataError as error:
                raise SquashFSMetadataStreamError(
                    f"Cannot read metadata block at {current_offset:#x}"
                ) from error

            if current_byte_offset > len(block.data):
                raise SquashFSMetadataStreamError(
                    "Metadata offset exceeds decompressed block: "
                    f"offset {current_byte_offset}, block size {len(block.data)}"
                )

            available = len(block.data) - current_byte_offset
            if remaining <= available:
                return SquashFSMetadataReference(
                    block_offset=current_offset - self.table_start,
                    byte_offset=current_byte_offset + remaining,
                )

            remaining -= available
            current_offset = block.next_offset
            current_byte_offset = 0

    def read_inode_header(self, reference: int) -> SquashFSInodeHeader:
        """Read and decode only the fixed common inode header."""
        metadata_reference = decode_metadata_reference(reference)
        data = self.read(metadata_reference, INODE_HEADER_SIZE)
        return parse_inode_header(data)

    def read_basic_directory_inode(
        self,
        reference: SquashFSMetadataReference,
    ) -> SquashFSBasicDirectoryInode:
        """Read and decode only a basic directory inode."""
        data = self.read(reference, BASIC_DIRECTORY_INODE_SIZE)
        return parse_basic_directory_inode(data)


def open_filesystem(image: SquashFSImage) -> SquashFSFilesystem:
    """Open the typed root inode without reading children or payloads."""
    if not isinstance(image, SquashFSImage):
        raise SquashFSFilesystemGraphError("Filesystem image has an invalid type")
    try:
        superblock = image.read_superblock()
        root_reference = decode_metadata_reference(superblock.root_inode)
        inode_stream = SquashFSMetadataStream(image, superblock.inode_table_start)
        root_inode = read_inode(inode_stream, root_reference)
    except (OSError, TypeError, ValueError, SquashFSMetadataStreamError, SquashFSInodeError) as error:
        raise SquashFSRootError("Cannot open SquashFS root inode") from error
    if not isinstance(root_inode.body, (SquashFSBasicDirectoryInode, SquashFSExtendedDirectoryInode)):
        raise SquashFSRootError("SquashFS root inode is not a directory")
    identity = SquashFSInodeIdentity(root_inode.reference, root_inode.header.inode_number)
    return SquashFSFilesystem(image, superblock, inode_stream, root_inode, identity)


def get_root(filesystem: SquashFSFilesystem) -> SquashFSDirectoryNode:
    """Return the immutable root node without performing further I/O."""
    if not isinstance(filesystem, SquashFSFilesystem):
        raise SquashFSFilesystemGraphError("Filesystem has an invalid type")
    return SquashFSDirectoryNode(
        filesystem, filesystem.root_identity, filesystem.root_inode,
        None, None, b"/", SquashFSNodeType.DIRECTORY,
    )

def _child_node(filesystem, parent, record, inode):
    if inode.reference != record.inode_reference or inode.header.inode_number != record.inode_number:
        raise SquashFSChildInodeError("Directory child identity does not match record")
    name = record.name
    if not isinstance(name, bytes) or not name or b'/' in name or b'\0' in name or name in (b'.', b'..'):
        raise SquashFSDirectoryEntryError("Directory child name is invalid")
    path = b'/' + name if parent.absolute_path == b'/' else parent.absolute_path + b'/' + name
    identity = SquashFSInodeIdentity(record.inode_reference, inode.header.inode_number)
    args = (filesystem, identity, inode, name, parent.absolute_path, path)
    if isinstance(inode.body, (SquashFSBasicDirectoryInode, SquashFSExtendedDirectoryInode)):
        return SquashFSDirectoryNode(*args, SquashFSNodeType.DIRECTORY)
    if isinstance(inode.body, (SquashFSBasicRegularInode, SquashFSExtendedRegularInode)):
        return SquashFSRegularFileNode(*args, SquashFSNodeType.REGULAR_FILE)
    if isinstance(inode.body, (SquashFSBasicSymlinkInode, SquashFSExtendedSymlinkInode)):
        return SquashFSSymlinkNode(*args, SquashFSNodeType.SYMLINK)
    return SquashFSUnsupportedNode(*args, SquashFSNodeType.UNSUPPORTED)

def list_children(filesystem: SquashFSFilesystem, directory: SquashFSDirectoryNode) -> SquashFSDirectoryListing:
    if not isinstance(filesystem, SquashFSFilesystem):
        raise SquashFSFilesystemGraphError("Filesystem or directory has an invalid type")
    if not isinstance(directory, SquashFSDirectoryNode):
        raise SquashFSNodeTypeError("Node is not a directory")
    if directory.filesystem is not filesystem:
        raise SquashFSFilesystemGraphError("Directory belongs to another filesystem")
    try:
        records = read_directory(SquashFSMetadataStream(filesystem.image, filesystem.superblock.directory_table_start), directory.inode.body)
    except (KeyError, IndexError, TypeError, ValueError, SquashFSMetadataStreamError) as error:
        raise SquashFSDirectoryReadError("Cannot read directory") from error
    children=[]
    for record in records:
        try: inode=read_inode(filesystem.inode_stream, record.inode_reference)
        except (KeyError, IndexError, TypeError, ValueError, SquashFSMetadataStreamError, SquashFSInodeError) as error:
            raise SquashFSChildInodeError("Cannot read directory child inode") from error
        children.append(_child_node(filesystem,directory,record,inode))
    return SquashFSDirectoryListing(directory.absolute_path, tuple(children))


def _path_components(path: bytes) -> tuple[bytes, ...]:
    if not isinstance(path, bytes):
        raise SquashFSPathError("Path must be bytes")
    if path == b"/":
        return ()
    if not path or not path.startswith(b"/") or path.endswith(b"/"):
        raise SquashFSPathError("Path must be a non-root absolute bytes path without a trailing slash")
    components = path[1:].split(b"/")
    if any(not part or b"\0" in part or part in (b".", b"..") for part in components):
        raise SquashFSPathError("Path contains an invalid component")
    return tuple(components)


def lookup_path(filesystem: SquashFSFilesystem, path: bytes) -> SquashFSPathNode:
    """Lazily resolve an absolute raw-bytes path without following symlinks."""
    if not isinstance(filesystem, SquashFSFilesystem):
        raise SquashFSFilesystemGraphError("Filesystem has an invalid type")
    components = _path_components(path)
    current: SquashFSPathNode = get_root(filesystem)
    for position, component in enumerate(components):
        if not isinstance(current, SquashFSDirectoryNode):
            raise SquashFSNotDirectoryError("Path component is not a directory: " + repr(current.absolute_path))
        matches = tuple(child for child in list_children(filesystem, current).children if child.raw_name == component)
        if not matches:
            raise SquashFSPathNotFoundError("Path component was not found: " + repr(component))
        if len(matches) != 1:
            raise SquashFSDuplicateNameError("Duplicate directory name at " + repr(current.absolute_path) + ": " + repr(component))
        current = matches[0]
        if position + 1 < len(components) and not isinstance(current, SquashFSDirectoryNode):
            raise SquashFSNotDirectoryError("Path component is not a directory: " + repr(current.absolute_path))
    return current


def walk_filesystem(filesystem: SquashFSFilesystem):
    """Return an immutable depth-first preorder traversal of the graph."""
    if not isinstance(filesystem, SquashFSFilesystem):
        raise SquashFSFilesystemGraphError("Filesystem has an invalid type")
    root = get_root(filesystem)
    result: list[SquashFSPathNode] = []
    paths: set[bytes] = set()

    def visit(node: SquashFSPathNode, active: tuple[SquashFSInodeIdentity, ...]) -> None:
        if node.absolute_path in paths:
            raise SquashFSDuplicateNameError("Duplicate absolute path: " + repr(node.absolute_path))
        paths.add(node.absolute_path)
        result.append(node)
        if not isinstance(node, SquashFSDirectoryNode):
            return
        for child in list_children(filesystem, node).children:
            if isinstance(child, SquashFSDirectoryNode) and child.identity in active:
                raise SquashFSDirectoryCycleError(
                    "Directory cycle at " + repr(child.absolute_path) + " for inode " + repr(child.identity)
                )
            visit(child, active + (child.identity,) if isinstance(child, SquashFSDirectoryNode) else active)

    visit(root, (root.identity,))
    return tuple(result)


def build_filesystem_index(filesystem: SquashFSFilesystem) -> SquashFSFilesystemIndex:
    """Build immutable forward and reverse indexes from one explicit walk."""
    nodes = walk_filesystem(filesystem)
    paths: dict[bytes, SquashFSPathNode] = {}
    inode_paths: dict[SquashFSInodeIdentity, list[bytes]] = {}
    for node in nodes:
        if node.absolute_path in paths:
            raise SquashFSFilesystemIndexError("Duplicate absolute path: " + repr(node.absolute_path))
        paths[node.absolute_path] = node
        inode_paths.setdefault(node.identity, []).append(node.absolute_path)
    return SquashFSFilesystemIndex(get_root(filesystem), nodes, MappingProxyType(paths),
                                   MappingProxyType({key: tuple(value) for key, value in inode_paths.items()}))


def node_for_path(index: SquashFSFilesystemIndex, path: bytes) -> SquashFSPathNode:
    if not isinstance(index, SquashFSFilesystemIndex):
        raise SquashFSFilesystemIndexError("Filesystem index has an invalid type")
    _path_components(path)
    try:
        return index.paths[path]
    except KeyError as error:
        raise SquashFSPathNotFoundError("Indexed path was not found: " + repr(path)) from error


def paths_for_inode(index: SquashFSFilesystemIndex, inode: SquashFSInodeIdentity | int) -> tuple[bytes, ...]:
    if not isinstance(index, SquashFSFilesystemIndex):
        raise SquashFSFilesystemIndexError("Filesystem index has an invalid type")
    if isinstance(inode, int) and not isinstance(inode, bool):
        matches = [paths for identity, paths in index.inode_paths.items() if identity.inode_number == inode]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise SquashFSFilesystemIndexError("Inode number is ambiguous; use SquashFSInodeIdentity")
        return ()
    if not isinstance(inode, SquashFSInodeIdentity):
        raise SquashFSFilesystemIndexError("Inode identity has an invalid type")
    return index.inode_paths.get(inode, ())


def read_node_bytes(filesystem: SquashFSFilesystem, node: SquashFSRegularFileNode) -> bytes:
    if not isinstance(filesystem, SquashFSFilesystem) or not isinstance(node, SquashFSRegularFileNode):
        raise SquashFSNodeTypeError("Node is not a regular file")
    if node.filesystem is not filesystem:
        raise SquashFSFilesystemGraphError("Node belongs to another filesystem")
    try:
        if isinstance(node.inode.body, SquashFSBasicRegularInode):
            return read_basic_regular_file(filesystem.image, filesystem.inode_stream, node.inode)
        return read_extended_regular_file(filesystem.image, filesystem.inode_stream, node.inode)
    except (OSError, TypeError, ValueError, SquashFSRegularFileError, SquashFSMetadataStreamError) as error:
        raise SquashFSNodeContentError("Cannot read regular-file node") from error


def read_node_symlink(filesystem: SquashFSFilesystem, node: SquashFSSymlinkNode) -> str:
    if not isinstance(filesystem, SquashFSFilesystem) or not isinstance(node, SquashFSSymlinkNode):
        raise SquashFSNodeTypeError("Node is not a symbolic link")
    if node.filesystem is not filesystem:
        raise SquashFSFilesystemGraphError("Node belongs to another filesystem")
    try:
        if isinstance(node.inode.body, SquashFSBasicSymlinkInode):
            return read_basic_symlink(filesystem.inode_stream, node.inode)
        return read_extended_symlink(filesystem.inode_stream, node.inode)
    except (OSError, TypeError, ValueError, SquashFSSymlinkError, SquashFSMetadataStreamError) as error:
        raise SquashFSNodeContentError("Cannot read symbolic-link node") from error


def read_node_xattrs(filesystem: SquashFSFilesystem, node: SquashFSPathNode, table: SquashFSXAttrIDTable | None = None) -> SquashFSXAttrList | None:
    if not isinstance(filesystem, SquashFSFilesystem) or not isinstance(node, SquashFSPathNode):
        raise SquashFSFilesystemGraphError("Filesystem or node has an invalid type")
    if node.filesystem is not filesystem:
        raise SquashFSFilesystemGraphError("Node belongs to another filesystem")
    try:
        return read_inode_xattrs(filesystem.image, node.inode, table)
    except (AttributeError, TypeError, ValueError, SquashFSXAttrError) as error:
        raise SquashFSNodeContentError("Cannot read node xattrs") from error


def _read_regular_file(
    image: SquashFSImage,
    metadata_stream: SquashFSMetadataStream,
    *,
    start_block: int,
    file_size: int,
    fragment: int,
    offset: int,
    block_list_reference: SquashFSMetadataReference,
) -> bytes:
    """Assemble a basic or extended regular file from its explicit fields."""
    superblock = image.superblock or image.read_superblock()
    tail_size = file_size % superblock.block_size
    if fragment != SQUASHFS_INVALID_FRAGMENT and tail_size == 0:
        raise SquashFSFragmentTailError("Regular-file fragment has no tail")
    entry_count = basic_regular_file_block_count(file_size, superblock.block_size, fragment)
    if entry_count == 0 and fragment == SQUASHFS_INVALID_FRAGMENT:
        return b""

    list_data = metadata_stream.read(
        block_list_reference, entry_count * REGULAR_FILE_BLOCK_SIZE_ENTRY_SIZE
    )
    blocks: list[SquashFSRegularFileBlock] = []
    remaining = file_size
    for index in range(entry_count):
        logical_size = min(superblock.block_size, remaining)
        entry_offset = index * REGULAR_FILE_BLOCK_SIZE_ENTRY_SIZE
        blocks.append(parse_regular_file_block_size_entry(list_data[entry_offset:], logical_size))
        remaining -= logical_size

    expected_remaining = tail_size if fragment != SQUASHFS_INVALID_FRAGMENT else 0
    if remaining != expected_remaining:
        raise SquashFSRegularFileError(
            "Regular-file block list does not cover declared file size: "
            f"remaining {remaining}"
        )

    data_offset = start_block
    parts: list[bytes] = []
    for block in blocks:
        parts.append(image.read_regular_data_block(data_offset, block))
        data_offset += block.stored_size

    if fragment != SQUASHFS_INVALID_FRAGMENT:
        try:
            fragment_block = SquashFSFragmentTable(image).read_block(fragment)
        except SquashFSFragmentError as error:
            raise SquashFSFragmentTailError("Cannot read regular-file fragment") from error
        fragment_end = offset + tail_size
        if offset > len(fragment_block) or fragment_end > len(fragment_block):
            raise SquashFSFragmentTailError("Regular-file fragment tail exceeds fragment block")
        parts.append(fragment_block[offset:fragment_end])

    result = b"".join(parts)
    if len(result) != file_size:
        raise SquashFSRegularFileError(
            "Regular-file result size mismatch: "
            f"expected {file_size}, got {len(result)}"
        )
    return result


def read_basic_regular_file(
    image: SquashFSImage,
    metadata_stream: SquashFSMetadataStream,
    inode: SquashFSInode,
) -> bytes:
    """Read all ordinary data blocks of one fragment-free basic regular file."""
    if not isinstance(image, SquashFSImage):
        raise TypeError("SquashFS image has an invalid type")
    if not isinstance(metadata_stream, SquashFSMetadataStream):
        raise TypeError("Regular-file metadata stream has an invalid type")
    if not isinstance(inode, SquashFSInode):
        raise TypeError("Regular-file inode has an invalid type")
    if metadata_stream.image is not image:
        raise ValueError("Regular-file metadata stream belongs to another image")
    if not isinstance(inode.body, SquashFSBasicRegularInode):
        raise SquashFSRegularFileError("Typed inode is not a basic regular file")

    regular_inode = inode.body
    return _read_regular_file(
        image,
        metadata_stream,
        start_block=regular_inode.start_block,
        file_size=regular_inode.file_size,
        fragment=regular_inode.fragment,
        offset=regular_inode.offset,
        block_list_reference=metadata_stream.advance_reference(
        inode.reference,
        BASIC_REGULAR_INODE_SIZE,
        ),
    )


def read_extended_regular_file(
    image: SquashFSImage,
    metadata_stream: SquashFSMetadataStream,
    inode: SquashFSInode,
) -> bytes:
    """Read all data blocks and an optional fragment tail of an extended file."""
    if not isinstance(image, SquashFSImage):
        raise TypeError("SquashFS image has an invalid type")
    if not isinstance(metadata_stream, SquashFSMetadataStream):
        raise TypeError("Regular-file metadata stream has an invalid type")
    if not isinstance(inode, SquashFSInode):
        raise TypeError("Regular-file inode has an invalid type")
    if metadata_stream.image is not image:
        raise ValueError("Regular-file metadata stream belongs to another image")
    if not isinstance(inode.body, SquashFSExtendedRegularInode):
        raise SquashFSRegularFileError("Typed inode is not an extended regular file")
    regular_inode = inode.body
    return _read_regular_file(
        image,
        metadata_stream,
        start_block=regular_inode.start_block,
        file_size=regular_inode.file_size,
        fragment=regular_inode.fragment,
        offset=regular_inode.offset,
        block_list_reference=metadata_stream.advance_reference(
            inode.reference, EXTENDED_REGULAR_INODE_SIZE
        ),
    )


def _read_symlink_target(stream: SquashFSMetadataStream, reference: SquashFSMetadataReference, size: int) -> str:
    try:
        return stream.read(reference, size).decode("utf-8")
    except SquashFSMetadataStreamError as error:
        raise SquashFSSymlinkError("Symbolic-link target is truncated") from error
    except UnicodeDecodeError as error:
        raise SquashFSSymlinkError("Symbolic-link target is not valid UTF-8") from error


def read_basic_symlink(
    metadata_stream: SquashFSMetadataStream,
    inode: SquashFSInode,
) -> str:
    """Read and UTF-8 decode the target of one basic symbolic-link inode."""
    if not isinstance(metadata_stream, SquashFSMetadataStream):
        raise TypeError("Symlink metadata stream has an invalid type")
    if not isinstance(inode, SquashFSInode):
        raise TypeError("Symlink inode has an invalid type")
    if not isinstance(inode.body, SquashFSBasicSymlinkInode):
        raise SquashFSSymlinkError("Typed inode is not a basic symbolic link")

    target_reference = metadata_stream.advance_reference(
        inode.reference,
        BASIC_SYMLINK_INODE_SIZE,
    )
    return _read_symlink_target(metadata_stream, target_reference, inode.body.symlink_size)


def read_extended_symlink(metadata_stream: SquashFSMetadataStream, inode: SquashFSInode) -> str:
    if not isinstance(metadata_stream, SquashFSMetadataStream) or not isinstance(inode, SquashFSInode):
        raise TypeError("Symlink reader arguments have invalid types")
    if not isinstance(inode.body, SquashFSExtendedSymlinkInode):
        raise SquashFSSymlinkError("Typed inode is not an extended symbolic link")
    return _read_symlink_target(
        metadata_stream,
        metadata_stream.advance_reference(inode.reference, EXTENDED_SYMLINK_INODE_SIZE),
        inode.body.symlink_size,
    )
