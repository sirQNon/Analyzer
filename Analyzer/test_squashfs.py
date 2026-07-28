"""Stage 1 regression test for the extracted UDM SquashFS image."""

import unittest
from pathlib import Path

from squashfs import SQUASHFS_MAGIC, SquashFSImage


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


if __name__ == "__main__":
    unittest.main()
