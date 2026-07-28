"""SquashFS v4 superblock reader."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


SQUASHFS_MAGIC = 0x73717368
SUPERBLOCK_FORMAT = "<IIIIIHHHHHHQQQQQQQQ"
SUPERBLOCK_SIZE = struct.calcsize(SUPERBLOCK_FORMAT)


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
