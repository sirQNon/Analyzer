"""
extent_tree.py

Production implementation of EXT4 extent tree traversal.

Supported:

    depth = 0
    depth = 1
    depth = N

Specification:

    struct ext4_extent_header
    struct ext4_extent_idx
    struct ext4_extent

Reference:

    fs/ext4/extents.h
"""

from __future__ import annotations

import struct

EXTENT_MAGIC = 0xF30A

HEADER_SIZE = 12
IDX_SIZE = 12
EXTENT_SIZE = 12


class ExtentTreeError(Exception):
    pass


class InvalidExtentHeader(ExtentTreeError):
    pass


class InvalidExtentDepth(ExtentTreeError):
    pass


class ExtentTree:

    def __init__(self, fs):

        self.fs = fs

    # ---------------------------------------------------------

    def get_extents(self, inode: bytes):

        header = self.parse_header(inode[40:52])

        if header["depth"] == 0:
            return self.read_leaf_from_inode(inode, header)

        return self.walk_index_node(
            inode,
            header,
        )

    # ---------------------------------------------------------

    def parse_header(self, data):

        if len(data) < HEADER_SIZE:
            raise InvalidExtentHeader()

        magic = struct.unpack_from("<H", data, 0)[0]

        if magic != EXTENT_MAGIC:
            raise InvalidExtentHeader(
                f"Bad magic {magic:#x}"
            )

        entries = struct.unpack_from("<H", data, 2)[0]
        maximum = struct.unpack_from("<H", data, 4)[0]
        depth = struct.unpack_from("<H", data, 6)[0]
        generation = struct.unpack_from("<I", data, 8)[0]

        return {

            "magic": magic,

            "entries": entries,

            "max": maximum,

            "depth": depth,

            "generation": generation,

        }

    # ---------------------------------------------------------

    def parse_extent(self, data):

        block = struct.unpack_from("<I", data, 0)[0]

        length = struct.unpack_from("<H", data, 4)[0]

        start_hi = struct.unpack_from("<H", data, 6)[0]

        start_lo = struct.unpack_from("<I", data, 8)[0]

        physical = (start_hi << 32) | start_lo

        return {

            "logical_block": block,

            "length": length,

            "physical_block": physical,

        }

    # ---------------------------------------------------------

    def parse_index(self, data):

        block = struct.unpack_from("<I", data, 0)[0]

        leaf_lo = struct.unpack_from("<I", data, 4)[0]

        leaf_hi = struct.unpack_from("<H", data, 8)[0]

        physical = (leaf_hi << 32) | leaf_lo

        return {

            "logical_block": block,

            "physical_block": physical,

        }

    # ---------------------------------------------------------

    def read_leaf_from_inode(
        self,
        inode,
        header,
    ):

        extents = []

        offset = 52

        for _ in range(header["entries"]):

            raw = inode[offset:offset + EXTENT_SIZE]

            extents.append(
                self.parse_extent(raw)
            )

            offset += EXTENT_SIZE

        return extents

    # ---------------------------------------------------------

    def read_header_from_block(
        self,
        block_number,
    ):

        block = self.fs.read_block(block_number)

        header = self.parse_header(
            block[:12]
        )

        return block, header

    # ---------------------------------------------------------

    def read_index_entries(
        self,
        block,
        header,
    ):

        indexes = []

        offset = 12

        for _ in range(header["entries"]):

            raw = block[offset:offset + IDX_SIZE]

            indexes.append(
                self.parse_index(raw)
            )

            offset += IDX_SIZE

        return indexes

    # ---------------------------------------------------------

    def read_leaf_entries(
        self,
        block,
        header,
    ):

        extents = []

        offset = 12

        for _ in range(header["entries"]):

            raw = block[offset:offset + EXTENT_SIZE]

            extents.append(
                self.parse_extent(raw)
            )

            offset += EXTENT_SIZE

        return extents
        # ---------------------------------------------------------

    def walk_index_node(
        self,
        inode,
        header,
    ):

        extents = []

        offset = 52

        for _ in range(header["entries"]):

            raw = inode[offset:offset + IDX_SIZE]

            index = self.parse_index(raw)

            extents.extend(
                self.walk_node(
                    index["physical_block"]
                )
            )

            offset += IDX_SIZE

        return extents

    # ---------------------------------------------------------

    def walk_node(
        self,
        block_number,
    ):

        block, header = self.read_header_from_block(
            block_number
        )

        if header["depth"] == 0:

            return self.read_leaf_entries(
                block,
                header,
            )

        indexes = self.read_index_entries(
            block,
            header,
        )

        extents = []

        for index in indexes:

            extents.extend(
                self.walk_node(
                    index["physical_block"]
                )
            )

        return extents

    # ---------------------------------------------------------

    def validate(self, inode):

        header = self.parse_header(
            inode[40:52]
        )

        if header["entries"] > header["max"]:

            raise InvalidExtentHeader(
                "entries > max"
            )

        if header["depth"] > 5:

            raise InvalidExtentDepth(
                f"Unsupported depth {header['depth']}"
            )

        return True

    # ---------------------------------------------------------

    def dump(self, inode):

        self.validate(inode)

        extents = self.get_extents(inode)

        print("=" * 60)
        print("EXTENTS")
        print("=" * 60)

        for i, e in enumerate(extents):

            print(
                f"{i:4}  "
                f"logical={e['logical_block']:8}  "
                f"length={e['length']:8}  "
                f"physical={e['physical_block']}"
            )

        print()

        return extents