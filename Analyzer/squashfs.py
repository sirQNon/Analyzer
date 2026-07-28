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


class SquashFSMetadataError(ValueError):
    """Invalid or unreadable SquashFS metadata block."""


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
