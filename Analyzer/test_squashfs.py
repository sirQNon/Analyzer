"""Stage 1 regression test for the extracted UDM SquashFS image."""

import struct
import tempfile
import unittest
from pathlib import Path

import zstandard

from squashfs import (
    METADATA_UNCOMPRESSED_BIT,
    SQUASHFS_MAGIC,
    SquashFSImage,
    SquashFSMetadataError,
)


ROOT = Path(__file__).resolve().parent.parent
ROOTFS = ROOT / "Extracted" / "rootfs"


class SquashFSSuperBlockTest(unittest.TestCase):
    def test_rootfs_superblock_matches_investigation(self):
        superblock = SquashFSImage(ROOTFS).read_superblock()

        self.assertEqual(superblock.magic, SQUASHFS_MAGIC)
        self.assertEqual(superblock.version_major, 4)
        self.assertEqual(superblock.version_minor, 0)
        self.assertEqual(superblock.compression, 6)
        self.assertEqual(superblock.block_size, 262144)
        self.assertEqual(superblock.inode_count, 43427)
        self.assertEqual(superblock.bytes_used, 609067236)
        self.assertEqual(superblock.fragment_count, 1677)
        self.assertEqual(superblock.id_count, 26)
        self.assertEqual(superblock.flags, 0x00C0)


class SquashFSMetadataBlockTest(unittest.TestCase):
    def read_temporary_block(self, contents: bytes):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "metadata.bin"
            image.write_bytes(contents)
            return SquashFSImage(image).read_metadata_block(0)

    def test_uncompressed_metadata_block(self):
        payload = b"metadata"
        header = struct.pack("<H", METADATA_UNCOMPRESSED_BIT | len(payload))

        block = self.read_temporary_block(header + payload)

        self.assertEqual(block.offset, 0)
        self.assertEqual(block.stored_size, len(payload))
        self.assertFalse(block.is_compressed)
        self.assertEqual(block.data, payload)
        self.assertEqual(block.next_offset, len(header) + len(payload))

    def test_compressed_zstd_metadata_block(self):
        payload = b"known ZSTD metadata payload" * 16
        stored = zstandard.ZstdCompressor().compress(payload)
        header = struct.pack("<H", len(stored))

        block = self.read_temporary_block(header + stored)

        self.assertEqual(block.stored_size, len(stored))
        self.assertTrue(block.is_compressed)
        self.assertEqual(block.data, payload)
        self.assertEqual(block.next_offset, len(header) + len(stored))

    def test_short_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "metadata.bin"
            image.write_bytes(b"\x01")

            with self.assertRaises(SquashFSMetadataError):
                SquashFSImage(image).read_metadata_block(0)

    def test_payload_outside_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "metadata.bin"
            image.write_bytes(struct.pack("<H", METADATA_UNCOMPRESSED_BIT | 5) + b"abc")

            with self.assertRaises(SquashFSMetadataError):
                SquashFSImage(image).read_metadata_block(0)

    def test_invalid_compressed_payload_is_rejected(self):
        with self.assertRaises(SquashFSMetadataError):
            self.read_temporary_block(struct.pack("<H", 4) + b"bad!")

    def test_decompressed_metadata_above_limit_is_rejected(self):
        payload = b"x" * 8193
        stored = zstandard.ZstdCompressor().compress(payload)

        with self.assertRaises(SquashFSMetadataError):
            self.read_temporary_block(struct.pack("<H", len(stored)) + stored)

    def test_rootfs_inode_table_metadata_block(self):
        image = SquashFSImage(ROOTFS)
        superblock = image.read_superblock()

        first = image.read_metadata_block(superblock.inode_table_start)
        second = image.read_metadata_block(superblock.inode_table_start)

        self.assertTrue(first.data)
        self.assertLessEqual(len(first.data), 8192)
        self.assertGreater(first.next_offset, first.offset)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
