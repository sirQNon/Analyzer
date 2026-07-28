"""SquashFS v4 superblock reader."""

from __future__ import annotations

import struct
from dataclasses import dataclass
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
DIRECTORY_HEADER_STRUCT = struct.Struct("<III")
DIRECTORY_HEADER_SIZE = DIRECTORY_HEADER_STRUCT.size
DIRECTORY_ENTRY_STRUCT = struct.Struct("<HhHH")
DIRECTORY_ENTRY_SIZE = DIRECTORY_ENTRY_STRUCT.size
DIRECTORY_NAME_MAX = 256


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


@dataclass(frozen=True)
class SquashFSMetadataReference:
    """A location in a decompressed SquashFS metadata stream."""

    block_offset: int
    byte_offset: int


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


class SquashFSMetadataError(ValueError):
    """Invalid or unreadable SquashFS metadata block."""


class SquashFSMetadataStreamError(ValueError):
    """A requested range cannot be read from a SquashFS metadata stream."""


class SquashFSInodeError(ValueError):
    """Invalid or incomplete common SquashFS inode header."""


class SquashFSDirectoryError(ValueError):
    """Invalid or incomplete SquashFS directory structure."""


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

    try:
        body = BASIC_DIRECTORY_INODE_BODY_STRUCT.unpack_from(data, INODE_HEADER_SIZE)
    except struct.error as error:
        raise SquashFSInodeError("Cannot unpack basic directory inode body") from error

    return SquashFSBasicDirectoryInode(header, *body)


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
                data = zstandard.ZstdDecompressor().decompress(
                    payload,
                    max_output_size=METADATA_SIZE,
                )
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
