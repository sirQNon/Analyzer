import unittest
from pathlib import Path

from ext4 import Ext4Image


ROOT = Path(__file__).resolve().parent.parent


class Ext4ImageRangeReadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fs = Ext4Image(ROOT / "root.img")
        cls.inode_number = cls.fs.path_to_inode("/rootfs")
        cls.raw_inode = cls.fs.read_inode(cls.inode_number)
        cls.info = cls.fs.parse_inode(cls.raw_inode)
        cls.extents = cls.fs.extents.get_extents(cls.raw_inode)
        cls.block_size = cls.fs.read_superblock()["block_size"]

    def test_reads_file_beginning(self):
        expected = self.fs.read_block(self.extents[0]["physical_block"])[:64]

        self.assertEqual(self.fs.read_file_range(self.inode_number, 0, 64), expected)

    def test_reads_non_zero_offset(self):
        offset = self.block_size + 17
        expected = self.fs.read_block(self.extents[0]["physical_block"] + 1)[17:81]

        self.assertEqual(self.fs.read_file_range(self.inode_number, offset, 64), expected)

    def test_read_past_eof_is_truncated(self):
        offset = self.info["size"] - 10
        last_extent = self.extents[-1]
        last_block = last_extent["physical_block"] + last_extent["length"] - 1
        expected = self.fs.read_block(last_block)[-10:]

        self.assertEqual(self.fs.read_file_range(self.inode_number, offset, 64), expected)

    def test_zero_length_read(self):
        self.assertEqual(self.fs.read_file_range(self.inode_number, 0, 0), b"")

    def test_negative_offset_and_size_are_rejected(self):
        with self.assertRaises(ValueError):
            self.fs.read_file_range(self.inode_number, -1, 1)
        with self.assertRaises(ValueError):
            self.fs.read_file_range(self.inode_number, 0, -1)

    def test_range_reads_are_repeatable(self):
        self.assertEqual(
            self.fs.read_file_range(self.inode_number, 128, 64),
            self.fs.read_file_range(self.inode_number, 128, 64),
        )
