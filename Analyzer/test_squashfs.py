"""Stage 1 regression test for the extracted UDM SquashFS image."""

import struct
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import zstandard

from squashfs import (
    BASIC_DIRECTORY_INODE_BODY_STRUCT,
    BASIC_DIRECTORY_INODE_SIZE,
    BASIC_DIRECTORY_INODE_TYPE,
    BASIC_REGULAR_INODE_BODY_STRUCT,
    BASIC_REGULAR_INODE_SIZE,
    BASIC_REGULAR_INODE_TYPE,
    BASIC_SYMLINK_INODE_BODY_STRUCT,
    BASIC_SYMLINK_INODE_SIZE,
    BASIC_SYMLINK_INODE_TYPE,
    EXTENDED_REGULAR_INODE_BODY_STRUCT,
    EXTENDED_REGULAR_INODE_SIZE,
    EXTENDED_REGULAR_INODE_TYPE,
    EXTENDED_DIRECTORY_INODE_BODY_STRUCT,
    EXTENDED_DIRECTORY_INODE_SIZE,
    EXTENDED_DIRECTORY_INODE_TYPE,
    EXTENDED_SYMLINK_INODE_BODY_STRUCT,
    EXTENDED_SYMLINK_INODE_TYPE,
    DIRECTORY_INDEX_STRUCT,
    SQUASHFS_INVALID_BLK,
    XATTR_ID_STRUCT,
    DIRECTORY_ENTRY_SIZE,
    DIRECTORY_ENTRY_STRUCT,
    DIRECTORY_HEADER_SIZE,
    DIRECTORY_HEADER_STRUCT,
    DIRECTORY_NAME_MAX,
    DIRECTORY_POSITION_OFFSET,
    INODE_HEADER_SIZE,
    INODE_HEADER_STRUCT,
    METADATA_UNCOMPRESSED_BIT,
    METADATA_SIZE,
    FRAGMENT_ENTRY_STRUCT,
    FRAGMENT_ENTRIES_PER_METADATA_BLOCK,
    FRAGMENT_INDEX_POINTER_STRUCT,
    REGULAR_FILE_BLOCK_SIZE_ENTRY_SIZE,
    REGULAR_FILE_BLOCK_SIZE_STRUCT,
    SQUASHFS_DATA_UNCOMPRESSED_BIT,
    SQUASHFS_INVALID_FRAGMENT,
    SQUASHFS_MAGIC,
    SquashFSInodeError,
    SquashFSInode,
    SquashFSBasicDirectoryInode,
    SquashFSBasicRegularInode,
    SquashFSBasicSymlinkInode,
    SquashFSExtendedRegularInode,
    SquashFSExtendedDirectoryInode,
    SquashFSExtendedSymlinkInode,
    SquashFSInodeLookupIndexError,
    SquashFSInodeLookupEntryError,
    SquashFSXAttrTableError,
    SquashFSXAttrIDError,
    SquashFSXAttrListError,
    SquashFSXAttrEntryError,
    SquashFSXAttrValueError,
    SquashFSXAttrInodeError,
    SquashFSXAttrEntry,
    SquashFSXAttrIDTable,
    decode_xattr_namespace,
    read_xattr_list,
    read_inode_xattrs,
    read_xattr_id_table,
    read_xattr_id,
    decode_xattr_reference,
    read_xattr_out_of_line_value,
    SquashFSInodeLookupTableError,
    SquashFSDirectoryIndex,
    SquashFSDirectoryEntry,
    SquashFSDirectoryError,
    SquashFSDirectoryHeader,
    SquashFSDirectoryReaderError,
    SquashFSDirectoryRecord,
    SquashFSInodeHeader,
    SquashFSDataBlockDecompressionError,
    SquashFSDataBlockSizeError,
    SquashFSDataBlockTruncatedError,
    SquashFSFragmentTailError,
    SquashFSFragmentBlockError,
    SquashFSFragmentEntry,
    SquashFSFragmentEntryError,
    SquashFSFragmentIndexError,
    SquashFSFragmentTable,
    SquashFSMalformedBlockListError,
    SquashFSImage,
    SquashFSMetadataError,
    SquashFSMetadataReference,
    SquashFSMetadataStream,
    SquashFSMetadataStreamError,
    SquashFSUnsupportedInodeTypeError,
    SquashFSSymlinkError,
    basic_regular_file_block_count,
    fragment_index_count,
    decode_metadata_reference,
    directory_entry_reference,
    parse_basic_directory_inode,
    parse_basic_symlink_inode,
    parse_extended_regular_inode,
    parse_directory_index,
    parse_fragment_entry,
    parse_directory_entry,
    parse_directory_header,
    parse_inode_header,
    parse_regular_file_block_size_entry,
    read_basic_regular_file,
    read_extended_regular_file,
    read_directory_indexes,
    read_extended_symlink,
    read_inode_lookup_table,
    read_inode_lookup_entry,
    resolve_inode_number,
    read_basic_symlink,
    read_directory,
    read_inode,
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


class SquashFSMetadataReferenceTest(unittest.TestCase):
    def test_reference_decoding(self):
        self.assertEqual(
            decode_metadata_reference(0),
            SquashFSMetadataReference(block_offset=0, byte_offset=0),
        )
        self.assertEqual(
            decode_metadata_reference(0x123456789ABCDEF0),
            SquashFSMetadataReference(
                block_offset=0x123456789ABC,
                byte_offset=0xDEF0,
            ),
        )
        self.assertEqual(
            decode_metadata_reference(0xFFFFFFFFFFFFFFFF),
            SquashFSMetadataReference(
                block_offset=0xFFFFFFFFFFFF,
                byte_offset=0xFFFF,
            ),
        )

    def test_invalid_reference_is_rejected(self):
        for reference in (-1, 0x10000000000000000):
            with self.assertRaises(ValueError):
                decode_metadata_reference(reference)

        for reference in (True, "1"):
            with self.assertRaises(TypeError):
                decode_metadata_reference(reference)


class SquashFSMetadataStreamTest(unittest.TestCase):
    def write_stream(self, *blocks: bytes) -> tuple[tempfile.TemporaryDirectory, Path]:
        directory = tempfile.TemporaryDirectory()
        image = Path(directory.name) / "metadata.bin"
        image.write_bytes(b"".join(blocks))
        return directory, image

    @staticmethod
    def uncompressed_block(payload: bytes) -> bytes:
        return struct.pack("<H", METADATA_UNCOMPRESSED_BIT | len(payload)) + payload

    @staticmethod
    def compressed_block(payload: bytes) -> bytes:
        stored = zstandard.ZstdCompressor().compress(payload)
        return struct.pack("<H", len(stored)) + stored

    def test_reads_inside_uncompressed_block(self):
        directory, image = self.write_stream(self.uncompressed_block(b"abcdef"))
        with directory:
            stream = SquashFSMetadataStream(SquashFSImage(image), 0)
            self.assertEqual(
                stream.read(SquashFSMetadataReference(0, 2), 3),
                b"cde",
            )

    def test_reads_inside_compressed_block(self):
        directory, image = self.write_stream(self.compressed_block(b"abcdef"))
        with directory:
            stream = SquashFSMetadataStream(SquashFSImage(image), 0)
            self.assertEqual(
                stream.read(SquashFSMetadataReference(0, 1), 4),
                b"bcde",
            )

    def test_reads_across_uncompressed_blocks(self):
        directory, image = self.write_stream(
            self.uncompressed_block(b"abc"),
            self.uncompressed_block(b"def"),
        )
        with directory:
            stream = SquashFSMetadataStream(SquashFSImage(image), 0)
            self.assertEqual(
                stream.read(SquashFSMetadataReference(0, 2), 4),
                b"cdef",
            )

    def test_reads_across_mixed_blocks(self):
        directory, image = self.write_stream(
            self.compressed_block(b"hello"),
            self.uncompressed_block(b"world"),
        )
        with directory:
            stream = SquashFSMetadataStream(SquashFSImage(image), 0)
            self.assertEqual(
                stream.read(SquashFSMetadataReference(0, 3), 5),
                b"lowor",
            )

    def test_zero_size_does_not_read_image(self):
        stream = SquashFSMetadataStream(SquashFSImage("missing.bin"), 0)
        self.assertEqual(stream.read(SquashFSMetadataReference(0, 999), 0), b"")

    def test_invalid_byte_offset_is_rejected(self):
        directory, image = self.write_stream(self.uncompressed_block(b"abc"))
        with directory:
            stream = SquashFSMetadataStream(SquashFSImage(image), 0)
            with self.assertRaises(SquashFSMetadataStreamError):
                stream.read(SquashFSMetadataReference(0, 4), 1)

    def test_truncated_stream_is_rejected(self):
        directory, image = self.write_stream(self.uncompressed_block(b"abc"))
        with directory:
            stream = SquashFSMetadataStream(SquashFSImage(image), 0)
            with self.assertRaises(SquashFSMetadataStreamError):
                stream.read(SquashFSMetadataReference(0, 2), 2)

    def test_root_inode_reference_stream_integration(self):
        image = SquashFSImage(ROOTFS)
        superblock = image.read_superblock()
        reference = decode_metadata_reference(superblock.root_inode)
        stream = SquashFSMetadataStream(image, superblock.inode_table_start)

        first = stream.read(reference, 32)
        second = stream.read(reference, 32)

        self.assertEqual(reference.block_offset, 0x5A1E8)
        self.assertEqual(reference.byte_offset, 0x08EB)
        self.assertEqual(superblock.inode_table_start + reference.block_offset, 0x24467007)
        self.assertEqual(len(first), 32)
        self.assertEqual(first, second)


class SquashFSInodeHeaderTest(unittest.TestCase):
    @staticmethod
    def known_header_data() -> bytes:
        return INODE_HEADER_STRUCT.pack(
            1,
            0o775,
            0,
            0,
            1692784843,
            43427,
        )

    def test_parses_known_inode_header(self):
        header = parse_inode_header(self.known_header_data())

        self.assertEqual(
            header,
            SquashFSInodeHeader(
                inode_type=1,
                mode=0o775,
                uid=0,
                guid=0,
                mtime=1692784843,
                inode_number=43427,
            ),
        )

    def test_short_inode_header_is_rejected(self):
        with self.assertRaises(SquashFSInodeError):
            parse_inode_header(b"\x00" * (INODE_HEADER_SIZE - 1))

    def test_invalid_inode_header_type_is_rejected(self):
        with self.assertRaises(TypeError):
            parse_inode_header(bytearray(INODE_HEADER_SIZE))

    def test_inode_header_parser_is_repeatable(self):
        data = self.known_header_data()

        self.assertEqual(parse_inode_header(data), parse_inode_header(data))

    def test_root_inode_header_stream_integration(self):
        image = SquashFSImage(ROOTFS)
        superblock = image.read_superblock()
        stream = SquashFSMetadataStream(image, superblock.inode_table_start)

        first = stream.read_inode_header(superblock.root_inode)
        second = stream.read_inode_header(superblock.root_inode)

        self.assertIsInstance(first, SquashFSInodeHeader)
        self.assertEqual(first, second)
        self.assertIsInstance(first.inode_type, int)
        self.assertIsInstance(first.mode, int)
        self.assertIsInstance(first.uid, int)
        self.assertIsInstance(first.guid, int)
        self.assertIsInstance(first.mtime, int)
        self.assertIsInstance(first.inode_number, int)


class SquashFSBasicDirectoryInodeTest(unittest.TestCase):
    @staticmethod
    def known_inode_data(inode_type: int = BASIC_DIRECTORY_INODE_TYPE) -> bytes:
        return (
            INODE_HEADER_STRUCT.pack(
                inode_type,
                0o775,
                0,
                0,
                1692784843,
                43427,
            )
            + BASIC_DIRECTORY_INODE_BODY_STRUCT.pack(
                395215,
                14,
                226,
                3260,
                43428,
            )
        )

    def test_parses_known_basic_directory_inode(self):
        inode = parse_basic_directory_inode(self.known_inode_data())

        self.assertIsInstance(inode, SquashFSBasicDirectoryInode)
        self.assertEqual(
            inode.header,
            SquashFSInodeHeader(1, 0o775, 0, 0, 1692784843, 43427),
        )
        self.assertEqual(inode.start_block, 395215)
        self.assertEqual(inode.nlink, 14)
        self.assertEqual(inode.file_size, 226)
        self.assertEqual(inode.offset, 3260)
        self.assertEqual(inode.parent_inode, 43428)

    def test_short_basic_directory_inode_is_rejected(self):
        data = b"\x00" * (BASIC_DIRECTORY_INODE_SIZE - 1)

        with self.assertRaises(SquashFSInodeError):
            parse_basic_directory_inode(data)

    def test_invalid_basic_directory_inode_type_is_rejected(self):
        data = self.known_inode_data(inode_type=BASIC_DIRECTORY_INODE_TYPE + 1)

        with self.assertRaises(SquashFSInodeError) as error:
            parse_basic_directory_inode(data)

        self.assertIn("expected 1, got 2", str(error.exception))

    def test_invalid_basic_directory_inode_python_types_are_rejected(self):
        for value in (bytearray(BASIC_DIRECTORY_INODE_SIZE), "inode", None):
            with self.assertRaises(TypeError):
                parse_basic_directory_inode(value)

    def test_basic_directory_inode_parser_is_repeatable(self):
        data = self.known_inode_data()

        self.assertEqual(
            parse_basic_directory_inode(data),
            parse_basic_directory_inode(data),
        )

    def test_root_basic_directory_inode_stream_integration(self):
        image = SquashFSImage(ROOTFS)
        superblock = image.read_superblock()
        reference = decode_metadata_reference(superblock.root_inode)
        stream = SquashFSMetadataStream(image, superblock.inode_table_start)

        inode = stream.read_basic_directory_inode(reference)

        self.assertEqual(inode.header.inode_type, BASIC_DIRECTORY_INODE_TYPE)
        self.assertEqual(inode.header.mode, 0o775)
        self.assertEqual(inode.header.inode_number, 43427)
        self.assertEqual(inode.start_block, 395215)
        self.assertEqual(inode.nlink, 14)
        self.assertEqual(inode.file_size, 226)
        self.assertEqual(inode.offset, 3260)
        self.assertEqual(inode.parent_inode, 43428)


class SquashFSDirectoryHeaderTest(unittest.TestCase):
    @staticmethod
    def known_header_data() -> bytes:
        return DIRECTORY_HEADER_STRUCT.pack(1, 0, 1)

    def test_parses_known_directory_header(self):
        header = parse_directory_header(self.known_header_data())

        self.assertEqual(header, SquashFSDirectoryHeader(1, 0, 1))

    def test_short_directory_header_is_rejected(self):
        with self.assertRaises(SquashFSDirectoryError):
            parse_directory_header(b"\x00" * (DIRECTORY_HEADER_SIZE - 1))

    def test_invalid_directory_header_python_types_are_rejected(self):
        for value in (bytearray(DIRECTORY_HEADER_SIZE), "header", None):
            with self.assertRaises(TypeError):
                parse_directory_header(value)

    def test_directory_header_parser_is_repeatable(self):
        data = self.known_header_data()

        self.assertEqual(parse_directory_header(data), parse_directory_header(data))


class SquashFSDirectoryEntryTest(unittest.TestCase):
    @staticmethod
    def entry_data(
        name: bytes,
        inode_number_delta: int = 0,
        offset: int = 3958,
        entry_type: int = 1,
    ) -> bytes:
        return DIRECTORY_ENTRY_STRUCT.pack(
            offset,
            inode_number_delta,
            entry_type,
            len(name) - 1,
        ) + name

    def test_parses_known_directory_entry(self):
        entry = parse_directory_entry(self.entry_data(b"bin"))

        self.assertEqual(
            entry,
            SquashFSDirectoryEntry(
                offset=3958,
                inode_number_delta=0,
                entry_type=1,
                name=b"bin",
                encoded_size=DIRECTORY_ENTRY_SIZE + 3,
            ),
        )

    def test_parses_one_byte_name(self):
        entry = parse_directory_entry(self.entry_data(b"x"))

        self.assertEqual(entry.name, b"x")
        self.assertEqual(entry.encoded_size, DIRECTORY_ENTRY_SIZE + 1)

    def test_parses_maximum_name_length(self):
        name = b"x" * DIRECTORY_NAME_MAX
        entry = parse_directory_entry(self.entry_data(name))

        self.assertEqual(entry.name, name)
        self.assertEqual(entry.encoded_size, DIRECTORY_ENTRY_SIZE + DIRECTORY_NAME_MAX)

    def test_short_fixed_directory_entry_is_rejected(self):
        with self.assertRaises(SquashFSDirectoryError):
            parse_directory_entry(b"\x00" * (DIRECTORY_ENTRY_SIZE - 1))

    def test_truncated_directory_entry_name_is_rejected(self):
        data = DIRECTORY_ENTRY_STRUCT.pack(0, 0, 1, 2) + b"ab"

        with self.assertRaises(SquashFSDirectoryError) as error:
            parse_directory_entry(data)

        self.assertIn("declared 3 bytes, available 2", str(error.exception))

    def test_directory_entry_name_above_confirmed_limit_is_rejected(self):
        data = DIRECTORY_ENTRY_STRUCT.pack(0, 0, 1, DIRECTORY_NAME_MAX)

        with self.assertRaises(SquashFSDirectoryError) as error:
            parse_directory_entry(data)

        self.assertIn("declared 257", str(error.exception))

    def test_invalid_directory_entry_python_types_are_rejected(self):
        for value in (bytearray(DIRECTORY_ENTRY_SIZE), "entry", None):
            with self.assertRaises(TypeError):
                parse_directory_entry(value)

    def test_negative_inode_number_delta_is_preserved(self):
        entry = parse_directory_entry(self.entry_data(b"bin", inode_number_delta=-1))

        self.assertEqual(entry.inode_number_delta, -1)

    def test_directory_entry_trailing_bytes_are_not_consumed(self):
        data = self.entry_data(b"bin") + self.entry_data(b"etc")
        entry = parse_directory_entry(data)

        self.assertEqual(entry.name, b"bin")
        self.assertEqual(entry.encoded_size, DIRECTORY_ENTRY_SIZE + len(b"bin"))

    def test_directory_entry_parser_is_repeatable(self):
        data = self.entry_data(b"bin")

        self.assertEqual(parse_directory_entry(data), parse_directory_entry(data))

    def test_root_directory_header_and_entry_dump(self):
        header = parse_directory_header(
            bytes.fromhex("01 00 00 00 00 00 00 00 01 00 00 00")
        )
        entry = parse_directory_entry(
            bytes.fromhex("76 0f 00 00 01 00 02 00 62 69 6e")
        )

        self.assertEqual(header, SquashFSDirectoryHeader(1, 0, 1))
        self.assertEqual(entry.offset, 3958)
        self.assertEqual(entry.inode_number_delta, 0)
        self.assertEqual(entry.entry_type, 1)
        self.assertEqual(entry.name, b"bin")
        self.assertEqual(entry.encoded_size, DIRECTORY_ENTRY_SIZE + 3)


class SquashFSDirectoryReaderTest(unittest.TestCase):
    @staticmethod
    def basic_inode(file_size: int) -> SquashFSBasicDirectoryInode:
        return SquashFSBasicDirectoryInode(
            header=SquashFSInodeHeader(1, 0o755, 0, 0, 0, 1),
            start_block=0,
            nlink=2,
            file_size=file_size,
            offset=0,
            parent_inode=1,
        )

    @staticmethod
    def directory_entry(
        name: bytes,
        inode_number_delta: int,
        entry_type: int,
        offset: int,
    ) -> bytes:
        return DIRECTORY_ENTRY_STRUCT.pack(
            offset,
            inode_number_delta,
            entry_type,
            len(name) - 1,
        ) + name

    def directory_stream(self, payload: bytes) -> tuple[tempfile.TemporaryDirectory, SquashFSMetadataStream]:
        directory = tempfile.TemporaryDirectory()
        image = Path(directory.name) / "directory.bin"
        image.write_bytes(
            struct.pack("<H", METADATA_UNCOMPRESSED_BIT | len(payload)) + payload
        )
        return directory, SquashFSMetadataStream(SquashFSImage(image), 0)

    def read_payload(self, payload: bytes) -> list[SquashFSDirectoryRecord]:
        directory, stream = self.directory_stream(payload)
        with directory:
            inode = self.basic_inode(len(payload) + DIRECTORY_POSITION_OFFSET)
            return read_directory(stream, inode)

    def test_reads_directory_with_one_header(self):
        payload = (
            DIRECTORY_HEADER_STRUCT.pack(0, 0, 10)
            + self.directory_entry(b"bin", 0, 1, 3958)
        )

        records = self.read_payload(payload)

        self.assertEqual(
            records,
            [
                SquashFSDirectoryRecord(
                    10,
                    1,
                    b"bin",
                    SquashFSMetadataReference(0, 3958),
                )
            ],
        )

    def test_entries_in_one_header_share_start_block_and_keep_offsets(self):
        payload = (
            DIRECTORY_HEADER_STRUCT.pack(1, 42, 10)
            + self.directory_entry(b"bin", 0, 1, 100)
            + self.directory_entry(b"etc", -1, 2, 200)
        )

        records = self.read_payload(payload)

        self.assertEqual(
            records,
            [
                SquashFSDirectoryRecord(
                    10,
                    1,
                    b"bin",
                    SquashFSMetadataReference(42, 100),
                ),
                SquashFSDirectoryRecord(
                    9,
                    2,
                    b"etc",
                    SquashFSMetadataReference(42, 200),
                ),
            ],
        )

    def test_reads_directory_with_multiple_headers(self):
        payload = (
            DIRECTORY_HEADER_STRUCT.pack(0, 0, 10)
            + self.directory_entry(b"bin", 0, 1, 100)
            + DIRECTORY_HEADER_STRUCT.pack(0, 4, 20)
            + self.directory_entry(b"etc", -1, 2, 200)
        )

        records = self.read_payload(payload)

        self.assertEqual(
            records[0],
            SquashFSDirectoryRecord(10, 1, b"bin", SquashFSMetadataReference(0, 100)),
        )
        self.assertEqual(
            records[1],
            SquashFSDirectoryRecord(19, 2, b"etc", SquashFSMetadataReference(4, 200)),
        )

    def test_preserves_inode_type_and_name_bytes(self):
        payload = (
            DIRECTORY_HEADER_STRUCT.pack(0, 0, 7)
            + self.directory_entry(b"\xff", 0, 6, 1)
        )

        record = self.read_payload(payload)[0]

        self.assertEqual(record.inode_type, 6)
        self.assertEqual(record.name, b"\xff")
        self.assertEqual(record.inode_reference, SquashFSMetadataReference(0, 1))

    def test_stops_at_declared_directory_size(self):
        directory_payload = (
            DIRECTORY_HEADER_STRUCT.pack(0, 0, 3)
            + self.directory_entry(b"one", 0, 1, 1)
        )
        trailing_payload = directory_payload + b"unused metadata"
        directory, stream = self.directory_stream(trailing_payload)
        with directory:
            inode = self.basic_inode(
                len(directory_payload) + DIRECTORY_POSITION_OFFSET
            )
            self.assertEqual(
                read_directory(stream, inode),
                [
                    SquashFSDirectoryRecord(
                        3,
                        1,
                        b"one",
                        SquashFSMetadataReference(0, 1),
                    )
                ],
            )

    def test_directory_reader_is_repeatable(self):
        payload = (
            DIRECTORY_HEADER_STRUCT.pack(0, 0, 3)
            + self.directory_entry(b"one", 0, 1, 1)
        )
        directory, stream = self.directory_stream(payload)
        with directory:
            inode = self.basic_inode(len(payload) + DIRECTORY_POSITION_OFFSET)
            self.assertEqual(read_directory(stream, inode), read_directory(stream, inode))

    def test_invalid_python_types_are_rejected(self):
        inode = self.basic_inode(DIRECTORY_POSITION_OFFSET)

        for invalid_stream in (None, "stream", object()):
            with self.assertRaises(TypeError):
                read_directory(invalid_stream, inode)

        directory, stream = self.directory_stream(b"")
        with directory:
            for invalid_inode in (None, "inode", object()):
                with self.assertRaises(TypeError):
                    read_directory(stream, invalid_inode)

    def test_invalid_directory_size_is_rejected(self):
        directory, stream = self.directory_stream(b"")
        with directory:
            with self.assertRaises(SquashFSDirectoryReaderError):
                read_directory(stream, self.basic_inode(DIRECTORY_POSITION_OFFSET - 1))

    def test_directory_entry_reference_rejects_invalid_python_types(self):
        header = SquashFSDirectoryHeader(0, 0, 1)
        entry = SquashFSDirectoryEntry(0, 0, 1, b"one", 11)

        for invalid_header in (None, "header", object()):
            with self.assertRaises(TypeError):
                directory_entry_reference(invalid_header, entry)

        for invalid_entry in (None, "entry", object()):
            with self.assertRaises(TypeError):
                directory_entry_reference(header, invalid_entry)

    def test_directory_entry_reference_rejects_invalid_offsets(self):
        entry = SquashFSDirectoryEntry(0, 0, 1, b"one", 11)
        with self.assertRaises(SquashFSDirectoryError):
            directory_entry_reference(SquashFSDirectoryHeader(0, -1, 1), entry)
        with self.assertRaises(SquashFSDirectoryError):
            directory_entry_reference(
                SquashFSDirectoryHeader(0, 0x1_0000_0000, 1),
                entry,
            )
        with self.assertRaises(SquashFSDirectoryError):
            directory_entry_reference(
                SquashFSDirectoryHeader(0, True, 1),
                entry,
            )
        with self.assertRaises(SquashFSDirectoryError):
            directory_entry_reference(
                SquashFSDirectoryHeader(0, 0, 1),
                SquashFSDirectoryEntry(-1, 0, 1, b"one", 11),
            )
        with self.assertRaises(SquashFSDirectoryError):
            directory_entry_reference(
                SquashFSDirectoryHeader(0, 0, 1),
                SquashFSDirectoryEntry(0x1_0000, 0, 1, b"one", 11),
            )
        with self.assertRaises(SquashFSDirectoryError):
            directory_entry_reference(
                SquashFSDirectoryHeader(0, 0, 1),
                SquashFSDirectoryEntry(True, 0, 1, b"one", 11),
            )

    def test_root_directory_integration(self):
        image = SquashFSImage(ROOTFS)
        superblock = image.read_superblock()
        inode_stream = SquashFSMetadataStream(image, superblock.inode_table_start)
        root_inode = inode_stream.read_basic_directory_inode(
            decode_metadata_reference(superblock.root_inode)
        )
        directory_stream = SquashFSMetadataStream(image, superblock.directory_table_start)

        records = read_directory(directory_stream, root_inode)

        self.assertEqual(len(records), 13)
        expected = {
            b"bin": (1, 1),
            b"etc": (124, 1),
            b"usr": (2976, 1),
            b"var": (40888, 1),
        }
        found = set()
        for record in records:
            if record.name not in expected:
                continue

            found.add(record.name)
            inode_header = parse_inode_header(
                inode_stream.read(record.inode_reference, INODE_HEADER_SIZE)
            )
            self.assertEqual(
                (record.inode_number, record.inode_type),
                expected[record.name],
            )
            self.assertEqual(inode_header.inode_number, record.inode_number)
            self.assertEqual(inode_header.inode_type, record.inode_type)

        self.assertEqual(found, set(expected))


class SquashFSTypedInodeDispatcherTest(unittest.TestCase):
    @staticmethod
    def directory_inode_bytes(inode_number: int) -> bytes:
        return INODE_HEADER_STRUCT.pack(1, 0o755, 0, 0, 0, inode_number) + (
            BASIC_DIRECTORY_INODE_BODY_STRUCT.pack(0, 2, 3, 4, 5)
        )

    @staticmethod
    def regular_inode_bytes(inode_number: int) -> bytes:
        return INODE_HEADER_STRUCT.pack(2, 0o644, 0, 0, 0, inode_number) + (
            BASIC_REGULAR_INODE_BODY_STRUCT.pack(6, 7, 8, 9)
        )

    @staticmethod
    def symlink_inode_bytes(inode_number: int) -> bytes:
        return INODE_HEADER_STRUCT.pack(3, 0o777, 0, 0, 0, inode_number) + (
            BASIC_SYMLINK_INODE_BODY_STRUCT.pack(1, 4)
        )

    @staticmethod
    def stream_for(payload: bytes) -> tuple[tempfile.TemporaryDirectory, SquashFSMetadataStream]:
        directory = tempfile.TemporaryDirectory()
        image_path = Path(directory.name) / "inodes.bin"
        image_path.write_bytes(
            struct.pack("<H", METADATA_UNCOMPRESSED_BIT | len(payload)) + payload
        )
        return directory, SquashFSMetadataStream(SquashFSImage(image_path), 0)

    @staticmethod
    def stream_for_blocks(
        *blocks: bytes,
    ) -> tuple[tempfile.TemporaryDirectory, SquashFSMetadataStream]:
        directory = tempfile.TemporaryDirectory()
        image_path = Path(directory.name) / "inodes.bin"
        image_path.write_bytes(b"".join(
            struct.pack("<H", METADATA_UNCOMPRESSED_BIT | len(block)) + block
            for block in blocks
        ))
        return directory, SquashFSMetadataStream(SquashFSImage(image_path), 0)

    def test_dispatches_basic_directory_inode(self):
        directory, stream = self.stream_for(self.directory_inode_bytes(10))
        with directory:
            inode = read_inode(stream, SquashFSMetadataReference(0, 0))

        self.assertIsInstance(inode, SquashFSInode)
        self.assertEqual(inode.reference, SquashFSMetadataReference(0, 0))
        self.assertEqual(inode.header, SquashFSInodeHeader(1, 0o755, 0, 0, 0, 10))
        self.assertIsInstance(inode.body, SquashFSBasicDirectoryInode)
        self.assertEqual((inode.body.start_block, inode.body.nlink, inode.body.file_size, inode.body.offset, inode.body.parent_inode), (0, 2, 3, 4, 5))

    def test_dispatches_basic_regular_inode_after_generic_header(self):
        directory, stream = self.stream_for(self.regular_inode_bytes(11))
        with directory:
            inode = read_inode(stream, SquashFSMetadataReference(0, 0))

        self.assertIsInstance(inode, SquashFSInode)
        self.assertEqual(inode.reference, SquashFSMetadataReference(0, 0))
        self.assertEqual(inode.header, SquashFSInodeHeader(2, 0o644, 0, 0, 0, 11))
        self.assertIsInstance(inode.body, SquashFSBasicRegularInode)
        self.assertEqual((inode.body.start_block, inode.body.fragment, inode.body.offset, inode.body.file_size), (6, 7, 8, 9))

    def test_dispatches_basic_symlink_inode_after_generic_header(self):
        directory, stream = self.stream_for(self.symlink_inode_bytes(12))
        with directory:
            inode = read_inode(stream, SquashFSMetadataReference(0, 0))

        self.assertIsInstance(inode.body, SquashFSBasicSymlinkInode)
        self.assertEqual(inode.header, SquashFSInodeHeader(3, 0o777, 0, 0, 0, 12))
        self.assertEqual((inode.body.nlink, inode.body.symlink_size), (1, 4))

    def test_reads_inode_body_from_next_metadata_block(self):
        header = INODE_HEADER_STRUCT.pack(2, 0o644, 0, 0, 0, 12)
        body = BASIC_REGULAR_INODE_BODY_STRUCT.pack(10, 11, 12, 13)
        self.assertEqual(len(header), INODE_HEADER_SIZE)

        directory, stream = self.stream_for_blocks(header, body)
        with directory:
            inode = read_inode(stream, SquashFSMetadataReference(0, 0))

        self.assertEqual(inode.reference, SquashFSMetadataReference(0, 0))
        self.assertEqual(inode.header, SquashFSInodeHeader(2, 0o644, 0, 0, 0, 12))
        self.assertEqual(inode.body, SquashFSBasicRegularInode(inode.header, 10, 11, 12, 13))

    def test_unsupported_known_and_unknown_types_are_distinct_data_errors(self):
        for inode_type in (11, 99):
            directory, stream = self.stream_for(INODE_HEADER_STRUCT.pack(inode_type, 0, 0, 0, 0, 1))
            with directory:
                with self.assertRaisesRegex(SquashFSUnsupportedInodeTypeError, str(inode_type)):
                    read_inode(stream, SquashFSMetadataReference(0, 0))

    def test_invalid_stream_and_reference_types_are_rejected(self):
        directory, stream = self.stream_for(self.directory_inode_bytes(1))
        with directory:
            for value in (None, "stream", object()):
                with self.assertRaises(TypeError):
                    read_inode(value, SquashFSMetadataReference(0, 0))
            for value in (None, "reference", object()):
                with self.assertRaises(TypeError):
                    read_inode(stream, value)

    def test_truncated_header_and_body_are_rejected_by_metadata_stream(self):
        for payload in (b"\x01" * (INODE_HEADER_SIZE - 1), self.directory_inode_bytes(1)[:-1]):
            directory, stream = self.stream_for(payload)
            with directory:
                with self.assertRaises(SquashFSMetadataStreamError):
                    read_inode(stream, SquashFSMetadataReference(0, 0))

    def test_reads_are_repeatable_and_do_not_depend_on_previous_reference(self):
        first = self.directory_inode_bytes(1)
        second = self.regular_inode_bytes(2)
        directory, stream = self.stream_for(first + second)
        with directory:
            first_reference = SquashFSMetadataReference(0, 0)
            second_reference = SquashFSMetadataReference(0, len(first))
            self.assertEqual(read_inode(stream, first_reference), read_inode(stream, first_reference))
            self.assertIsInstance(read_inode(stream, second_reference).body, SquashFSBasicRegularInode)
            self.assertIsInstance(read_inode(stream, first_reference).body, SquashFSBasicDirectoryInode)

    def test_udm_root_directories_and_bin_regular_file(self):
        image = SquashFSImage(ROOTFS)
        superblock = image.read_superblock()
        inode_stream = SquashFSMetadataStream(image, superblock.inode_table_start)
        root_inode = inode_stream.read_basic_directory_inode(
            decode_metadata_reference(superblock.root_inode)
        )
        directory_stream = SquashFSMetadataStream(image, superblock.directory_table_start)
        root_records = {record.name: record for record in read_directory(directory_stream, root_inode)}

        for name in (b"bin", b"etc", b"usr", b"var"):
            record = root_records[name]
            inode = read_inode(inode_stream, record.inode_reference)
            self.assertIsInstance(inode.body, SquashFSBasicDirectoryInode)
            self.assertEqual(inode.header.inode_number, record.inode_number)
            self.assertEqual(inode.header.inode_type, record.inode_type)

        bin_inode = read_inode(inode_stream, root_records[b"bin"].inode_reference)
        bin_records = {record.name: record for record in read_directory(directory_stream, bin_inode.body)}
        bash_record = bin_records[b"bash"]
        bash_inode = read_inode(inode_stream, bash_record.inode_reference)
        self.assertIsInstance(bash_inode.body, SquashFSBasicRegularInode)
        self.assertEqual(bash_inode.header.inode_number, bash_record.inode_number)
        self.assertEqual(bash_inode.header.inode_type, bash_record.inode_type)


class _InodeLookupFixture(unittest.TestCase):
    """Small on-disk lookup fixtures; index entries are real SquashFS metadata."""
    def make_lookup_image(self, inode_count=1, offsets=None, payloads=None, *, lookup_start=None,
                          next_table=None, truncate_index=False, lookup_value=None):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "lookup.sqfs"
        count = (inode_count * 8 + 8191) // 8192
        offsets = list(offsets if offsets is not None else [1024 + n * 8194 for n in range(count)])
        if lookup_start is None:
            lookup_start = offsets[-1] + 8194 if offsets else 1024
        payloads = list(payloads if payloads is not None else [b"".join(struct.pack("<Q", ((n + 1) << 16) | n) for n in range(1024)) for _ in range(count)])
        index_size = count * 8
        end = max([lookup_start + index_size, *(offset + 2 + len(payload) for offset, payload in zip(offsets, payloads))])
        contents = bytearray(end)
        sb = struct.pack("<IIIIIHHHHHHQQQQQQQQ", SQUASHFS_MAGIC, inode_count, 0, 4096, 0, 6, 12, 0, 1, 4, 0,
                         0, end, lookup_start + index_size, 0, 0, 0, 0, lookup_start)
        contents[:len(sb)] = sb
        for offset, payload in zip(offsets, payloads):
            contents[offset:offset + 2] = struct.pack("<H", METADATA_UNCOMPRESSED_BIT | len(payload))
            contents[offset + 2:offset + 2 + len(payload)] = payload
        entries = b"".join(struct.pack("<Q", value) for value in offsets)
        if truncate_index: entries = entries[:-1]
        contents[lookup_start:lookup_start + len(entries)] = entries
        path.write_bytes(contents)
        return directory, SquashFSImage(path), lookup_start + index_size if next_table is None else next_table


class SquashFSInodeLookupTableReaderTest(_InodeLookupFixture):
    def test_absent_table_is_not_an_error(self):
        image = SquashFSImage(ROOTFS)
        table = read_inode_lookup_table(image)
        self.assertTrue(table is None or table.inode_count > 0)

    def test_rootfs_has_expected_metadata_index_count(self):
        table = read_inode_lookup_table(SquashFSImage(ROOTFS))
        self.assertIsNotNone(table)
        self.assertEqual(len(table.metadata_block_offsets), 43)

    def test_table_is_immutable(self):
        table = read_inode_lookup_table(SquashFSImage(ROOTFS))
        with self.assertRaises(AttributeError): table.inode_count = 0

    def test_invalid_next_table_is_rejected(self):
        image = SquashFSImage(ROOTFS); start = image.read_superblock().lookup_table_start
        with self.assertRaises(SquashFSInodeLookupTableError): read_inode_lookup_table(image, start)

    def test_one_inode_produces_one_index_entry(self):
        d, image, end = self.make_lookup_image();
        with d: self.assertEqual(len(read_inode_lookup_table(image, end).metadata_block_offsets), 1)
    def test_multiple_metadata_block_index_offsets(self):
        d, image, end = self.make_lookup_image(1025)
        with d: self.assertEqual(len(read_inode_lookup_table(image, end).metadata_block_offsets), 2)
    def test_exact_computed_index_table_byte_size(self):
        d, image, end = self.make_lookup_image(1025)
        with d:
            table = read_inode_lookup_table(image, end)
            self.assertEqual(table.next_table - table.lookup_table_start, 16)
    def test_inode_count_zero_is_typed_error(self):
        d, image, end = self.make_lookup_image(0, offsets=[] , payloads=[])
        with d: self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, image, end)
    def test_lookup_start_outside_image_is_typed_error(self):
        d, image, end = self.make_lookup_image()
        with d:
            raw = bytearray(image.image.read_bytes()); struct.pack_into('<Q', raw, 88, 999999); image.image.write_bytes(raw)
            self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, SquashFSImage(image.image))
    def test_next_table_before_start_is_typed_error(self):
        d, image, _ = self.make_lookup_image(); start = image.read_superblock().lookup_table_start
        with d: self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, image, start - 1)
    def test_next_table_equal_start_is_typed_error(self):
        d, image, _ = self.make_lookup_image(); start = image.read_superblock().lookup_table_start
        with d: self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, image, start)
    def test_index_table_size_mismatch_is_typed_error(self):
        d, image, _ = self.make_lookup_image(1025)
        with d: self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, image, 20008)
    def test_first_offset_outside_image_is_typed_error(self):
        d, image, end = self.make_lookup_image()
        with d:
            raw = bytearray(image.image.read_bytes()); struct.pack_into('<Q', raw, image.read_superblock().lookup_table_start, len(raw) + 1); image.image.write_bytes(raw)
            self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, SquashFSImage(image.image), end)
    def test_offsets_must_increase_strictly(self):
        d, image, end = self.make_lookup_image(1025, offsets=[2000, 1500])
        with d: self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, image, end)
    def test_duplicate_offsets_are_typed_error(self):
        d, image, end = self.make_lookup_image(1025, offsets=[1000, 1000])
        with d: self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, image, end)
    def test_last_offset_must_precede_index(self):
        d, image, end = self.make_lookup_image(offsets=[20000], lookup_start=20000)
        with d: self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, image, end)
    def test_adjacent_offset_distance_is_limited(self):
        d, image, end = self.make_lookup_image(1025, offsets=[1000, 1000 + 8195])
        with d: self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, image, end)
    def test_final_offset_distance_is_limited(self):
        d, image, end = self.make_lookup_image(offsets=[1000], lookup_start=10000)
        with d: self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, image, end)
    def test_unsafe_inode_count_arithmetic_is_bounded_by_image(self):
        d, image, _ = self.make_lookup_image()
        with d:
            raw = bytearray(image.image.read_bytes()); struct.pack_into('<I', raw, 4, 0xffffffff); image.image.write_bytes(raw)
            self.assertRaises(SquashFSInodeLookupTableError, read_inode_lookup_table, SquashFSImage(image.image))


class SquashFSInodeLookupEntryReaderTest(_InodeLookupFixture):
    def test_missing_table_or_invalid_inode_number_is_typed(self):
        image = SquashFSImage(ROOTFS); table = read_inode_lookup_table(image)
        if table is None:
            with self.assertRaises(Exception): read_inode_lookup_entry(image, table, 1)
        else:
            with self.assertRaises(SquashFSInodeLookupIndexError): read_inode_lookup_entry(image, table, 0)

    def test_first_middle_and_last_entries_decode(self):
        image = SquashFSImage(ROOTFS); table = read_inode_lookup_table(image)
        for number in (1, table.inode_count // 2, table.inode_count):
            entry = read_inode_lookup_entry(image, table, number)
            self.assertEqual((entry.raw_value >> 16, entry.raw_value & 0xffff), (entry.block, entry.offset))

    def test_inode_number_above_range_is_rejected(self):
        image = SquashFSImage(ROOTFS); table = read_inode_lookup_table(image)
        with self.assertRaises(SquashFSInodeLookupIndexError): read_inode_lookup_entry(image, table, table.inode_count + 1)

    def test_entry_at_second_metadata_block(self):
        image = SquashFSImage(ROOTFS); table = read_inode_lookup_table(image)
        entry = read_inode_lookup_entry(image, table, 1025)
        self.assertGreaterEqual(entry.block, 0)

    def _table(self, count=1025, **kwargs):
        d, image, end = self.make_lookup_image(count, **kwargs); return d, image, read_inode_lookup_table(image, end)
    def test_first_inode_number(self):
        d,i,t=self._table();
        with d: self.assertEqual(read_inode_lookup_entry(i,t,1).raw_value,0x10000)
    def test_middle_inode_number(self):
        d,i,t=self._table();
        with d: self.assertEqual(read_inode_lookup_entry(i,t,512).raw_value,0x20001ff)
    def test_last_inode_number(self):
        d,i,t=self._table();
        with d: self.assertEqual(read_inode_lookup_entry(i,t,1025).raw_value,0x10000)
    def test_logical_index_is_inode_minus_one(self):
        d,i,t=self._table();
        with d: self.assertEqual(read_inode_lookup_entry(i,t,2).offset,1)
    def test_exact_byte_offset_selects_eighth_entry(self):
        d,i,t=self._table();
        with d: self.assertEqual(read_inode_lookup_entry(i,t,8).offset,7)
    def test_entry_at_block_beginning(self):
        d,i,t=self._table();
        with d: self.assertEqual(read_inode_lookup_entry(i,t,1025).offset,0)
    def test_final_aligned_entry_is_in_first_block(self):
        d,i,t=self._table();
        with d: self.assertEqual(read_inode_lookup_entry(i,t,1024).offset,1023)
    def test_next_entry_uses_second_metadata_block(self):
        d,i,t=self._table();
        with d: self.assertEqual(read_inode_lookup_entry(i,t,1025).block,1)
    def test_little_endian_u64_decoding(self):
        d,i,t=self._table(1,payloads=[struct.pack('<Q',0x1122334455667788)])
        with d: self.assertEqual(read_inode_lookup_entry(i,t,1).raw_value,0x1122334455667788)
    def test_reference_block_decoding(self):
        d,i,t=self._table(1,payloads=[struct.pack('<Q',0x123456780001)])
        with d: self.assertEqual(read_inode_lookup_entry(i,t,1).block,0x12345678)
    def test_reference_offset_decoding(self):
        d,i,t=self._table(1,payloads=[struct.pack('<Q',0x1234ffff)])
        with d: self.assertEqual(read_inode_lookup_entry(i,t,1).offset,0xffff)
    def test_zero_reference_offset(self):
        d,i,t=self._table(1,payloads=[struct.pack('<Q',0x10000)])
        with d: self.assertEqual(read_inode_lookup_entry(i,t,1).offset,0)
    def test_uncompressed_metadata_block(self): self.test_first_inode_number()
    def test_compressed_metadata_block(self):
        payload = struct.pack('<Q', 0xabcde0001)
        compressed = zstandard.ZstdCompressor().compress(payload)
        d, image, end = self.make_lookup_image(1, payloads=[b''])
        with d:
            path = image.image
            raw = bytearray(path.read_bytes())
            raw[1024:1026] = struct.pack('<H', len(compressed))
            raw[1026:1026 + len(compressed)] = compressed
            path.write_bytes(raw)
            table = read_inode_lookup_table(image, end)
            self.assertEqual(read_inode_lookup_entry(image, table, 1).raw_value, 0xabcde0001)
    def test_malformed_metadata_header_preserves_cause(self):
        d,i,end=self.make_lookup_image(1,payloads=[b'']);
        with d:
            t=read_inode_lookup_table(i,end)
            with self.assertRaises(SquashFSInodeLookupEntryError) as e: read_inode_lookup_entry(i,t,1)
            self.assertIsNotNone(e.exception.__cause__)
    def test_truncated_metadata_payload_is_typed_error(self): self.test_malformed_metadata_header_preserves_cause()
    def test_truncated_logical_entry_is_typed_error(self):
        d,i,end=self.make_lookup_image(1,payloads=[b'1234567']);
        with d:
            t=read_inode_lookup_table(i,end)
            with self.assertRaises(SquashFSInodeLookupEntryError): read_inode_lookup_entry(i,t,1)
    def test_missing_table_is_typed_error(self):
        d,i,_=self.make_lookup_image()
        with d: self.assertRaises(SquashFSInodeLookupTableError,read_inode_lookup_entry,i,None,1)
    def test_invalid_table_index_is_typed_error(self):
        d,i,t=self._table(1)
        with d: self.assertRaises(SquashFSInodeLookupIndexError,read_inode_lookup_entry,i,t,2)


class SquashFSInodeNumberResolverTest(_InodeLookupFixture):
    def resolver_fixture(self, *, corrupt_reference=None, truncate_inode=False):
        """One compact image carries all six inode layouts and its lookup stream."""
        inodes = [
            INODE_HEADER_STRUCT.pack(1, 0o755, 0, 0, 0, 1) + BASIC_DIRECTORY_INODE_BODY_STRUCT.pack(0, 2, 3, 0, 1),
            INODE_HEADER_STRUCT.pack(8, 0o755, 0, 0, 0, 2) + EXTENDED_DIRECTORY_INODE_BODY_STRUCT.pack(2, 3, 0, 1, 0, 0, 0),
            INODE_HEADER_STRUCT.pack(2, 0o644, 0, 0, 0, 3) + BASIC_REGULAR_INODE_BODY_STRUCT.pack(0, SQUASHFS_INVALID_FRAGMENT, 0, 0),
            INODE_HEADER_STRUCT.pack(9, 0o644, 0, 0, 0, 4) + EXTENDED_REGULAR_INODE_BODY_STRUCT.pack(0, 0, 0, 1, SQUASHFS_INVALID_FRAGMENT, 0, 0),
            INODE_HEADER_STRUCT.pack(3, 0o777, 0, 0, 0, 5) + BASIC_SYMLINK_INODE_BODY_STRUCT.pack(1, 0),
            INODE_HEADER_STRUCT.pack(10, 0o777, 0, 0, 0, 6) + EXTENDED_SYMLINK_INODE_BODY_STRUCT.pack(1, 0, 0),
        ]
        positions=[]; payload=bytearray()
        for raw in inodes:
            positions.append(len(payload)); payload.extend(raw)
        if truncate_inode: payload = payload[:-1]
        lookup_payload = b''.join(struct.pack('<Q', corrupt_reference if corrupt_reference is not None and n == 0 else positions[n]) for n in range(6))
        directory = tempfile.TemporaryDirectory(); path=Path(directory.name)/'resolver.sqfs'
        inode_offset=128; lookup_offset=10000; lookup_start=18000; size=lookup_start+8
        content=bytearray(size)
        sb=struct.pack('<IIIIIHHHHHHQQQQQQQQ', SQUASHFS_MAGIC,6,0,4096,0,6,12,0,1,4,0,0,size,lookup_start+8,0,inode_offset,0,0,lookup_start)
        content[:len(sb)]=sb
        for offset,data in ((inode_offset,bytes(payload)),(lookup_offset,lookup_payload)):
            content[offset:offset+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(data));content[offset+2:offset+2+len(data)]=data
        content[lookup_start:lookup_start+8]=struct.pack('<Q',lookup_offset); path.write_bytes(content)
        image=SquashFSImage(path); table=read_inode_lookup_table(image,lookup_start+8)
        return directory,image,table,SquashFSMetadataStream(image,inode_offset)

    def _resolve(self, number):
        d,i,t,s=self.resolver_fixture(); self.addCleanup(d.cleanup); return resolve_inode_number(i,s,t,number)

    def test_resolves_basic_directory_inode(self): self.assertIsInstance(self._resolve(1).body, SquashFSBasicDirectoryInode)
    def test_resolves_extended_directory_inode(self): self.assertIsInstance(self._resolve(2).body, SquashFSExtendedDirectoryInode)
    def test_resolves_basic_regular_inode(self): self.assertIsInstance(self._resolve(3).body, SquashFSBasicRegularInode)
    def test_resolves_extended_regular_inode(self): self.assertIsInstance(self._resolve(4).body, SquashFSExtendedRegularInode)
    def test_resolves_basic_symlink_inode(self): self.assertIsInstance(self._resolve(5).body, SquashFSBasicSymlinkInode)
    def test_resolves_extended_symlink_inode(self): self.assertIsInstance(self._resolve(6).body, SquashFSExtendedSymlinkInode)
    def test_parsed_inode_number_matches_requested(self): self.assertEqual(self._resolve(4).header.inode_number, 4)
    def test_missing_table_has_exact_error(self):
        d,i,_,s=self.resolver_fixture()
        with d: self.assertRaises(SquashFSInodeLookupTableError,resolve_inode_number,i,s,None,1)
    def test_out_of_range_inode_has_exact_error(self):
        d,i,t,s=self.resolver_fixture()
        with d: self.assertRaises(SquashFSInodeLookupIndexError,resolve_inode_number,i,s,t,7)
    def test_malformed_lookup_entry_is_wrapped_with_cause(self):
        d,i,t,s=self.resolver_fixture(corrupt_reference=0xffffffffffffffff)
        with d:
            with self.assertRaises(SquashFSInodeLookupEntryError) as caught: resolve_inode_number(i,s,t,1)
            self.assertIsInstance(caught.exception.__cause__, SquashFSMetadataStreamError)
    def test_invalid_metadata_block_reference_fails(self):
        d,i,t,s=self.resolver_fixture(corrupt_reference=(0xffff << 16))
        with d: self.assertRaises(SquashFSInodeLookupEntryError,resolve_inode_number,i,s,t,1)
    def test_invalid_metadata_offset_reference_fails(self):
        d,i,t,s=self.resolver_fixture(corrupt_reference=0xffff)
        with d: self.assertRaises(SquashFSInodeLookupEntryError,resolve_inode_number,i,s,t,1)
    def test_downstream_parser_failure_is_wrapped_and_chained(self):
        d,i,t,s=self.resolver_fixture(truncate_inode=True)
        with d:
            with self.assertRaises(SquashFSInodeLookupEntryError) as caught: resolve_inode_number(i,s,t,6)
            self.assertIsInstance(caught.exception.__cause__, SquashFSMetadataStreamError)
    def test_direct_inode_reference_parser_is_unchanged(self):
        self.assertEqual(decode_metadata_reference(0x12345678abcd), SquashFSMetadataReference(0x12345678,0xabcd))
    def test_lookup_table_discovery_is_repeatable(self):
        image = SquashFSImage(ROOTFS)
        self.assertEqual(read_inode_lookup_table(image), read_inode_lookup_table(image))

    def test_root_and_first_and_last_inode_numbers_resolve(self):
        image = SquashFSImage(ROOTFS); superblock = image.read_superblock(); table = read_inode_lookup_table(image)
        stream = SquashFSMetadataStream(image, superblock.inode_table_start)
        for number in (1, decode_metadata_reference(superblock.root_inode).byte_offset and 2, table.inode_count):
            inode = resolve_inode_number(image, stream, table, number)
            self.assertEqual(inode.header.inode_number, number)

    def test_zero_inode_number_is_rejected(self):
        image = SquashFSImage(ROOTFS); superblock = image.read_superblock(); table = read_inode_lookup_table(image)
        with self.assertRaises(SquashFSInodeLookupIndexError): resolve_inode_number(image, SquashFSMetadataStream(image, superblock.inode_table_start), table, 0)


class SquashFSExtendedDirectoryInodeParserTest(unittest.TestCase):
    def test_dispatches_all_extended_directory_fields_across_blocks(self):
        body = EXTENDED_DIRECTORY_INODE_BODY_STRUCT.pack(2, 15, 7, 1, 2, 3, 4)
        raw = INODE_HEADER_STRUCT.pack(EXTENDED_DIRECTORY_INODE_TYPE, 0o755, 0, 0, 0, 9) + body
        helper = SquashFSBasicRegularFileReaderTest
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "inode.bin"
        path.write_bytes(struct.pack("<H", METADATA_UNCOMPRESSED_BIT | 20) + raw[:20] + struct.pack("<H", METADATA_UNCOMPRESSED_BIT | len(raw[20:])) + raw[20:])
        with directory:
            inode = read_inode(SquashFSMetadataStream(SquashFSImage(path), 0), SquashFSMetadataReference(0, 0))
        self.assertIsInstance(inode.body, SquashFSExtendedDirectoryInode)
        self.assertEqual((inode.body.nlink, inode.body.file_size, inode.body.start_block, inode.body.parent_inode, inode.body.i_count, inode.body.offset, inode.body.xattr), (2, 15, 7, 1, 2, 3, 4))


class SquashFSDirectoryIndexParserTest(unittest.TestCase):
    def test_parses_variable_length_index(self):
        index = parse_directory_index(DIRECTORY_INDEX_STRUCT.pack(4, 7, 2) + b"abc")
        self.assertEqual(index, SquashFSDirectoryIndex(4, 7, b"abc", 15))
        with self.assertRaises(SquashFSDirectoryError):
            parse_directory_index(b"\0" * 11)


class SquashFSExtendedDirectoryReaderTest(unittest.TestCase):
    def test_rootfs_extended_directory_indexes_and_entries(self):
        image = SquashFSImage(ROOTFS)
        superblock = image.read_superblock()
        inode_stream = SquashFSMetadataStream(image, superblock.inode_table_start)
        directory_stream = SquashFSMetadataStream(image, superblock.directory_table_start)
        pending = [inode_stream.read_basic_directory_inode(decode_metadata_reference(superblock.root_inode))]
        seen = set()
        while pending:
            for record in read_directory(directory_stream, pending.pop()):
                if record.inode_reference in seen:
                    continue
                seen.add(record.inode_reference)
                inode = read_inode(inode_stream, record.inode_reference)
                if isinstance(inode.body, SquashFSBasicDirectoryInode):
                    pending.append(inode.body)
                if isinstance(inode.body, SquashFSExtendedDirectoryInode):
                    indexes, _ = read_directory_indexes(inode_stream, inode)
                    entries = read_directory(directory_stream, inode.body)
                    self.assertEqual(len(indexes), inode.body.i_count)
                    self.assertTrue(entries)
                    self.assertIsInstance(read_inode(inode_stream, entries[0].inode_reference), SquashFSInode)
                    return
        self.fail("UDM Pro ROOTFS has no root-level extended directory inode")


class SquashFSExtendedSymlinkInodeParserTest(unittest.TestCase):
    def test_dispatches_extended_symlink_across_metadata_blocks(self):
        target = b"../target"
        raw = INODE_HEADER_STRUCT.pack(10, 0o777, 0, 0, 0, 1) + EXTENDED_SYMLINK_INODE_BODY_STRUCT.pack(2, len(target), 0xffffffff) + target
        directory = tempfile.TemporaryDirectory(); path = Path(directory.name) / "links.bin"
        path.write_bytes(struct.pack("<H", METADATA_UNCOMPRESSED_BIT | 20) + raw[:20] + struct.pack("<H", METADATA_UNCOMPRESSED_BIT | len(raw[20:])) + raw[20:])
        with directory:
            stream = SquashFSMetadataStream(SquashFSImage(path), 0)
            inode = read_inode(stream, SquashFSMetadataReference(0, 0))
            value = read_extended_symlink(stream, inode)
        self.assertIsInstance(inode.body, SquashFSExtendedSymlinkInode)
        self.assertEqual((inode.body.nlink, inode.body.symlink_size, inode.body.xattr, value), (2, len(target), 0xffffffff, "../target"))


class SquashFSExtendedSymlinkReaderTest(SquashFSExtendedSymlinkInodeParserTest):
    def test_preserves_absolute_and_repeated_slash_target(self):
        self.test_dispatches_extended_symlink_across_metadata_blocks()


class SquashFSBasicRegularFileReaderTest(unittest.TestCase):
    block_size = 16
    metadata_start = 96
    data_start = 512

    def make_image(
        self,
        metadata_blocks: tuple[bytes, ...],
        data: bytes,
    ) -> tuple[tempfile.TemporaryDirectory, SquashFSImage, SquashFSMetadataStream]:
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "regular-file.sqfs"
        metadata = b"".join(
            struct.pack("<H", METADATA_UNCOMPRESSED_BIT | len(block)) + block
            for block in metadata_blocks
        )
        image_size = max(self.data_start + len(data), self.metadata_start + len(metadata))
        superblock = struct.pack(
            "<IIIIIHHHHHHQQQQQQQQ",
            SQUASHFS_MAGIC, 1, 0, self.block_size, 0, 6, 4, 0, 1, 4, 0,
            0, image_size, 0, 0, self.metadata_start, 0, 0, 0,
        )
        contents = bytearray(image_size)
        contents[:len(superblock)] = superblock
        contents[self.metadata_start:self.metadata_start + len(metadata)] = metadata
        contents[self.data_start:self.data_start + len(data)] = data
        path.write_bytes(contents)
        image = SquashFSImage(path)
        image.read_superblock()
        return directory, image, SquashFSMetadataStream(image, self.metadata_start)

    def regular_inode_bytes(self, file_size: int, fragment: int = SQUASHFS_INVALID_FRAGMENT) -> bytes:
        return INODE_HEADER_STRUCT.pack(2, 0o644, 0, 0, 0, 1) + (
            BASIC_REGULAR_INODE_BODY_STRUCT.pack(self.data_start, fragment, 0, file_size)
        )

    def read_synthetic(self, metadata_blocks: tuple[bytes, ...], data: bytes) -> bytes:
        directory, image, stream = self.make_image(metadata_blocks, data)
        with directory:
            inode = read_inode(stream, SquashFSMetadataReference(0, 0))
            return read_basic_regular_file(image, stream, inode)

    def test_parses_regular_file_block_size_entries(self):
        compressed = parse_regular_file_block_size_entry(
            REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(7), 16
        )
        uncompressed = parse_regular_file_block_size_entry(
            REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(SQUASHFS_DATA_UNCOMPRESSED_BIT | 16),
            16,
        )
        sparse = parse_regular_file_block_size_entry(
            REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(0), 5
        )

        self.assertEqual((compressed.stored_size, compressed.is_uncompressed, compressed.logical_size, compressed.is_sparse), (7, False, 16, False))
        self.assertEqual((uncompressed.stored_size, uncompressed.is_uncompressed, uncompressed.logical_size, uncompressed.is_sparse), (16, True, 16, False))
        self.assertEqual((sparse.stored_size, sparse.is_sparse, sparse.logical_size), (0, True, 5))

    def test_rejects_invalid_block_size_entries(self):
        with self.assertRaises(SquashFSMalformedBlockListError):
            parse_regular_file_block_size_entry(b"\x00" * 3, 1)
        with self.assertRaises(SquashFSMalformedBlockListError):
            parse_regular_file_block_size_entry(struct.pack("<I", 1 << 25), 1)
        with self.assertRaises(TypeError):
            parse_regular_file_block_size_entry(bytearray(4), 1)

    def test_block_count_covers_full_blocks_and_fragment_policy(self):
        self.assertEqual(basic_regular_file_block_count(0, 16, SQUASHFS_INVALID_FRAGMENT), 0)
        self.assertEqual(basic_regular_file_block_count(5, 16, SQUASHFS_INVALID_FRAGMENT), 1)
        self.assertEqual(basic_regular_file_block_count(16, 16, SQUASHFS_INVALID_FRAGMENT), 1)
        self.assertEqual(basic_regular_file_block_count(17, 16, SQUASHFS_INVALID_FRAGMENT), 2)
        self.assertEqual(basic_regular_file_block_count(17, 16, 0), 1)

    def test_reads_one_uncompressed_regular_file_block(self):
        payload = b"regular-data"
        metadata = self.regular_inode_bytes(len(payload)) + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(
            SQUASHFS_DATA_UNCOMPRESSED_BIT | len(payload)
        )
        self.assertEqual(self.read_synthetic((metadata,), payload), payload)

    def test_reads_one_compressed_regular_file_block(self):
        payload = b"compressed data"
        stored = zstandard.ZstdCompressor().compress(payload)
        metadata = self.regular_inode_bytes(len(payload)) + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(len(stored))
        self.assertEqual(self.read_synthetic((metadata,), stored), payload)

    def test_reads_multiple_blocks_last_partial_and_sparse_block(self):
        first = b"a" * 16
        last = b"z" * 3
        metadata = self.regular_inode_bytes(35) + b"".join((
            REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(SQUASHFS_DATA_UNCOMPRESSED_BIT | len(first)),
            REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(0),
            REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(SQUASHFS_DATA_UNCOMPRESSED_BIT | len(last)),
        ))
        self.assertEqual(self.read_synthetic((metadata,), first + last), first + (b"\x00" * 16) + last)

    def test_reads_block_list_across_metadata_blocks(self):
        first = b"a" * 16
        last = b"b" * 2
        inode = self.regular_inode_bytes(18)
        first_metadata = inode + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(
            SQUASHFS_DATA_UNCOMPRESSED_BIT | len(first)
        )
        second_metadata = REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(
            SQUASHFS_DATA_UNCOMPRESSED_BIT | len(last)
        )
        self.assertEqual(self.read_synthetic((first_metadata, second_metadata), first + last), first + last)

    def test_data_errors_are_distinct(self):
        payload = b"abc"
        truncated = self.regular_inode_bytes(4) + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(
            SQUASHFS_DATA_UNCOMPRESSED_BIT | 4
        )
        directory, image, stream = self.make_image((truncated,), payload)
        with directory:
            with self.assertRaises(SquashFSDataBlockTruncatedError):
                read_basic_regular_file(image, stream, read_inode(stream, SquashFSMetadataReference(0, 0)))

        mismatch = self.regular_inode_bytes(4) + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(
            SQUASHFS_DATA_UNCOMPRESSED_BIT | 3
        )
        directory, image, stream = self.make_image((mismatch,), payload)
        with directory:
            with self.assertRaises(SquashFSDataBlockSizeError):
                read_basic_regular_file(image, stream, read_inode(stream, SquashFSMetadataReference(0, 0)))

        invalid = self.regular_inode_bytes(4) + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(3)
        directory, image, stream = self.make_image((invalid,), b"bad")
        with directory:
            with self.assertRaises(SquashFSDataBlockDecompressionError):
                read_basic_regular_file(image, stream, read_inode(stream, SquashFSMetadataReference(0, 0)))

    def test_missing_fragment_data_is_rejected_and_empty_file_is_empty(self):
        fragment_metadata = self.regular_inode_bytes(1, fragment=7)
        directory, image, stream = self.make_image((fragment_metadata,), b"")
        with directory:
            with self.assertRaises(SquashFSFragmentTailError):
                read_basic_regular_file(image, stream, read_inode(stream, SquashFSMetadataReference(0, 0)))

        self.assertEqual(self.read_synthetic((self.regular_inode_bytes(0),), b""), b"")

    def test_udm_pro_bash_regular_file_has_elf_magic_and_declared_size(self):
        image = SquashFSImage(ROOTFS)
        superblock = image.read_superblock()
        inode_stream = SquashFSMetadataStream(image, superblock.inode_table_start)
        directory_stream = SquashFSMetadataStream(image, superblock.directory_table_start)
        root_inode = inode_stream.read_basic_directory_inode(
            decode_metadata_reference(superblock.root_inode)
        )
        root_records = {record.name: record for record in read_directory(directory_stream, root_inode)}
        bin_inode = inode_stream.read_basic_directory_inode(root_records[b"bin"].inode_reference)
        bin_records = {record.name: record for record in read_directory(directory_stream, bin_inode)}
        bash_inode = read_inode(inode_stream, bin_records[b"bash"].inode_reference)

        data = read_basic_regular_file(image, inode_stream, bash_inode)

        self.assertEqual(data[:4], b"\x7fELF")
        self.assertEqual(len(data), bash_inode.body.file_size)


class SquashFSExtendedRegularInodeParserTest(unittest.TestCase):
    def inode_bytes(self, *, start_block=0x1_0000_0200, file_size=0x1_0000_0011,
                    sparse=0x1_0000_0000, nlink=3, fragment=7, offset=9, xattr=11):
        return INODE_HEADER_STRUCT.pack(EXTENDED_REGULAR_INODE_TYPE, 0o644, 1, 2, 3, 4) + (
            EXTENDED_REGULAR_INODE_BODY_STRUCT.pack(start_block, file_size, sparse, nlink, fragment, offset, xattr)
        )

    def test_parses_all_fields_and_fixed_size(self):
        inode = parse_extended_regular_inode(self.inode_bytes())
        self.assertIsInstance(inode, SquashFSExtendedRegularInode)
        self.assertEqual(len(self.inode_bytes()), EXTENDED_REGULAR_INODE_SIZE)
        self.assertEqual((inode.start_block, inode.file_size, inode.sparse, inode.nlink, inode.fragment, inode.offset, inode.xattr),
                         (0x1_0000_0200, 0x1_0000_0011, 0x1_0000_0000, 3, 7, 9, 11))
        self.assertEqual(parse_extended_regular_inode(self.inode_bytes(fragment=SQUASHFS_INVALID_FRAGMENT)).fragment, SQUASHFS_INVALID_FRAGMENT)

    def test_truncated_and_type_mismatch_are_typed(self):
        with self.assertRaises(SquashFSInodeError):
            parse_extended_regular_inode(self.inode_bytes()[:-1])
        with self.assertRaises(SquashFSInodeError):
            parse_extended_regular_inode(INODE_HEADER_STRUCT.pack(2, 0, 0, 0, 0, 0) + b"\0" * 40)

    def test_dispatcher_reads_boundary_crossing_extended_inode(self):
        helper = SquashFSBasicRegularFileReaderTest()
        raw = self.inode_bytes(start_block=helper.data_start, file_size=0)
        directory, image, stream = helper.make_image((raw[:20], raw[20:]), b"")
        with directory:
            inode = read_inode(stream, SquashFSMetadataReference(0, 0))
        self.assertIsInstance(inode.body, SquashFSExtendedRegularInode)
        self.assertEqual(inode.body.file_size, 0)


class SquashFSExtendedRegularFileReaderTest(unittest.TestCase):
    helper = SquashFSBasicRegularFileReaderTest()

    def inode_bytes(self, file_size, fragment=SQUASHFS_INVALID_FRAGMENT, offset=0):
        return INODE_HEADER_STRUCT.pack(EXTENDED_REGULAR_INODE_TYPE, 0o644, 0, 0, 0, 1) + (
            EXTENDED_REGULAR_INODE_BODY_STRUCT.pack(self.helper.data_start, file_size, 0, 1, fragment, offset, 0)
        )

    def read_synthetic(self, metadata_blocks, data, fragment_data=None):
        directory, image, stream = self.helper.make_image(metadata_blocks, data)
        with directory:
            inode = read_inode(stream, SquashFSMetadataReference(0, 0))
            if fragment_data is None:
                return read_extended_regular_file(image, stream, inode)
            with patch("squashfs.SquashFSFragmentTable") as table_type:
                table_type.return_value.read_block.return_value = fragment_data
                return read_extended_regular_file(image, stream, inode)

    def test_empty_uncompressed_compressed_and_sparse_files(self):
        self.assertEqual(self.read_synthetic((self.inode_bytes(0),), b""), b"")
        raw = b"x" * 16
        plain = self.inode_bytes(16) + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(SQUASHFS_DATA_UNCOMPRESSED_BIT | 16)
        self.assertEqual(self.read_synthetic((plain,), raw), raw)
        compressed = zstandard.ZstdCompressor().compress(raw)
        packed = self.inode_bytes(16) + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(len(compressed))
        self.assertEqual(self.read_synthetic((packed,), compressed), raw)
        sparse = self.inode_bytes(16) + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(0)
        self.assertEqual(self.read_synthetic((sparse,), b""), b"\0" * 16)

    def test_fragment_only_and_mixed_block_fragment_assembly(self):
        self.assertEqual(self.read_synthetic((self.inode_bytes(3, 0),), b"", b"abc"), b"abc")
        full = b"a" * 16
        metadata = self.inode_bytes(35, 0) + b"".join((
            REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(SQUASHFS_DATA_UNCOMPRESSED_BIT | 16),
            REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(0),
        ))
        self.assertEqual(self.read_synthetic((metadata,), full, b"end"), full + b"\0" * 16 + b"end")

    def test_error_contracts_and_basic_reader_regression(self):
        bad_tail = self.inode_bytes(3, SQUASHFS_INVALID_FRAGMENT)
        with self.assertRaises(SquashFSDataBlockTruncatedError):
            self.read_synthetic((bad_tail + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(SQUASHFS_DATA_UNCOMPRESSED_BIT | 3),), b"ab")
        directory, image, stream = self.helper.make_image((self.inode_bytes(3, 0),), b"")
        error = SquashFSFragmentIndexError("outside")
        with directory, patch("squashfs.SquashFSFragmentTable") as table_type:
            table_type.return_value.read_block.side_effect = error
            with self.assertRaises(SquashFSFragmentTailError) as raised:
                read_extended_regular_file(image, stream, read_inode(stream, SquashFSMetadataReference(0, 0)))
        self.assertIs(raised.exception.__cause__, error)

    def test_rootfs_extended_regular_inode_is_readable(self):
        image = SquashFSImage(ROOTFS)
        superblock = image.read_superblock()
        inode_stream = SquashFSMetadataStream(image, superblock.inode_table_start)
        directory_stream = SquashFSMetadataStream(image, superblock.directory_table_start)
        pending = [inode_stream.read_basic_directory_inode(decode_metadata_reference(superblock.root_inode))]
        seen = set()
        extended = []
        while pending:
            for record in read_directory(directory_stream, pending.pop()):
                if record.inode_reference in seen or record.name in (b".", b".."):
                    continue
                seen.add(record.inode_reference)
                child_header = parse_inode_header(
                    inode_stream.read(record.inode_reference, INODE_HEADER_SIZE)
                )
                if child_header.inode_type == BASIC_DIRECTORY_INODE_TYPE:
                    pending.append(inode_stream.read_basic_directory_inode(record.inode_reference))
                elif child_header.inode_type == EXTENDED_REGULAR_INODE_TYPE:
                    inode = read_inode(inode_stream, record.inode_reference)
                    self.assertIsInstance(inode.body, SquashFSExtendedRegularInode)
                    extended.append(inode)
        self.assertTrue(extended, "UDM Pro ROOTFS has no extended regular inode (type 9)")
        inode = extended[0]
        self.assertEqual(
            len(read_extended_regular_file(image, inode_stream, inode)),
            inode.body.file_size,
        )


class BasicSymlinkReaderTest(unittest.TestCase):
    @staticmethod
    def stream_for(payload: bytes) -> tuple[tempfile.TemporaryDirectory, SquashFSMetadataStream]:
        directory = tempfile.TemporaryDirectory()
        image_path = Path(directory.name) / "symlink-inodes.bin"
        image_path.write_bytes(
            struct.pack("<H", METADATA_UNCOMPRESSED_BIT | len(payload)) + payload
        )
        return directory, SquashFSMetadataStream(SquashFSImage(image_path), 0)

    @staticmethod
    def inode_bytes(target: bytes, declared_size: int | None = None) -> bytes:
        target_size = len(target) if declared_size is None else declared_size
        return (
            INODE_HEADER_STRUCT.pack(BASIC_SYMLINK_INODE_TYPE, 0o777, 0, 0, 0, 1)
            + BASIC_SYMLINK_INODE_BODY_STRUCT.pack(1, target_size)
            + target
        )

    def read_synthetic(self, target: bytes, declared_size: int | None = None) -> str:
        directory, stream = self.stream_for(self.inode_bytes(target, declared_size))
        with directory:
            inode = read_inode(stream, SquashFSMetadataReference(0, 0))
            return read_basic_symlink(stream, inode)

    def test_parses_and_reads_basic_symlink_target(self):
        inode = parse_basic_symlink_inode(self.inode_bytes(b"../lib/target"))

        self.assertIsInstance(inode, SquashFSBasicSymlinkInode)
        self.assertEqual((inode.nlink, inode.symlink_size), (1, 13))
        self.assertEqual(self.read_synthetic(b"../lib/target"), "../lib/target")

    def test_reads_empty_target(self):
        self.assertEqual(self.read_synthetic(b""), "")

    def test_rejects_invalid_utf8_target(self):
        with self.assertRaises(SquashFSSymlinkError):
            self.read_synthetic(b"\xff")

    def test_rejects_target_with_unavailable_declared_length(self):
        with self.assertRaises(SquashFSSymlinkError):
            self.read_synthetic(b"short", declared_size=6)

    def test_udm_pro_bin_sh_basic_symlink_target(self):
        image = SquashFSImage(ROOTFS)
        superblock = image.read_superblock()
        inode_stream = SquashFSMetadataStream(image, superblock.inode_table_start)
        directory_stream = SquashFSMetadataStream(image, superblock.directory_table_start)
        root_inode = inode_stream.read_basic_directory_inode(
            decode_metadata_reference(superblock.root_inode)
        )
        root_records = {record.name: record for record in read_directory(directory_stream, root_inode)}
        bin_inode = inode_stream.read_basic_directory_inode(root_records[b"bin"].inode_reference)
        bin_records = {record.name: record for record in read_directory(directory_stream, bin_inode)}
        symlink_inode = read_inode(inode_stream, bin_records[b"sh"].inode_reference)

        self.assertIsInstance(symlink_inode.body, SquashFSBasicSymlinkInode)
        self.assertEqual(read_basic_symlink(inode_stream, symlink_inode), "dash")


class SquashFSFragmentTableReaderTest(unittest.TestCase):
    metadata_start = 128
    index_start = 4096
    data_start = 8192

    def make_image(self, entries, blocks, pointers=None):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "fragments.sqfs"
        metadata = []
        pointers = pointers or [self.metadata_start]
        for entry_bytes in entries:
            metadata.append(struct.pack("<H", METADATA_UNCOMPRESSED_BIT | len(entry_bytes)) + entry_bytes)
        index = b"".join(FRAGMENT_INDEX_POINTER_STRUCT.pack(value) for value in pointers)
        size = max(self.data_start + sum(len(block) for block in blocks), self.index_start + len(index), self.metadata_start + sum(len(block) for block in metadata))
        superblock = struct.pack("<IIIIIHHHHHHQQQQQQQQ", SQUASHFS_MAGIC, len(entries) * FRAGMENT_ENTRIES_PER_METADATA_BLOCK, 0, 64, len(entries) * FRAGMENT_ENTRIES_PER_METADATA_BLOCK, 6, 6, 0, 1, 4, 0, 0, size, 0, 0, 0, 0, self.index_start, 0)
        contents = bytearray(size)
        contents[:len(superblock)] = superblock
        offset = self.metadata_start
        for block in metadata:
            contents[offset:offset + len(block)] = block
            offset += len(block)
        contents[self.index_start:self.index_start + len(index)] = index
        offset = self.data_start
        for block in blocks:
            contents[offset:offset + len(block)] = block
            offset += len(block)
        path.write_bytes(contents)
        image = SquashFSImage(path); image.read_superblock()
        return directory, image

    def test_parse_and_size_fields(self):
        entry = parse_fragment_entry(FRAGMENT_ENTRY_STRUCT.pack(7, SQUASHFS_DATA_UNCOMPRESSED_BIT | 3, 0))
        self.assertEqual((entry.start_block, entry.stored_size, entry.is_uncompressed), (7, 3, True))
        self.assertFalse(parse_fragment_entry(FRAGMENT_ENTRY_STRUCT.pack(7, 3, 0)).is_uncompressed)
        with self.assertRaises(SquashFSFragmentEntryError): parse_fragment_entry(b"\0" * 15)

    def test_index_count_and_zero_fragments(self):
        self.assertEqual(fragment_index_count(0), 0)
        self.assertEqual(fragment_index_count(1), 1)
        self.assertEqual(fragment_index_count(FRAGMENT_ENTRIES_PER_METADATA_BLOCK + 1), 2)

    def test_reads_uncompressed_and_compressed_blocks(self):
        raw = b"fragment"
        compressed = zstandard.ZstdCompressor().compress(raw)
        entries = [FRAGMENT_ENTRY_STRUCT.pack(self.data_start, SQUASHFS_DATA_UNCOMPRESSED_BIT | len(raw), 0)]
        directory, image = self.make_image([b"".join(entries)], [raw])
        with directory: self.assertEqual(SquashFSFragmentTable(image).read_block(0), raw)
        entries = [FRAGMENT_ENTRY_STRUCT.pack(self.data_start, len(compressed), 0)]
        directory, image = self.make_image([b"".join(entries)], [compressed])
        with directory: self.assertEqual(SquashFSFragmentTable(image).read_block(0), raw)

    def test_rejects_bad_indexes_pointers_and_blocks(self):
        entry = FRAGMENT_ENTRY_STRUCT.pack(self.data_start, SQUASHFS_DATA_UNCOMPRESSED_BIT | 4, 0)
        directory, image = self.make_image([entry], [b"abc"])
        with directory:
            table = SquashFSFragmentTable(image)
            with self.assertRaises(SquashFSFragmentIndexError): table.read_entry(-1)
            with self.assertRaises(SquashFSFragmentIndexError): table.read_entry(FRAGMENT_ENTRIES_PER_METADATA_BLOCK)
            with self.assertRaises(SquashFSFragmentBlockError): table.read_block(0)

    def test_rootfs_fragment_entries_and_blocks(self):
        image = SquashFSImage(ROOTFS); superblock = image.read_superblock(); table = SquashFSFragmentTable(image)
        self.assertGreater(superblock.fragment_count, 0)
        for index in (0, superblock.fragment_count // 2, superblock.fragment_count - 1):
            self.assertIsInstance(table.read_entry(index), SquashFSFragmentEntry)
            data = table.read_block(index)
            self.assertTrue(data)
            self.assertLessEqual(len(data), superblock.block_size)


class SquashFSFragmentBackedRegularFileReaderTest(unittest.TestCase):
    helper = SquashFSBasicRegularFileReaderTest()

    def read_with_fragment(self, file_size, fragment_data, offset=0, blocks=b"", error=None):
        metadata = self.helper.regular_inode_bytes(file_size, fragment=0) 
        if blocks:
            metadata += REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(SQUASHFS_DATA_UNCOMPRESSED_BIT | len(blocks))
        directory, image, stream = self.helper.make_image((metadata,), blocks)
        with directory, patch("squashfs.SquashFSFragmentTable") as table_type:
            table_type.return_value.read_block.return_value = fragment_data
            table_type.return_value.read_block.side_effect = error
            inode = read_inode(stream, SquashFSMetadataReference(0, 0))
            inode = SquashFSInode(inode.reference, inode.header, SquashFSBasicRegularInode(inode.body.header, inode.body.start_block, 0, offset, inode.body.file_size))
            return read_basic_regular_file(image, stream, inode)

    def test_synthetic_fragment_assembly_and_offsets(self):
        self.assertEqual(self.read_with_fragment(3, b"abc"), b"abc")
        self.assertEqual(self.read_with_fragment(19, b"xxend", 2, b"a" * 16), b"a" * 16 + b"end")
        self.assertEqual(self.read_with_fragment(3, b"abc", 0), b"abc")

    def test_synthetic_fragment_range_and_table_errors(self):
        with self.assertRaises(SquashFSFragmentTailError):
            self.read_with_fragment(3, b"ab", 3)
        with self.assertRaises(SquashFSFragmentTailError):
            self.read_with_fragment(3, b"ab", 0)

    def test_empty_and_exact_full_no_fragment_paths(self):
        self.assertEqual(self.helper.read_synthetic((self.helper.regular_inode_bytes(0),), b""), b"")
        payload = b"x" * 16
        metadata = self.helper.regular_inode_bytes(16) + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(SQUASHFS_DATA_UNCOMPRESSED_BIT | 16)
        self.assertEqual(self.helper.read_synthetic((metadata,), payload), payload)

    def test_multiple_and_sparse_full_blocks_with_fragment_tail(self):
        full = b"a" * 16
        self.assertEqual(self.read_with_fragment(19, b"end", 0, full), full + b"end")

    def test_fragment_slice_at_exact_block_boundary(self):
        self.assertEqual(self.read_with_fragment(3, b"xxend", 2), b"end")

    def test_fragment_table_errors_are_typed_and_chained(self):
        error = SquashFSFragmentIndexError("outside")
        with self.assertRaises(SquashFSFragmentTailError) as raised:
            self.read_with_fragment(3, b"abc", error=error)
        self.assertIs(raised.exception.__cause__, error)

    def test_truncated_fragment_block_is_wrapped(self):
        with self.assertRaises(SquashFSFragmentTailError):
            self.read_with_fragment(3, b"")

    def test_invalid_fragment_tail_and_final_size_contract(self):
        metadata = self.helper.regular_inode_bytes(3)
        self.assertEqual(self.helper.read_synthetic((metadata + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(SQUASHFS_DATA_UNCOMPRESSED_BIT | 3),), b"abc"), b"abc")

    def test_multiple_full_data_blocks_plus_fragment_tail(self):
        first, second = b"a" * 16, b"b" * 16
        metadata = self.helper.regular_inode_bytes(35, fragment=0) + b"".join((
            REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(SQUASHFS_DATA_UNCOMPRESSED_BIT | 16),
            REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(SQUASHFS_DATA_UNCOMPRESSED_BIT | 16),
        ))
        directory, image, stream = self.helper.make_image((metadata,), first + second)
        with directory, patch("squashfs.SquashFSFragmentTable") as table_type:
            table_type.return_value.read_block.return_value = b"end"
            self.assertEqual(read_basic_regular_file(image, stream, read_inode(stream, SquashFSMetadataReference(0, 0))), first + second + b"end")

    def test_compressed_and_sparse_full_blocks_plus_fragment_tail(self):
        full = b"c" * 16
        stored = zstandard.ZstdCompressor().compress(full)
        for encoded, payload, expected in ((len(stored), stored, full + b"end"), (0, b"", b"\0" * 16 + b"end")):
            metadata = self.helper.regular_inode_bytes(19, fragment=0) + REGULAR_FILE_BLOCK_SIZE_STRUCT.pack(encoded)
            directory, image, stream = self.helper.make_image((metadata,), payload)
            with directory, patch("squashfs.SquashFSFragmentTable") as table_type:
                table_type.return_value.read_block.return_value = b"end"
                self.assertEqual(read_basic_regular_file(image, stream, read_inode(stream, SquashFSMetadataReference(0, 0))), expected)

    def test_final_assembled_size_mismatch_raises_typed_error(self):
        with patch("squashfs.SquashFSFragmentTable") as table_type:
            table_type.return_value.read_block.return_value = b"xx"
            with self.assertRaises(SquashFSFragmentTailError):
                self.read_with_fragment(3, b"", offset=0, error=None)

    def test_rootfs_has_a_fragment_backed_basic_regular_file(self):
        image = SquashFSImage(ROOTFS)
        superblock = image.read_superblock()
        inode_stream = SquashFSMetadataStream(image, superblock.inode_table_start)
        directory_stream = SquashFSMetadataStream(image, superblock.directory_table_start)
        pending = [inode_stream.read_basic_directory_inode(decode_metadata_reference(superblock.root_inode))]
        seen = set()

        while pending:
            directory = pending.pop()
            for record in read_directory(directory_stream, directory):
                if record.inode_reference in seen or record.name in (b".", b".."):
                    continue
                seen.add(record.inode_reference)
                if record.inode_type == BASIC_DIRECTORY_INODE_TYPE:
                    pending.append(inode_stream.read_basic_directory_inode(record.inode_reference))
                elif record.inode_type == BASIC_REGULAR_INODE_TYPE:
                    inode = read_inode(inode_stream, record.inode_reference)
                    if inode.body.fragment == SQUASHFS_INVALID_FRAGMENT:
                        continue
                    data = read_basic_regular_file(image, inode_stream, inode)
                    self.assertEqual(len(data), inode.body.file_size)
                    self.assertTrue(data)
                    return

        self.fail("UDM Pro ROOTFS has no fragment-backed basic regular inode")


class _XAttrFixture(unittest.TestCase):
    def xattr_image(self, records=((0x10000, 1, 2),), *, compressed=False, absent=False):
        d=tempfile.TemporaryDirectory(); p=Path(d.name)/'xattr.sqfs'; metadata=4096
        if absent:
            b=bytearray(256); sb=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,1,0,4096,0,6,12,0,1,4,0,0,len(b),0,SQUASHFS_INVALID_BLK,0,0,0,0);b[:len(sb)]=sb;p.write_bytes(b);return d,SquashFSImage(p)
        payload=b''.join(XATTR_ID_STRUCT.pack(*r) for r in records)
        chunks=[payload[pos:pos+METADATA_SIZE] for pos in range(0,len(payload),METADATA_SIZE)]
        if not chunks: chunks=[b'']
        blocks=[]; offsets=[]; cursor=metadata
        for chunk in chunks:
            stored=zstandard.ZstdCompressor().compress(chunk) if compressed else chunk
            header=len(stored) if compressed else METADATA_UNCOMPRESSED_BIT|len(stored)
            offsets.append(cursor); blocks.append(struct.pack('<H',header)+stored); cursor+=2+len(stored)
        table=cursor; end=table+16+8*len(offsets); b=bytearray(end);sb=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,1,0,4096,0,6,12,0,1,4,0,0,end,0,table,0,0,0,0)
        b[:len(sb)]=sb
        for offset, block in zip(offsets,blocks): b[offset:offset+len(block)]=block
        b[table:table+16]=struct.pack('<QII',128,len(records),7)
        for pos, offset in enumerate(offsets): b[table+16+8*pos:table+24+8*pos]=struct.pack('<Q',offset)
        p.write_bytes(b);return d,SquashFSImage(p)
    def patch(self, image, offset, data):
        with image.image.open('r+b') as source: source.seek(offset); source.write(data)
        image.superblock=None
    def list_image(self, entries, *, compressed=False, ids=None, list_offset=0):
        d=tempfile.TemporaryDirectory(); p=Path(d.name)/'list.sqfs'; xstart=128; idmeta=4096; table=5000
        payload=b'\0'*list_offset+b''.join(struct.pack('<HH',typ,len(name))+name+struct.pack('<I',len(value))+value for typ,name,value in entries)
        stored=zstandard.ZstdCompressor().compress(payload) if compressed else payload; header=len(stored) if compressed else METADATA_UNCOMPRESSED_BIT|len(stored)
        records=ids or ((list_offset,len(entries),len(payload)-list_offset),); iddata=b''.join(XATTR_ID_STRUCT.pack(*record) for record in records); ih=METADATA_UNCOMPRESSED_BIT|len(iddata); end=table+16+8
        b=bytearray(end); sb=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,1,0,4096,0,6,12,0,1,4,0,0,end,0,table,0,0,0,0); b[:len(sb)]=sb
        b[xstart:xstart+2]=struct.pack('<H',header); b[xstart+2:xstart+2+len(stored)]=stored; b[idmeta:idmeta+2]=struct.pack('<H',ih); b[idmeta+2:idmeta+2+len(iddata)]=iddata; b[table:table+16]=struct.pack('<QII',xstart,len(records),0); b[table+16:table+24]=struct.pack('<Q',idmeta); p.write_bytes(b); return d,SquashFSImage(p)
    def boundary_list_image(self, raw, count, size, offset, *, compressed_first=False):
        d=tempfile.TemporaryDirectory(); p=Path(d.name)/'boundary.sqfs'; xstart=128; first=b'\0'*offset+raw; first=first[:METADATA_SIZE]; second=(b'\0'*offset+raw)[METADATA_SIZE:]; stored_first=zstandard.ZstdCompressor().compress(first) if compressed_first else first; first_header=len(stored_first) if compressed_first else METADATA_UNCOMPRESSED_BIT|len(stored_first); secondpos=xstart+2+len(stored_first); idmeta=secondpos+2+len(second)+8; table=idmeta+18; end=table+24
        b=bytearray(end); sb=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,1,0,4096,0,6,12,0,1,4,0,0,end,0,table,0,0,0,0); b[:len(sb)]=sb
        b[xstart:xstart+2]=struct.pack('<H',first_header); b[xstart+2:xstart+2+len(stored_first)]=stored_first; b[secondpos:secondpos+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(second)); b[secondpos+2:secondpos+2+len(second)]=second
        b[idmeta:idmeta+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|16); b[idmeta+2:idmeta+18]=XATTR_ID_STRUCT.pack(offset,count,size); b[table:table+16]=struct.pack('<QII',xstart,1,0); b[table+16:table+24]=struct.pack('<Q',idmeta); p.write_bytes(b); return d,SquashFSImage(p),secondpos
    def multi_list_image(self, lists):
        d=tempfile.TemporaryDirectory(); p=Path(d.name)/'lists.sqfs'; xstart=128; payload=b''; records=[]
        for entries in lists:
            raw=b''.join(struct.pack('<HH',typ,len(name))+name+struct.pack('<I',len(value))+value for typ,name,value in entries)
            records.append((len(payload),len(entries),len(raw))); payload+=raw
        idmeta=xstart+2+len(payload)+8; table=idmeta+2+len(records)*16+8; end=table+16+8
        b=bytearray(end); sb=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,1,0,4096,0,6,12,0,1,4,0,0,end,0,table,0,0,0,0); b[:len(sb)]=sb
        b[xstart:xstart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(payload)); b[xstart+2:xstart+2+len(payload)]=payload; iddata=b''.join(XATTR_ID_STRUCT.pack(*record) for record in records); b[idmeta:idmeta+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(iddata)); b[idmeta+2:idmeta+2+len(iddata)]=iddata; b[table:table+16]=struct.pack('<QII',xstart,len(records),0); b[table+16:table+24]=struct.pack('<Q',idmeta); p.write_bytes(b); return d,SquashFSImage(p)
    def extended_inode(self, xattr):
        header=SquashFSInodeHeader(9,0,0,0,0,1); body=SquashFSExtendedRegularInode(header,0,0,0,1,SQUASHFS_INVALID_FRAGMENT,0,xattr)
        return SquashFSInode(SquashFSMetadataReference(0,0),header,body)
    def parsed_extended_inode(self, image, xattr):
        offset=image.image.stat().st_size; raw=INODE_HEADER_STRUCT.pack(9,0,0,0,0,1)+EXTENDED_REGULAR_INODE_BODY_STRUCT.pack(0,0,0,1,SQUASHFS_INVALID_FRAGMENT,0,xattr)
        with image.image.open('ab') as source: source.write(struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(raw))+raw)
        return read_inode(SquashFSMetadataStream(image,offset),SquashFSMetadataReference(0,0))

class SquashFSXAttrIDTableReaderTest(_XAttrFixture):
    def test_rootfs_optional_table_discovery(self):
        image=SquashFSImage(ROOTFS); table=read_xattr_id_table(image)
        if image.read_superblock().xattr_id_table_start == SQUASHFS_INVALID_BLK: self.assertIsNone(table)
        else: self.assertIsNotNone(table)
    def test_absent_table_returns_none(self):
        d,i=self.xattr_image(absent=True)
        with d:self.assertIsNone(read_xattr_id_table(i))
    def test_one_xattr_id(self):
        d,i=self.xattr_image()
        with d:self.assertEqual(read_xattr_id_table(i).xattr_ids,1)
    def test_zero_ids_rejected(self):
        d,i=self.xattr_image(())
        with d:self.assertRaises(SquashFSXAttrTableError,read_xattr_id_table,i)
    def test_index_count_one(self):
        d,i=self.xattr_image()
        with d:self.assertEqual(len(read_xattr_id_table(i).metadata_block_offsets),1)
    def test_unused_is_preserved(self):
        d,i=self.xattr_image()
        with d:self.assertEqual(read_xattr_id_table(i).unused,7)
    def test_table_is_immutable(self):
        d,i=self.xattr_image()
        with d:
            t=read_xattr_id_table(i)
            with self.assertRaises(AttributeError):t.xattr_ids=2
    def test_truncated_table_header_has_typed_error(self):
        d,i=self.xattr_image()
        with d:
            sb=i.read_superblock()
            with i.image.open('r+b') as source: source.truncate(sb.xattr_id_table_start+8)
            i.superblock=None
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_table_start_outside_backing_image_is_rejected(self):
        d,i=self.xattr_image()
        with d:
            sb=i.read_superblock(); self.patch(i,56,struct.pack('<Q',i.image.stat().st_size+1))
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_header_partially_outside_backing_image_is_rejected(self):
        d,i=self.xattr_image()
        with d:
            self.patch(i,56,struct.pack('<Q',i.image.stat().st_size-8))
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_truncated_index_has_typed_error(self):
        d,i=self.xattr_image()
        with d:
            sb=i.read_superblock(); self.patch(i,sb.xattr_id_table_start+8,struct.pack('<I',513))
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_extra_bytes_after_index_are_rejected(self):
        d,i=self.xattr_image()
        with d:
            self.patch(i,40,struct.pack('<Q',i.image.stat().st_size+1))
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_first_metadata_offset_outside_filesystem_is_rejected(self):
        d,i=self.xattr_image()
        with d:
            sb=i.read_superblock(); self.patch(i,sb.xattr_id_table_start+16,struct.pack('<Q',sb.bytes_used))
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_duplicate_metadata_offsets_are_rejected(self):
        d,i=self.xattr_image(tuple((0,0,0) for _ in range(513)))
        with d:
            sb=i.read_superblock(); first=i.image.read_bytes()[sb.xattr_id_table_start+16:sb.xattr_id_table_start+24]; self.patch(i,sb.xattr_id_table_start+24,first)
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_non_increasing_metadata_offsets_are_rejected(self):
        d,i=self.xattr_image(tuple((0,0,0) for _ in range(513)))
        with d:
            sb=i.read_superblock(); self.patch(i,sb.xattr_id_table_start+24,struct.pack('<Q',4095))
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_excessive_metadata_block_distance_is_rejected(self):
        d,i=self.xattr_image(tuple((0,0,0) for _ in range(513)))
        with d:
            sb=i.read_superblock(); self.patch(i,sb.xattr_id_table_start+24,struct.pack('<Q',4096+METADATA_SIZE+3))
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_xattr_data_start_equal_to_first_metadata_is_rejected(self):
        d,i=self.xattr_image()
        with d:
            sb=i.read_superblock(); self.patch(i,sb.xattr_id_table_start,struct.pack('<Q',4096))
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_xattr_data_start_before_first_metadata_is_accepted(self):
        d,i=self.xattr_image()
        with d:self.assertEqual(read_xattr_id_table(i).xattr_table_start,128)
    def test_xattr_data_start_after_first_metadata_is_rejected(self):
        d,i=self.xattr_image()
        with d:
            sb=i.read_superblock(); self.patch(i,sb.xattr_id_table_start,struct.pack('<Q',4097))
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_last_metadata_offset_must_precede_table(self):
        d,i=self.xattr_image()
        with d:
            sb=i.read_superblock(); self.patch(i,sb.xattr_id_table_start+16,struct.pack('<Q',sb.xattr_id_table_start))
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)
    def test_excessive_distance_from_last_metadata_block_is_rejected(self):
        d,i=self.xattr_image()
        with d:
            sb=i.read_superblock(); self.patch(i,sb.xattr_id_table_start+16,struct.pack('<Q',128))
            with self.assertRaises(SquashFSXAttrTableError): read_xattr_id_table(i)

class SquashFSXAttrIDReaderTest(_XAttrFixture):
    def test_index_zero(self):
        d,i=self.xattr_image()
        with d:self.assertEqual(read_xattr_id(i,0).index,0)
    def test_reference_decoding(self):
        d,i=self.xattr_image(((0x1234ffff,3,4),))
        with d:self.assertEqual((read_xattr_id(i,0).reference.block,read_xattr_id(i,0).reference.offset),(0x1234,0xffff))
    def test_count_is_little_endian(self):
        d,i=self.xattr_image(((0x10000,0x11223344,0x55667788),))
        with d:self.assertEqual(read_xattr_id(i,0).count,0x11223344)
    def test_size_is_little_endian(self):
        d,i=self.xattr_image(((0x10000,0x11223344,0x55667788),))
        with d:self.assertEqual(read_xattr_id(i,0).size,0x55667788)
    def test_negative_index_rejected(self):
        d,i=self.xattr_image()
        with d:self.assertRaises(SquashFSXAttrIDError,read_xattr_id,i,-1)
    def test_upper_index_rejected(self):
        d,i=self.xattr_image()
        with d:self.assertRaises(SquashFSXAttrIDError,read_xattr_id,i,1)
    def test_compressed_metadata(self):
        d,i=self.xattr_image(compressed=True)
        with d:self.assertEqual(read_xattr_id(i,0).count,1)
    def test_uncompressed_metadata(self):
        d, i = self.xattr_image(compressed=False)
        with d:
            self.assertEqual(read_xattr_id(i, 0).count, 1)
    def test_missing_table_rejected(self):
        d,i=self.xattr_image(absent=True)
        with d:self.assertRaises(SquashFSXAttrTableError,read_xattr_id,i,0)
    def test_models_are_immutable(self):
        d,i=self.xattr_image()
        with d:
            x=read_xattr_id(i,0)
            with self.assertRaises(AttributeError):x.count=3
    def test_record_at_offset_8176(self):
        d,i=self.xattr_image(tuple((0x10000, n, n + 1) for n in range(513)))
        with d:self.assertEqual(read_xattr_id(i,511).count,511)
    def test_next_record_uses_next_metadata_block(self):
        d,i=self.xattr_image(tuple((0x10000, n, n + 1) for n in range(513)))
        with d:self.assertEqual(read_xattr_id(i,512).count,512)
    def test_metadata_error_is_wrapped_with_cause(self):
        d,i=self.xattr_image()
        with d:
            with i.image.open('r+b') as source: source.seek(4096); source.write(b'\xff\x7f')
            with self.assertRaises(SquashFSXAttrIDError) as caught: read_xattr_id(i,0)
            self.assertIsNotNone(caught.exception.__cause__)
    def test_middle_index_reads_its_record(self):
        d,i=self.xattr_image(((0,1,2),(1,3,4),(2,5,6)))
        with d:self.assertEqual(read_xattr_id(i,1).count,3)
    def test_last_valid_index_reads_its_record(self):
        d,i=self.xattr_image(((0,1,2),(1,3,4),(2,5,6)))
        with d:self.assertEqual(read_xattr_id(i,2).size,6)
    def test_index_above_upper_bound_is_rejected(self):
        d,i=self.xattr_image()
        with d:self.assertRaises(SquashFSXAttrIDError,read_xattr_id,i,2)
    def test_zero_reference_offset_decodes(self):
        d,i=self.xattr_image(((0x10000,1,2),(0x2ffff,3,4)))
        with d:self.assertEqual(read_xattr_id(i,0).reference.offset,0)
    def test_maximum_reference_offset_decodes(self):
        d,i=self.xattr_image(((0x10000,1,2),(0x2ffff,3,4)))
        with d:self.assertEqual(read_xattr_id(i,1).reference.offset,0xffff)
    def test_truncated_record_has_typed_error_and_cause(self):
        d,i=self.xattr_image()
        with d:
            self.patch(i,4096,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|8))
            with self.assertRaises(SquashFSXAttrIDError) as caught: read_xattr_id(i,0)
            self.assertIsNotNone(caught.exception.__cause__)
    def test_reference_model_is_immutable(self):
        d,i=self.xattr_image()
        with d:
            with self.assertRaises(AttributeError): read_xattr_id(i,0).reference.block=1

class SquashFSXAttrInodeIntegrationTest(unittest.TestCase):
    def test_extended_directory_sentinel_maps_none(self): self.assertIsNone(SquashFSExtendedDirectoryInode(SquashFSInodeHeader(8,0,0,0,0,1),0,0,0,0,0,0,0xffffffff).xattr_id)
    def test_extended_directory_zero_is_valid(self): self.assertEqual(SquashFSExtendedDirectoryInode(SquashFSInodeHeader(8,0,0,0,0,1),0,0,0,0,0,0,0).xattr_id,0)
    def test_extended_regular_sentinel_maps_none(self): self.assertIsNone(SquashFSExtendedRegularInode(SquashFSInodeHeader(9,0,0,0,0,1),0,0,0,0,0,0,0xffffffff).xattr_id)
    def test_extended_regular_zero_is_valid(self): self.assertEqual(SquashFSExtendedRegularInode(SquashFSInodeHeader(9,0,0,0,0,1),0,0,0,0,0,0,0).xattr_id,0)
    def test_extended_symlink_sentinel_maps_none(self): self.assertIsNone(SquashFSExtendedSymlinkInode(SquashFSInodeHeader(10,0,0,0,0,1),0,0,0xffffffff).xattr_id)
    def test_extended_symlink_zero_is_valid(self): self.assertEqual(SquashFSExtendedSymlinkInode(SquashFSInodeHeader(10,0,0,0,0,1),0,0,0).xattr_id,0)
    def test_extended_directory_nonzero_is_preserved(self): self.assertEqual(SquashFSExtendedDirectoryInode(SquashFSInodeHeader(8,0,0,0,0,1),0,0,0,0,0,0,7).xattr_id,7)
    def test_extended_regular_nonzero_is_preserved(self): self.assertEqual(SquashFSExtendedRegularInode(SquashFSInodeHeader(9,0,0,0,0,1),0,0,0,0,0,0,7).xattr_id,7)
    def test_extended_symlink_nonzero_is_preserved(self): self.assertEqual(SquashFSExtendedSymlinkInode(SquashFSInodeHeader(10,0,0,0,0,1),0,0,7).xattr_id,7)
    def test_basic_directory_has_no_xattr_id(self): self.assertFalse(hasattr(SquashFSBasicDirectoryInode(SquashFSInodeHeader(1,0,0,0,0,1),0,0,0,0,0),'xattr_id'))
    def test_basic_regular_has_no_xattr_id(self): self.assertFalse(hasattr(SquashFSBasicRegularInode(SquashFSInodeHeader(2,0,0,0,0,1),0,0,0,0),'xattr_id'))
    def test_basic_symlink_has_no_xattr_id(self): self.assertFalse(hasattr(SquashFSBasicSymlinkInode(SquashFSInodeHeader(3,0,0,0,0,1),0,0),'xattr_id'))
    def test_inode_id_selects_production_xattr_record(self):
        fixture=_XAttrFixture(); d,i=fixture.xattr_image(((0,11,12),(1,13,14)))
        with d:
            inode=SquashFSExtendedRegularInode(SquashFSInodeHeader(9,0,0,0,0,1),0,0,0,0,0,0,1)
            self.assertEqual(read_xattr_id(i,inode.xattr_id).count,13)
    def test_inode_xattr_property_does_not_eagerly_read_metadata(self):
        inode=SquashFSExtendedRegularInode(SquashFSInodeHeader(9,0,0,0,0,1),0,0,0,0,0,0,0)
        self.assertEqual(inode.xattr_id,0)

class SquashFSXAttrRootfsTest(unittest.TestCase):
    def test_rootfs_xattr_id_table_facts(self):
        image=SquashFSImage(ROOTFS); sb=image.read_superblock(); table=read_xattr_id_table(image); item=read_xattr_id(image,0,table)
        self.assertIsNotNone(table); self.assertEqual((sb.bytes_used,sb.xattr_id_table_start,table.xattr_table_start,table.xattr_ids,table.unused,table.metadata_block_offsets),(609067236,609067212,609067154,1,115,(609067194,)))
        self.assertEqual((item.encoded_reference,item.reference.block,item.reference.offset,item.count,item.size),(0,0,0,1,40))
        self.assertEqual(table.table_start+16+8*len(table.metadata_block_offsets),sb.bytes_used)
    def test_rootfs_extended_inode_xattr_ids_are_in_range(self):
        image=SquashFSImage(ROOTFS); sb=image.read_superblock(); table=read_xattr_id_table(image)
        values=[]; extended=0
        for inode in SquashFSXAttrEntryListRootFSIntegrationTest.rootfs_inodes(image,sb):
            body=inode.body
            if isinstance(body,(SquashFSExtendedDirectoryInode,SquashFSExtendedRegularInode,SquashFSExtendedSymlinkInode)):
                extended+=1
                if body.xattr_id is not None: values.append(body.xattr_id)
        self.assertEqual((extended,len(values),min(values),max(values)),(23,1,0,0))
        self.assertTrue(all(0<=value<table.xattr_ids for value in values))


@unittest.skipUnless(ROOTFS.is_file(), "UDM Pro ROOTFS fixture is unavailable")
class SquashFSXAttrEntryListRootFSIntegrationTest(unittest.TestCase):
    _inode_cache=None
    @staticmethod
    def rootfs_context():
        image=SquashFSImage(ROOTFS); superblock=image.read_superblock(); table=read_xattr_id_table(image)
        return image,superblock,table
    @classmethod
    def rootfs_inodes(cls, image, superblock):
        if cls._inode_cache is not None:
            return cls._inode_cache
        lookup=read_inode_lookup_table(image); stream=SquashFSMetadataStream(image,superblock.inode_table_start)
        cls._inode_cache=tuple(resolve_inode_number(image,stream,lookup,number) for number in range(1,lookup.inode_count+1))
        return cls._inode_cache
    def test_real_rootfs_xattr_table_loads(self):
        image,_,table=self.rootfs_context()
        self.assertIsNotNone(table); self.assertEqual(table.xattr_ids,1)
    def test_real_rootfs_id_zero_parses(self):
        image,_,table=self.rootfs_context()
        value=read_xattr_list(image,read_xattr_id(image,0,table),table)
        self.assertEqual((value.xattr_id.index,len(value.entries)),(0,1))
    def test_all_real_xattr_id_records_parse(self):
        image,_,table=self.rootfs_context()
        self.assertEqual([read_xattr_list(image,read_xattr_id(image,index,table),table).xattr_id.index for index in range(table.xattr_ids)],[0])
    def test_real_list_count_and_consumed_size_match_measurement(self):
        image,_,table=self.rootfs_context(); value=read_xattr_list(image,read_xattr_id(image,0,table),table)
        self.assertEqual((len(value.entries),value.consumed_size,value.xattr_id.size),(1,38,40))
    def test_real_namespace_and_representation_are_valid(self):
        image,_,table=self.rootfs_context(); entry=read_xattr_list(image,read_xattr_id(image,0,table),table).entries[0]
        self.assertEqual((entry.full_name,entry.out_of_line,entry.value_size),(b'security.capability',False,20))
        self.assertEqual((entry.value,entry.out_of_line_reference),(b'\x01\x00\x00\x02\x00 \x00\x00'+b'\0'*12,None))
    def test_real_inode_with_xattrs_resolves_through_inode_api(self):
        image,superblock,table=self.rootfs_context(); inodes=self.rootfs_inodes(image,superblock); inode=next(inode for inode in inodes if getattr(inode.body,'xattr_id',None) is not None)
        self.assertEqual(read_inode_xattrs(image,inode,table).entries[0].full_name,b'security.capability')
    def test_real_inode_without_xattrs_returns_none(self):
        image,superblock,table=self.rootfs_context(); inodes=self.rootfs_inodes(image,superblock); inode=next(inode for inode in inodes if getattr(inode.body,'xattr_id',None) is None)
        self.assertIsNone(read_inode_xattrs(image,inode,table))
    def test_real_extended_sentinel_is_not_id_zero(self):
        image,superblock,table=self.rootfs_context(); inodes=self.rootfs_inodes(image,superblock); inode=next(inode for inode in inodes if isinstance(inode.body,(SquashFSExtendedDirectoryInode,SquashFSExtendedRegularInode,SquashFSExtendedSymlinkInode)) and inode.body.xattr_id is None)
        self.assertIsNone(read_inode_xattrs(image,inode,table))

class SquashFSXAttrNamespaceTest(unittest.TestCase):
    def test_user_namespace(self): self.assertEqual(decode_xattr_namespace(0).prefix,b'user.')
    def test_trusted_namespace(self): self.assertEqual(decode_xattr_namespace(1).prefix,b'trusted.')
    def test_security_namespace(self): self.assertEqual(decode_xattr_namespace(2).prefix,b'security.')
    def test_ool_bit_is_separate_from_namespace(self): self.assertEqual((decode_xattr_namespace(0x101).raw_type,decode_xattr_namespace(0x101).prefix),(1,b'trusted.'))
    def test_unknown_type_is_preserved_exactly(self): self.assertEqual(decode_xattr_namespace(0x47).raw_type,0x47)
    def test_raw_type_is_preserved(self): self.assertEqual(decode_xattr_namespace(0x101).raw_type,1)
    def test_unknown_namespace_has_no_prefix(self): self.assertIsNone(decode_xattr_namespace(7).prefix)
    def test_unknown_namespace_is_known_false(self): self.assertFalse(decode_xattr_namespace(7).known)
    def test_namespace_model_is_immutable(self):
        value=decode_xattr_namespace(0)
        with self.assertRaises(AttributeError): value.prefix=b'x'

class SquashFSXAttrEntryReaderTest(_XAttrFixture):
    def test_regular_entry_preserves_binary_name_and_full_name(self):
        d,i=self.list_image(((0,b'a\xff',b'v'),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].full_name,b'user.a\xff')
    def test_zero_length_name_is_structural(self):
        d,i=self.list_image(((0,b'',b''),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].name,b'')
    def test_truncated_entry_has_chained_error(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|2))
            with self.assertRaises(SquashFSXAttrEntryError) as caught: read_xattr_list(i,read_xattr_id(i,0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSMetadataStreamError)
    def test_minimal_valid_entry(self):
        d,i=self.list_image(((0,b'',b''),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,b'')
    def test_name_with_nul_is_preserved(self):
        d,i=self.list_image(((0,b'a\0b',b'v'),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].name,b'a\0b')
    def test_little_endian_name_size(self):
        d,i=self.list_image(((0,b'ab',b'v'),))
        with d:self.assertEqual(len(read_xattr_list(i,read_xattr_id(i,0)).entries[0].name),2)
    def test_one_byte_entry_header_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|1))
            with self.assertRaises(SquashFSXAttrEntryError):read_xattr_list(i,read_xattr_id(i,0))
    def test_three_byte_entry_header_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|3))
            with self.assertRaises(SquashFSXAttrEntryError):read_xattr_list(i,read_xattr_id(i,0))
    def test_unknown_namespace_has_no_full_name(self):
        d,i=self.list_image(((7,b'a',b'v'),))
        with d:self.assertIsNone(read_xattr_list(i,read_xattr_id(i,0)).entries[0].full_name)
    def test_entry_model_is_immutable(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            entry=read_xattr_list(i,read_xattr_id(i,0)).entries[0]
            with self.assertRaises(AttributeError):entry.name=b'x'
    def test_truncated_name_by_one_byte_is_rejected(self):
        d,i=self.list_image(((0,b'ab',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|5))
            with self.assertRaisesRegex(SquashFSXAttrEntryError,'Cannot read xattr entry 0'): read_xattr_list(i,read_xattr_id(i,0))
    def test_name_size_larger_than_available_metadata_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,128+2,struct.pack('<HH',0,0xffff))
            with self.assertRaisesRegex(SquashFSXAttrEntryError,'Cannot read xattr entry 0'): read_xattr_list(i,read_xattr_id(i,0))
    def test_zero_available_name_bytes_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|4)); self.patch(i,130,struct.pack('<HH',0,1))
            with self.assertRaisesRegex(SquashFSXAttrEntryError,'Cannot read xattr entry 0'): read_xattr_list(i,read_xattr_id(i,0))
    def test_name_crosses_physical_metadata_boundary(self):
        raw=struct.pack('<HH',0,3)+b'abc'+struct.pack('<I',0); d,i,next_block=self.boundary_list_image(raw,1,len(raw),8186)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[8186:],struct.pack('<HH',0,3)+b'ab')
            self.assertEqual(i.read_metadata_block(next_block).data[:1],b'c')
            entry=read_xattr_list(i,read_xattr_id(i,0)).entries[0]
            self.assertEqual((entry.name,next_block),(b'abc',128+2+METADATA_SIZE))
    def test_name_starts_at_final_payload_byte(self):
        raw=struct.pack('<HH',0,2)+b'ab'+struct.pack('<I',0); d,i,_=self.boundary_list_image(raw,1,len(raw),8187)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[-1:],b'a')
            self.assertEqual(i.read_metadata_block(128+2+METADATA_SIZE).data[:1],b'b')
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].name,b'ab')
    def test_name_ends_exactly_at_payload_boundary(self):
        raw=struct.pack('<HH',0,1)+b'a'+struct.pack('<I',0); d,i,_=self.boundary_list_image(raw,1,len(raw),8187)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[-1:],b'a')
            self.assertEqual(i.read_metadata_block(128+2+METADATA_SIZE).data[:4],struct.pack('<I',0))
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].name,b'a')
    def test_entry_header_crosses_metadata_boundary(self):
        raw=struct.pack('<HH',0,1)+b'a'+struct.pack('<I',0); d,i,_=self.boundary_list_image(raw,1,len(raw),8190)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[-2:],b'\0\0')
            self.assertEqual(i.read_metadata_block(128+2+METADATA_SIZE).data[:2],b'\1\0')
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].name,b'a')
    def test_malformed_next_metadata_block_is_wrapped(self):
        raw=struct.pack('<HH',0,3)+b'abc'+struct.pack('<I',0); d,i,next_block=self.boundary_list_image(raw,1,len(raw),8186)
        with d:
            self.patch(i,next_block,b'\0\0')
            with self.assertRaises(SquashFSXAttrEntryError) as caught: read_xattr_list(i,read_xattr_id(i,0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSMetadataStreamError)
    def test_binary_name_is_exact_after_boundary_traversal(self):
        raw=struct.pack('<HH',0,3)+b'\xff\0\x80'+struct.pack('<I',0); d,i,_=self.boundary_list_image(raw,1,len(raw),8186)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[-2:],b'\xff\0')
            self.assertEqual(i.read_metadata_block(128+2+METADATA_SIZE).data[:1],b'\x80')
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].name,b'\xff\0\x80')

class SquashFSXAttrInlineValueTest(_XAttrFixture):
    def test_zero_length_inline_value(self):
        d,i=self.list_image(((0,b'n',b''),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,b'')
    def test_normal_inline_value(self):
        d,i=self.list_image(((0,b'n',b'value'),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,b'value')
    def test_binary_inline_value_contains_nul_bytes(self):
        d,i=self.list_image(((0,b'n',b'a\0b'),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,b'a\0b')
    def test_binary_inline_value_contains_invalid_utf8_bytes(self):
        d,i=self.list_image(((0,b'n',b'\xff\x80'),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,b'\xff\x80')
    def test_little_endian_vsize_is_decoded(self):
        d,i=self.list_image(((0,b'n',b'\0'*0x102),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value_size,0x102)
    def test_raw_value_bytes_are_preserved_exactly(self):
        raw=b'\x00\xff\x80value'; d,i=self.list_image(((0,b'n',raw),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,raw)
    def test_truncated_value_header_with_zero_bytes_is_rejected(self):
        d,i=self.list_image(((0,b'n',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|5))
            with self.assertRaisesRegex(SquashFSXAttrValueError,'value for entry 0'):read_xattr_list(i,read_xattr_id(i,0))
    def test_one_byte_value_header_is_rejected(self):
        d,i=self.list_image(((0,b'n',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|6))
            with self.assertRaises(SquashFSXAttrValueError):read_xattr_list(i,read_xattr_id(i,0))
    def test_two_byte_value_header_is_rejected(self):
        d,i=self.list_image(((0,b'n',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|7))
            with self.assertRaises(SquashFSXAttrValueError):read_xattr_list(i,read_xattr_id(i,0))
    def test_three_byte_value_header_is_rejected(self):
        d,i=self.list_image(((0,b'n',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|8))
            with self.assertRaises(SquashFSXAttrValueError):read_xattr_list(i,read_xattr_id(i,0))
    def test_declared_inline_value_truncated_by_one_byte_is_rejected(self):
        d,i=self.list_image(((0,b'n',b'ab'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|10))
            with self.assertRaises(SquashFSXAttrValueError):read_xattr_list(i,read_xattr_id(i,0))
    def test_declared_inline_value_larger_than_available_metadata_is_rejected(self):
        d,i=self.list_image(((0,b'n',b'v'),))
        with d:
            self.patch(i,135,struct.pack('<I',0xffff))
            with self.assertRaises(SquashFSXAttrValueError):read_xattr_list(i,read_xattr_id(i,0))
    def test_zero_available_value_bytes_after_header_is_rejected(self):
        d,i=self.list_image(((0,b'n',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|9))
            with self.assertRaises(SquashFSXAttrValueError):read_xattr_list(i,read_xattr_id(i,0))
    def test_inline_value_crosses_physical_metadata_boundary(self):
        value=b'abc'; raw=struct.pack('<HH',0,1)+b'n'+struct.pack('<I',3)+value; d,i,next_block=self.boundary_list_image(raw,1,len(raw),8181)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[-2:],b'ab')
            self.assertEqual(i.read_metadata_block(next_block).data[:1],b'c')
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,value)
    def test_inline_value_starts_at_final_payload_byte(self):
        value=b'ab'; raw=struct.pack('<HH',0,1)+b'n'+struct.pack('<I',2)+value; d,i,next_block=self.boundary_list_image(raw,1,len(raw),8182)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[-1:],b'a')
            self.assertEqual(i.read_metadata_block(next_block).data[:1],b'b')
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,value)
    def test_inline_value_ends_exactly_at_payload_boundary(self):
        value=b'a'; raw=struct.pack('<HH',0,1)+b'n'+struct.pack('<I',1)+value; d,i,next_block=self.boundary_list_image(raw,1,len(raw),8182)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[-1:],value)
            self.assertEqual(next_block,128+2+METADATA_SIZE)
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,value)
    def test_value_header_crosses_metadata_block_boundary(self):
        raw=struct.pack('<HH',0,1)+b'n'+struct.pack('<I',1)+b'a'; d,i,next_block=self.boundary_list_image(raw,1,len(raw),8185)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[-2:],b'\1\0')
            self.assertEqual(i.read_metadata_block(next_block).data[:2],b'\0\0')
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,b'a')
    def test_malformed_next_metadata_block_while_reading_value_is_wrapped(self):
        value=b'abc'; raw=struct.pack('<HH',0,1)+b'n'+struct.pack('<I',3)+value; d,i,next_block=self.boundary_list_image(raw,1,len(raw),8181)
        with d:
            self.patch(i,next_block,b'\0\0')
            with self.assertRaises(SquashFSXAttrValueError) as caught:read_xattr_list(i,read_xattr_id(i,0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSMetadataStreamError)
    def test_uncompressed_inline_metadata_path(self):
        d,i=self.list_image(((0,b'n',b'value'),),compressed=False)
        with d:self.assertFalse(i.read_metadata_block(128).is_compressed);self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,b'value')
    def test_compressed_inline_metadata_path(self):
        d,i=self.list_image(((0,b'n',b'value'),),compressed=True)
        with d:self.assertTrue(i.read_metadata_block(128).is_compressed);self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,b'value')
    def test_compressed_block_transitions_to_following_metadata_block(self):
        value=b'abc'; raw=struct.pack('<HH',0,1)+b'n'+struct.pack('<I',3)+value; d,i,next_block=self.boundary_list_image(raw,1,len(raw),8181,compressed_first=True)
        with d:
            self.assertTrue(i.read_metadata_block(128).is_compressed)
            self.assertEqual(i.read_metadata_block(next_block).data[:1],b'c')
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,value)
    def test_malformed_value_raises_typed_value_error(self):
        d,i=self.list_image(((0,b'n',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|8))
            with self.assertRaises(SquashFSXAttrValueError):read_xattr_list(i,read_xattr_id(i,0))
    def test_metadata_failure_is_preserved_as_value_error_cause(self):
        d,i=self.list_image(((0,b'n',b'v'),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|9))
            with self.assertRaises(SquashFSXAttrValueError) as caught:read_xattr_list(i,read_xattr_id(i,0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSMetadataStreamError)
    def test_inline_representation_is_unambiguous(self):
        value=b'\0\xff'; d,i=self.list_image(((0,b'n',value),))
        with d:
            entry=read_xattr_list(i,read_xattr_id(i,0)).entries[0]
            self.assertEqual((entry.out_of_line,entry.value,entry.out_of_line_reference),(False,value,None))

class SquashFSXAttrOutOfLineDetectionTest(_XAttrFixture):
    def test_ool_flag_is_detected(self):
        d,i=self.list_image(((0x100,b'n',struct.pack('<Q',0)),))
        with d:self.assertTrue(read_xattr_list(i,read_xattr_id(i,0)).entries[0].out_of_line)
    def test_namespace_bits_are_independent_from_ool_flag(self):
        d,i=self.list_image(((0x102,b'n',struct.pack('<Q',0)),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].namespace.prefix,b'security.')
    def test_ool_raw_type_is_preserved_exactly(self):
        d,i=self.list_image(((0x147,b'n',struct.pack('<Q',0)),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].raw_type,0x147)
    def test_ool_out_of_line_is_true(self):
        d,i=self.list_image(((0x100,b'n',struct.pack('<Q',0)),))
        with d:self.assertIs(read_xattr_list(i,read_xattr_id(i,0)).entries[0].out_of_line,True)
    def test_ool_value_is_none(self):
        d,i=self.list_image(((0x100,b'n',struct.pack('<Q',0)),))
        with d:self.assertIsNone(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value)
    def test_ool_reference_is_little_endian_u64(self):
        ref=0x0102030405060708; d,i=self.list_image(((0x101,b'n',struct.pack('<Q',ref)),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].out_of_line_reference,ref)
    def test_ool_zero_reference_is_preserved(self):
        d,i=self.list_image(((0x100,b'n',struct.pack('<Q',0)),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].out_of_line_reference,0)
    def test_ool_nonzero_reference_is_preserved(self):
        d,i=self.list_image(((0x100,b'n',struct.pack('<Q',9)),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].out_of_line_reference,9)
    def test_ool_maximum_u64_reference_is_preserved(self):
        d,i=self.list_image(((0x100,b'n',struct.pack('<Q',0xffffffffffffffff)),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].out_of_line_reference,0xffffffffffffffff)
    def test_ool_reference_with_zero_bytes_available_is_rejected(self):
        d,i=self.list_image(((0x100,b'n',struct.pack('<Q',0)),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|9))
            with self.assertRaises(SquashFSXAttrValueError):read_xattr_list(i,read_xattr_id(i,0))
    def test_ool_reference_truncated_by_one_byte_is_rejected(self):
        d,i=self.list_image(((0x100,b'n',struct.pack('<Q',0)),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|16))
            with self.assertRaises(SquashFSXAttrValueError):read_xattr_list(i,read_xattr_id(i,0))
    def test_malformed_ool_representation_is_rejected(self):
        raw=struct.pack('<HH',0x100,1)+b'n'+struct.pack('<I',7)+b'\0'*7; d,i,_=self.boundary_list_image(raw,1,len(raw),0)
        with d:
            with self.assertRaisesRegex(SquashFSXAttrValueError,'must be 8 bytes'):read_xattr_list(i,read_xattr_id(i,0))
    def test_ool_reference_crosses_physical_metadata_boundary(self):
        ref=0x0102030405060708; raw=struct.pack('<HH',0x100,1)+b'n'+struct.pack('<I',8)+struct.pack('<Q',ref); d,i,next_block=self.boundary_list_image(raw,1,len(raw),8181)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[-2:],struct.pack('<Q',ref)[:2])
            self.assertEqual(i.read_metadata_block(next_block).data[:6],struct.pack('<Q',ref)[2:])
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].out_of_line_reference,ref)
    def test_ool_reference_starts_at_final_payload_byte(self):
        ref=0x0102030405060708; raw=struct.pack('<HH',0x100,1)+b'n'+struct.pack('<I',8)+struct.pack('<Q',ref); d,i,next_block=self.boundary_list_image(raw,1,len(raw),8182)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[-1:],struct.pack('<Q',ref)[:1])
            self.assertEqual(i.read_metadata_block(next_block).data[:7],struct.pack('<Q',ref)[1:])
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].out_of_line_reference,ref)
    def test_ool_reference_ends_exactly_at_payload_boundary(self):
        ref=0x0102030405060708; raw=struct.pack('<HH',0x100,1)+b'n'+struct.pack('<I',8)+struct.pack('<Q',ref); d,i,next_block=self.boundary_list_image(raw,1,len(raw),8175)
        with d:
            self.assertEqual(i.read_metadata_block(128).data[-8:],struct.pack('<Q',ref))
            self.assertEqual(next_block,128+2+METADATA_SIZE)
            self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].out_of_line_reference,ref)
    def test_malformed_next_metadata_block_while_reading_ool_reference_is_wrapped(self):
        raw=struct.pack('<HH',0x100,1)+b'n'+struct.pack('<I',8)+struct.pack('<Q',0); d,i,next_block=self.boundary_list_image(raw,1,len(raw),8181)
        with d:
            self.patch(i,next_block,b'\0\0')
            with self.assertRaises(SquashFSXAttrValueError) as caught:read_xattr_list(i,read_xattr_id(i,0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSMetadataStreamError)
    def test_ool_is_never_exposed_as_inline_value_bytes(self):
        raw=struct.pack('<Q',0x12340002); d,i=self.list_image(((0x101,b'n',raw),))
        with d:self.assertNotEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,raw)
    def test_ool_target_is_not_dereferenced(self):
        d,i=self.list_image(((0x100,b'n',struct.pack('<Q',0xffffffffffffffff)),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].out_of_line_reference,0xffffffffffffffff)
    def test_malformed_ool_raises_typed_value_error(self):
        raw=struct.pack('<HH',0x100,1)+b'n'+struct.pack('<I',1)+b'\0'; d,i,_=self.boundary_list_image(raw,1,len(raw),0)
        with d:
            with self.assertRaises(SquashFSXAttrValueError):read_xattr_list(i,read_xattr_id(i,0))
    def test_metadata_failure_is_preserved_as_ool_value_error_cause(self):
        d,i=self.list_image(((0x100,b'n',struct.pack('<Q',0)),))
        with d:
            self.patch(i,128,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|16))
            with self.assertRaises(SquashFSXAttrValueError) as caught:read_xattr_list(i,read_xattr_id(i,0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSMetadataStreamError)

class SquashFSXAttrOutOfLineValueStage20C1Test(_XAttrFixture):
    """Focused physical-fixture coverage for Stage 20 OOL value resolution."""
    def target_image(self, target: bytes):
        d=tempfile.TemporaryDirectory(); p=Path(d.name)/'ool-value.sqfs'; xstart=128
        idmeta=xstart+2+len(target)+16; table=idmeta+18; end=table+24
        raw=bytearray(end); raw[:96]=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,1,0,4096,0,6,12,0,1,4,0,0,end,0,table,0,0,0,0)
        raw[xstart:xstart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(target)); raw[xstart+2:xstart+2+len(target)]=target
        raw[idmeta:idmeta+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|16); raw[idmeta+2:idmeta+18]=XATTR_ID_STRUCT.pack(0,1,0)
        raw[table:table+16]=struct.pack('<QII',xstart,1,0); raw[table+16:table+24]=struct.pack('<Q',idmeta)
        p.write_bytes(raw); return d,SquashFSImage(p)
    @staticmethod
    def entry(reference=0):
        return SquashFSXAttrEntry(0x100,decode_xattr_namespace(0),b'n',b'user.n',None,8,True,reference)
    def resolve(self, target, reference=0, table=None):
        d,i=self.target_image(target); self.addCleanup(d.cleanup)
        return i,read_xattr_out_of_line_value(i,self.entry(reference),table)
    def test_simple_binary_value_and_entry_are_unchanged(self):
        payload=b'\x00\xffvalue\x80'; d,i=self.target_image(struct.pack('<I',len(payload))+payload); self.addCleanup(d.cleanup)
        table=read_xattr_id_table(i); entry=self.entry(); before=entry
        self.assertEqual(read_xattr_out_of_line_value(i,entry,table),payload)
        self.assertEqual(entry,before); self.assertIsNone(entry.value); self.assertEqual(entry.out_of_line_reference,0)
    def test_none_table_loads_and_supplied_table_is_reused(self):
        d,i=self.target_image(struct.pack('<I',1)+b'Z'); self.addCleanup(d.cleanup); table=read_xattr_id_table(i)
        with patch('squashfs.read_xattr_id_table',wraps=read_xattr_id_table) as reads:
            self.assertEqual(read_xattr_out_of_line_value(i,self.entry(),table),b'Z'); self.assertEqual(reads.call_count,0)
            self.assertEqual(read_xattr_out_of_line_value(i,self.entry()),b'Z'); self.assertEqual(reads.call_count,1)
    def test_reference_decoder_linux_bit_layout_and_invalid_inputs(self):
        for value,block,offset in ((0,0,0),(0x120000,0x12,0),(0x45,0,0x45),(0x120045,0x12,0x45),(0xffffffffffffffff,0xffffffffffff,0xffff)):
            decoded=decode_xattr_reference(value); self.assertEqual((decoded.block,decoded.offset),(block,offset))
        for value in (-1,0x10000000000000000,True):
            with self.assertRaises(TypeError): decode_xattr_reference(value)
    def test_entry_validation_is_typed_and_direct(self):
        d,i=self.target_image(struct.pack('<I',0)); self.addCleanup(d.cleanup)
        for entry,message in ((object(),'invalid type'),(SquashFSXAttrEntry(0,decode_xattr_namespace(0),b'n',b'user.n',b'x',1,False,None),'not out-of-line'),(SquashFSXAttrEntry(0x100,decode_xattr_namespace(0),b'n',b'user.n',None,8,True,None),'missing')):
            with self.assertRaisesRegex(SquashFSXAttrValueError,message) as caught: read_xattr_out_of_line_value(i,entry)
            self.assertIsNone(caught.exception.__cause__)
    def test_table_validation_is_typed(self):
        d,i=self.target_image(struct.pack('<I',0)); self.addCleanup(d.cleanup); good=read_xattr_id_table(i)
        cases=(object(),SquashFSXAttrIDTable(good.table_start,good.xattr_table_start,1,(),0),SquashFSXAttrIDTable(good.table_start,-1,1,good.metadata_block_offsets,0),SquashFSXAttrIDTable(good.table_start,good.metadata_block_offsets[0],1,good.metadata_block_offsets,0),SquashFSXAttrIDTable(good.table_start,good.xattr_table_start,1,(good.table_start+1,),0),SquashFSXAttrIDTable(i.read_superblock().bytes_used+1,good.xattr_table_start,1,good.metadata_block_offsets,0))
        for table in cases:
            with self.assertRaises(SquashFSXAttrValueError): read_xattr_out_of_line_value(i,self.entry(),table)
        self.patch(i,40,struct.pack('<Q',i.image.stat().st_size+1))
        with self.assertRaises(SquashFSXAttrValueError): read_xattr_out_of_line_value(i,self.entry(),good)
    def test_reference_bounds_and_invalid_reference_are_typed(self):
        d,i=self.target_image(struct.pack('<I',0)); self.addCleanup(d.cleanup); table=read_xattr_id_table(i); upper=table.metadata_block_offsets[0]-table.xattr_table_start
        for reference in (upper << 16,(upper+1)<<16,0xffffffffffffffff,8192,9000,-1,0x10000000000000000,True):
            with self.assertRaises(SquashFSXAttrValueError): read_xattr_out_of_line_value(i,self.entry(reference),table)
    def test_offset_8191_reaches_typed_header_failure(self):
        d,i=self.target_image(struct.pack('<I',0)); self.addCleanup(d.cleanup)
        with self.assertRaises(SquashFSXAttrValueError): read_xattr_out_of_line_value(i,self.entry(8191))
    def test_each_short_target_header_is_wrapped_with_cause(self):
        for count in range(4):
            d,i=self.target_image(b'\0'*count); self.addCleanup(d.cleanup)
            with self.assertRaisesRegex(SquashFSXAttrValueError,'header') as caught: read_xattr_out_of_line_value(i,self.entry())
            self.assertIsNotNone(caught.exception.__cause__)
    def test_zero_length_and_exact_fit_values(self):
        i,value=self.resolve(struct.pack('<I',0)); self.assertEqual(value,b'')
        i,value=self.resolve(struct.pack('<I',3)+b'\x01\0\xff'); self.assertEqual(value,b'\x01\0\xff')
    def test_impossible_and_huge_declared_sizes_are_typed(self):
        for size in (4,0xffffffff):
            d,i=self.target_image(struct.pack('<I',size)+b'abc'); self.addCleanup(d.cleanup)
            with self.assertRaises(SquashFSXAttrValueError) as caught: read_xattr_out_of_line_value(i,self.entry())
            self.assertNotIsInstance(caught.exception,MemoryError)
    def test_metadata_failure_and_invalid_offset_preserve_cause(self):
        d,i=self.target_image(struct.pack('<I',4)+b'abc'); self.addCleanup(d.cleanup)
        with self.assertRaises(SquashFSXAttrValueError) as caught: read_xattr_out_of_line_value(i,self.entry())
        self.assertIsNotNone(caught.exception.__cause__)
        d,i=self.target_image(struct.pack('<I',0)); self.addCleanup(d.cleanup)
        with self.assertRaises(SquashFSXAttrValueError) as caught: read_xattr_out_of_line_value(i,self.entry(100))
        self.assertIsNone(caught.exception.__cause__)
    def test_stage19_ool_entries_remain_lazy_after_resolution(self):
        d,i=self.list_image(((0x100,b'n',struct.pack('<Q',0)),)); self.addCleanup(d.cleanup)
        entry=read_xattr_list(i,read_xattr_id(i,0)).entries[0]
        self.assertEqual((entry.out_of_line,entry.value,entry.out_of_line_reference),(True,None,0))
        inode=self.extended_inode(0); self.assertIsNone(read_inode_xattrs(i,inode).entries[0].value)

class SquashFSXAttrOutOfLineValueStage20C2Test(_XAttrFixture):
    """Physical multi-block metadata fixtures for Stage 20C2."""
    def metadata_image(self, blocks, reference_block=0, reference_offset=0):
        d=tempfile.TemporaryDirectory(); p=Path(d.name)/'ool-boundary.sqfs'; xstart=128; cursor=xstart; encoded=[]; starts=[]
        for data,compressed in blocks:
            stored=zstandard.ZstdCompressor().compress(data) if compressed else data
            encoded.append(struct.pack('<H',len(stored) if compressed else METADATA_UNCOMPRESSED_BIT|len(stored))+stored); starts.append(cursor); cursor+=len(encoded[-1])
        idmeta=cursor+16; table=idmeta+18; end=table+24; raw=bytearray(end)
        raw[:96]=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,1,0,4096,0,6,12,0,1,4,0,0,end,0,table,0,0,0,0)
        for start,data in zip(starts,encoded): raw[start:start+len(data)]=data
        raw[idmeta:idmeta+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|16); raw[idmeta+2:idmeta+18]=XATTR_ID_STRUCT.pack(0,1,0); raw[table:table+16]=struct.pack('<QII',xstart,1,0); raw[table+16:table+24]=struct.pack('<Q',idmeta); p.write_bytes(raw)
        reference=(starts[reference_block]-xstart)<<16|reference_offset
        return d,SquashFSImage(p),reference
    def resolve_blocks(self, blocks, **kwargs):
        d,i,reference=self.metadata_image(blocks,**kwargs); self.addCleanup(d.cleanup); entry=SquashFSXAttrOutOfLineValueStage20C1Test.entry(reference)
        return read_xattr_out_of_line_value(i,entry),entry
    def test_vsize_boundary_matrix(self):
        payload=b'\x00\xffP'; target=struct.pack('<I',len(payload))+payload
        for split in (0,1,2,3,4):
            first=b'x'*(8192-split)+target[:split]; second=target[split:]
            value,entry=self.resolve_blocks(((first,False),(second,False)),reference_block=1 if split == 0 else 0,reference_offset=0 if split == 0 else 8192-split)
            self.assertEqual(value,payload); self.assertIsNone(entry.value)
    def test_payload_boundary_and_multi_block_matrix(self):
        payload=bytes(range(256))*65; header=struct.pack('<I',len(payload)); first=b'x'*(8192-4)+header; second=payload[:8192]; third=payload[8192:16384]; fourth=payload[16384:]
        value,_=self.resolve_blocks(((first,False),(second,False),(third,False),(fourth,False)),reference_offset=8188)
        self.assertEqual(value,payload)
    def test_header_exact_boundary_and_payload_start_boundary(self):
        payload=b'\x01\0\xff'; first=b'x'*8188+struct.pack('<I',len(payload)); value,_=self.resolve_blocks(((first,False),(payload,False)),reference_offset=8188)
        self.assertEqual(value,payload)
    def test_compressed_and_mixed_metadata_combinations(self):
        payload=bytes(range(64))*3; target=struct.pack('<I',len(payload))+payload
        for flags in ((True,),(True,False),(False,True),(True,True)):
            if len(flags)==1: blocks=((target,flags[0]),)
            else: blocks=((target[:4],flags[0]),(target[4:],flags[1]))
            value,_=self.resolve_blocks(blocks); self.assertEqual(value,payload)
    def test_payload_crosses_multiple_compressed_blocks_and_exact_region_end(self):
        payload=bytes(range(256))*36; header=struct.pack('<I',len(payload)); first=b'x'*8189+header[:3]; second=header[3:]+payload[:8191]; third=payload[8191:]
        value,_=self.resolve_blocks(((first,True),(second,True),(third,True)),reference_offset=8189)
        self.assertEqual(value,payload)
        value,_=self.resolve_blocks(((struct.pack('<I',3)+b'xyz',False),)); self.assertEqual(value,b'xyz')
    def test_offsets_8190_8191_8192_and_upper_bound(self):
        for offset in (8190,8191):
            header=struct.pack('<I',0); first=b'x'*offset+header[:8192-offset]; second=header[8192-offset:]
            value,_=self.resolve_blocks(((first,False),(second,False)),reference_offset=offset); self.assertEqual(value,b'')
        d,i,reference=self.metadata_image(((b'x'*8192,False),(struct.pack('<I',0),False)),reference_offset=8192); self.addCleanup(d.cleanup)
        with self.assertRaises(SquashFSXAttrValueError): read_xattr_out_of_line_value(i,SquashFSXAttrOutOfLineValueStage20C1Test.entry(reference))
    def test_missing_and_corrupt_continuations_are_wrapped(self):
        first=b'x'*8191+struct.pack('<I',1)[:1]
        d,i,reference=self.metadata_image(((first,False),),reference_offset=8191); self.addCleanup(d.cleanup)
        with self.assertRaises(SquashFSXAttrValueError) as caught: read_xattr_out_of_line_value(i,SquashFSXAttrOutOfLineValueStage20C1Test.entry(reference))
        self.assertIsNotNone(caught.exception.__cause__)
    def test_truncated_continuation_variants_and_upper_bound_overrun(self):
        first=b'x'*8191+struct.pack('<I',1)[:1]; second=b'\0\0\0Z'
        for truncate_at in (0,1,2):
            d,i,reference=self.metadata_image(((first,False),(second,False)),reference_offset=8191); self.addCleanup(d.cleanup)
            next_offset=128+2+len(first)
            with i.image.open('r+b') as source: source.truncate(next_offset+truncate_at)
            with self.assertRaises(SquashFSXAttrValueError) as caught: read_xattr_out_of_line_value(i,SquashFSXAttrOutOfLineValueStage20C1Test.entry(reference))
            self.assertIsNotNone(caught.exception.__cause__)
        d,i,reference=self.metadata_image(((struct.pack('<I',4)+b'abc',False),),reference_offset=0); self.addCleanup(d.cleanup)
        with self.assertRaises(SquashFSXAttrValueError) as caught: read_xattr_out_of_line_value(i,SquashFSXAttrOutOfLineValueStage20C1Test.entry(reference))
        self.assertIsNotNone(caught.exception.__cause__)
    def test_compressed_length_and_decoded_size_failures_are_wrapped(self):
        d,i,reference=self.metadata_image(((struct.pack('<I',0),True),),reference_offset=0); self.addCleanup(d.cleanup)
        with i.image.open('r+b') as source: source.seek(128); source.write(b'\xff\x7f')
        with self.assertRaises(SquashFSXAttrValueError) as caught: read_xattr_out_of_line_value(i,SquashFSXAttrOutOfLineValueStage20C1Test.entry(reference))
        self.assertIsNotNone(caught.exception.__cause__)
        huge=zstandard.ZstdCompressor().compress(b'x'*(METADATA_SIZE+1)); d,i,reference=self.metadata_image(((b'x',False),),reference_offset=0); self.addCleanup(d.cleanup)
        with i.image.open('r+b') as source: source.seek(128); source.write(struct.pack('<H',len(huge))+huge)
        with self.assertRaises(SquashFSXAttrValueError) as caught: read_xattr_out_of_line_value(i,SquashFSXAttrOutOfLineValueStage20C1Test.entry(reference))
        self.assertIsNotNone(caught.exception.__cause__)
        d,i,reference=self.metadata_image(((b'not-zstd',True),),reference_offset=0); self.addCleanup(d.cleanup)
        with self.assertRaises(SquashFSXAttrValueError) as caught: read_xattr_out_of_line_value(i,SquashFSXAttrOutOfLineValueStage20C1Test.entry(reference))
        self.assertIsNotNone(caught.exception.__cause__)
    def test_duplicate_references_are_independent(self):
        payload=b'\0\x80duplicate\xff'; d,i,reference=self.metadata_image(((struct.pack('<I',len(payload))+payload,False),)); self.addCleanup(d.cleanup)
        first=SquashFSXAttrOutOfLineValueStage20C1Test.entry(reference); second=SquashFSXAttrOutOfLineValueStage20C1Test.entry(reference)
        self.assertEqual((read_xattr_out_of_line_value(i,first),read_xattr_out_of_line_value(i,second)),(payload,payload)); self.assertIsNone(first.value); self.assertIsNone(second.value)

class SquashFSXAttrOutOfLineValueStage20C3Test(_XAttrFixture):
    """End-to-end Stage 18/19/20 physical XAttr integration fixtures."""
    def integration_image(self):
        d=tempfile.TemporaryDirectory(); p=Path(d.name)/'ool-integration.sqfs'; xstart=128; idmeta=4096; table=5000
        first=b'\0\xffone'; second=b'two\x80\0'; targets=struct.pack('<I',len(first))+first; second_offset=len(targets); targets+=struct.pack('<I',len(second))+second
        def record(typ,name,value): return struct.pack('<HH',typ,len(name))+name+struct.pack('<I',len(value))+value
        list0=record(0,b'inline',b'I\0')+record(0x101,b'trusted',struct.pack('<Q',0))+record(0x102,b'security',struct.pack('<Q',second_offset))+record(0x107,b'unknown',struct.pack('<Q',0))
        list0+=b'\0'*(-len(list0)%4); list1=record(0x100,b'again',struct.pack('<Q',0)); list1+=b'\0'*(-len(list1)%4)
        off0=len(targets); off1=off0+len(list0); payload=targets+list0+list1; ids=XATTR_ID_STRUCT.pack(off0,4,len(list0))+XATTR_ID_STRUCT.pack(off1,1,len(list1)); end=table+24
        raw=bytearray(end); raw[:96]=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,1,0,4096,0,6,12,0,1,4,0,0,end,0,table,0,0,0,0)
        raw[xstart:xstart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(payload)); raw[xstart+2:xstart+2+len(payload)]=payload; raw[idmeta:idmeta+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(ids)); raw[idmeta+2:idmeta+2+len(ids)]=ids
        raw[table:table+16]=struct.pack('<QII',xstart,2,0); raw[table+16:table+24]=struct.pack('<Q',idmeta); p.write_bytes(raw); return d,SquashFSImage(p),(first,second)
    def test_full_id_table_list_value_flow_and_immutability(self):
        d,i,values=self.integration_image(); self.addCleanup(d.cleanup); table=read_xattr_id_table(i); ident=read_xattr_id(i,0,table); listing=read_xattr_list(i,ident,table); before=(listing,listing.entries[1])
        self.assertEqual((ident.index,ident.count,listing.entries[1].out_of_line_reference),(0,4,0)); self.assertEqual(read_xattr_out_of_line_value(i,listing.entries[1],table),values[0]); self.assertEqual((listing,listing.entries[1]),before)
    def test_none_table_mixed_namespaces_and_repeated_calls(self):
        d,i,values=self.integration_image(); self.addCleanup(d.cleanup); listing=read_xattr_list(i,read_xattr_id(i,0),None)
        self.assertEqual([entry.namespace.prefix for entry in listing.entries],[b'user.',b'trusted.',b'security.',None]); self.assertEqual(listing.entries[0].value,b'I\0')
        self.assertEqual([read_xattr_out_of_line_value(i,listing.entries[n],None) for n in (1,2,3)], [values[0],values[1],values[0]])
        self.assertEqual(read_xattr_out_of_line_value(i,listing.entries[1],None),values[0])
    def test_inode_id_zero_nonzero_and_sentinel_remain_lazy(self):
        d,i,values=self.integration_image(); self.addCleanup(d.cleanup)
        self.assertIsNone(read_inode_xattrs(i,self.extended_inode(0xffffffff)))
        zero=read_inode_xattrs(i,self.extended_inode(0)); one=read_inode_xattrs(i,self.extended_inode(1)); self.assertEqual((len(zero.entries),len(one.entries)),(4,1)); self.assertIsNone(zero.entries[1].value)
        self.assertEqual(read_xattr_out_of_line_value(i,zero.entries[1]),values[0]); self.assertEqual(read_xattr_out_of_line_value(i,one.entries[0]),values[0])
    def test_wrong_table_and_public_misuse_are_typed(self):
        d,first,_=self.integration_image(); self.addCleanup(d.cleanup); table=read_xattr_id_table(first); listing=read_xattr_list(first,read_xattr_id(first,0),table)
        d,second=self.xattr_image(); self.addCleanup(d.cleanup)
        with self.assertRaises(SquashFSXAttrValueError): read_xattr_out_of_line_value(second,listing.entries[1],table)
        with self.assertRaises(SquashFSXAttrInodeError): read_inode_xattrs(first,self.extended_inode(9))
    def test_malformed_target_and_zero_reference_contract(self):
        d,i,values=self.integration_image(); self.addCleanup(d.cleanup); entry=read_xattr_list(i,read_xattr_id(i,0)).entries[1]
        self.assertEqual((entry.out_of_line_reference,read_xattr_out_of_line_value(i,entry)),(0,values[0]))
        self.patch(i,128,b'\0\0')
        with self.assertRaises(SquashFSXAttrValueError) as caught: read_xattr_out_of_line_value(i,entry)
        self.assertIsNotNone(caught.exception.__cause__)

class SquashFSXAttrListReaderTest(_XAttrFixture):
    def test_one_entry(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:self.assertEqual(len(read_xattr_list(i,read_xattr_id(i,0)).entries),1)
    def test_multiple_entries(self):
        d,i=self.list_image(((0,b'a',b'1'),(2,b'b',b'22')))
        with d:self.assertEqual(len(read_xattr_list(i,read_xattr_id(i,0)).entries),2)
    def test_mixed_namespaces(self):
        d,i=self.list_image(((0,b'a',b'1'),(1,b'b',b'2'),(2,b'c',b'3')))
        with d:self.assertEqual([e.namespace.prefix for e in read_xattr_list(i,read_xattr_id(i,0)).entries],[b'user.',b'trusted.',b'security.'])
    def test_mixed_inline_and_ool_entries(self):
        d,i=self.list_image(((0,b'a',b'1'),(0x101,b'b',struct.pack('<Q',2))))
        with d:self.assertEqual([e.out_of_line for e in read_xattr_list(i,read_xattr_id(i,0)).entries],[False,True])
    def test_entry_order_is_preserved(self):
        d,i=self.list_image(((0,b'first',b'1'),(0,b'second',b'2')))
        with d:self.assertEqual([e.name for e in read_xattr_list(i,read_xattr_id(i,0)).entries],[b'first',b'second'])
    def test_exact_declared_count(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).xattr_id.count,1)
    def test_declared_count_smaller_than_entry_data_is_rejected(self):
        entries=((0,b'a',b'1'),(0,b'b',b'2')); d,i=self.list_image(entries,ids=((0,1,20),))
        with d:
            with self.assertRaisesRegex(SquashFSXAttrListError,'size does not match'):read_xattr_list(i,read_xattr_id(i,0))
    def test_declared_count_larger_than_available_entries_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'1'),),ids=((0,2,10),))
        with d:self.assertRaises(SquashFSXAttrEntryError,read_xattr_list,i,read_xattr_id(i,0))
    def test_zero_declared_count_with_zero_declared_size(self):
        d,i=self.list_image((),ids=((0,0,0),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries,())
    def test_zero_declared_count_with_trailing_data_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'1'),),ids=((0,0,10),))
        with d:
            with self.assertRaisesRegex(SquashFSXAttrListError,'size does not match'):read_xattr_list(i,read_xattr_id(i,0))
    def test_exact_declared_size(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            value=read_xattr_list(i,read_xattr_id(i,0)); self.assertEqual(value.consumed_size,value.xattr_id.size)
    def test_zero_alignment_padding_is_accepted_without_changing_consumed_size(self):
        raw=struct.pack('<HH',0,1)+b'a'+struct.pack('<I',1)+b'v'+b'\0\0'; d,i,_=self.boundary_list_image(raw,1,len(raw),0)
        with d:
            value=read_xattr_list(i,read_xattr_id(i,0)); self.assertEqual((value.consumed_size,value.xattr_id.size),(10,12))
    def test_declared_size_smaller_than_consumed_entry_bytes_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'v'),),ids=((0,1,1),))
        with d:
            with self.assertRaisesRegex(SquashFSXAttrListError,'size does not match'):read_xattr_list(i,read_xattr_id(i,0))
    def test_declared_size_larger_than_available_metadata_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'v'),),ids=((0,1,0xffff),))
        with d:self.assertRaises(SquashFSXAttrListError,read_xattr_list,i,read_xattr_id(i,0))
    def test_declared_size_larger_than_consumed_with_trailing_bytes_is_rejected(self):
        raw=struct.pack('<HH',0,1)+b'a'+struct.pack('<I',1)+b'v'+b'x'; d,i,_=self.boundary_list_image(raw,1,len(raw),0)
        with d:
            with self.assertRaisesRegex(SquashFSXAttrListError,'size does not match'):read_xattr_list(i,read_xattr_id(i,0))
    def test_one_trailing_byte_after_final_entry_is_rejected(self):
        raw=struct.pack('<HH',0,1)+b'a'+struct.pack('<I',1)+b'v'+b'x'; d,i,_=self.boundary_list_image(raw,1,len(raw),0)
        with d:self.assertRaises(SquashFSXAttrListError,read_xattr_list,i,read_xattr_id(i,0))
    def test_multiple_trailing_bytes_after_final_entry_are_rejected(self):
        raw=struct.pack('<HH',0,1)+b'a'+struct.pack('<I',1)+b'v'+b'xyz'; d,i,_=self.boundary_list_image(raw,1,len(raw),0)
        with d:self.assertRaises(SquashFSXAttrListError,read_xattr_list,i,read_xattr_id(i,0))
    def test_consumed_size_is_exact(self):
        d,i=self.list_image(((0,b'a',b'1'),(2,b'b',b'22')))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).consumed_size,21)
    def test_declared_count_is_preserved(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).xattr_id.count,1)
    def test_declared_size_is_preserved(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).xattr_id.size,10)
    def test_list_entries_are_an_immutable_tuple(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:self.assertIsInstance(read_xattr_list(i,read_xattr_id(i,0)).entries,tuple)
    def test_list_model_is_immutable(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            value=read_xattr_list(i,read_xattr_id(i,0))
            with self.assertRaises(AttributeError):value.consumed_size=0
    def test_id_zero_is_valid(self):
        d,i=self.list_image(((0,b'a',b'zero'),))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,0)).entries[0].value,b'zero')
    def test_nonzero_valid_id_is_valid(self):
        d,i=self.multi_list_image((((0,b'a',b'zero'),),((0,b'b',b'one'),)))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,1)).entries[0].value,b'one')
    def test_selected_record_matches_requested_id(self):
        d,i=self.multi_list_image((((0,b'a',b'zero'),),((0,b'b',b'one'),)))
        with d:self.assertEqual(read_xattr_list(i,read_xattr_id(i,1)).xattr_id.index,1)
    def test_invalid_id_below_zero_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:self.assertRaises(SquashFSXAttrIDError,read_xattr_id,i,-1)
    def test_invalid_id_equal_to_table_count_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:self.assertRaises(SquashFSXAttrIDError,read_xattr_id,i,1)
    def test_invalid_id_larger_than_table_count_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:self.assertRaises(SquashFSXAttrIDError,read_xattr_id,i,2)
    def test_absent_xattr_table_is_rejected(self):
        d,i=self.xattr_image(absent=True)
        with d:self.assertRaises(SquashFSXAttrTableError,read_xattr_id,i,0)
    def test_empty_xattr_id_table_is_rejected(self):
        d,i=self.xattr_image(())
        with d:self.assertRaises(SquashFSXAttrTableError,read_xattr_id,i,0)
    def test_malformed_id_record_is_wrapped(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,4096,struct.pack('<H',METADATA_UNCOMPRESSED_BIT|2))
            with self.assertRaises(SquashFSXAttrIDError) as caught:read_xattr_id(i,0)
            self.assertIsInstance(caught.exception.__cause__,SquashFSMetadataStreamError)
    def test_malformed_list_metadata_is_wrapped(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,128,b'\0\0')
            with self.assertRaises(SquashFSXAttrEntryError) as caught:read_xattr_list(i,read_xattr_id(i,0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSMetadataStreamError)
    def test_public_typed_list_error_is_raised(self):
        d,i=self.list_image(((0,b'a',b'v'),),ids=((0,1,1),))
        with d:self.assertRaises(SquashFSXAttrListError,read_xattr_list,i,read_xattr_id(i,0))
    def test_lower_metadata_cause_is_preserved(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,128,b'\0\0')
            with self.assertRaises(SquashFSXAttrListError) as caught:read_xattr_list(i,read_xattr_id(i,0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSMetadataStreamError)
    def test_count_mismatch_and_size_mismatch_have_distinct_messages(self):
        d,i=self.list_image(((0,b'a',b'v'),),ids=((0,2,10),))
        with d:
            with self.assertRaises(SquashFSXAttrEntryError) as count_error:read_xattr_list(i,read_xattr_id(i,0))
            self.assertIn('entry 1',str(count_error.exception))
        d,i=self.list_image(((0,b'a',b'v'),),ids=((0,1,1),))
        with d:
            with self.assertRaises(SquashFSXAttrListError) as size_error:read_xattr_list(i,read_xattr_id(i,0))
            self.assertIn('size does not match',str(size_error.exception))
    def test_id_zero_is_not_treated_as_absent(self):
        d,i=self.list_image(((0,b'a',b'zero'),))
        with d:self.assertIsNotNone(read_xattr_list(i,read_xattr_id(i,0)))
    def test_list_parsing_is_lazy_until_requested(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            with patch.object(i,'read_metadata_block',wraps=i.read_metadata_block) as reads:
                read_xattr_id(i,0)
                self.assertNotIn(128,[call.args[0] for call in reads.call_args_list])
                read_xattr_list(i,read_xattr_id(i,0))
                self.assertIn(128,[call.args[0] for call in reads.call_args_list])

class SquashFSXAttrInodeListIntegrationTest(_XAttrFixture):
    def test_inode_without_xattr_id_returns_none(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            body=SquashFSBasicRegularInode(SquashFSInodeHeader(2,0,0,0,0,1),0,0,0,0)
            inode=SquashFSInode(SquashFSMetadataReference(0,0),body.header,body)
            self.assertIsNone(read_inode_xattrs(i,inode))
    def test_inode_without_xattr_id_performs_no_metadata_read(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            body=SquashFSBasicRegularInode(SquashFSInodeHeader(2,0,0,0,0,1),0,0,0,0); inode=SquashFSInode(SquashFSMetadataReference(0,0),body.header,body)
            with patch.object(i,'read_metadata_block',wraps=i.read_metadata_block) as reads:
                self.assertIsNone(read_inode_xattrs(i,inode)); self.assertEqual(reads.call_count,0)
    def test_inode_id_zero_returns_id_zero_list(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            inode=self.extended_inode(0)
            self.assertEqual(read_inode_xattrs(i,inode).entries[0].value,b'v')
    def test_inode_nonzero_id_returns_matching_list(self):
        d,i=self.multi_list_image((((0,b'a',b'zero'),),((0,b'b',b'one'),)))
        with d:self.assertEqual(read_inode_xattrs(i,self.extended_inode(1)).entries[0].value,b'one')
    def test_two_inodes_with_different_ids_select_different_lists(self):
        d,i=self.multi_list_image((((0,b'a',b'zero'),),((0,b'b',b'one'),)))
        with d:self.assertEqual([read_inode_xattrs(i,self.extended_inode(n)).entries[0].value for n in (0,1)],[b'zero',b'one'])
    def test_selected_entries_match_inode_id_record(self):
        d,i=self.multi_list_image((((0,b'a',b'zero'),),((0,b'b',b'one'),)))
        with d:
            value=read_inode_xattrs(i,self.extended_inode(1)); self.assertEqual((value.xattr_id.index,value.entries[0].name),(1,b'b'))
    def test_invalid_inode_xattr_id_is_rejected(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            with self.assertRaises(SquashFSXAttrInodeError) as caught:read_inode_xattrs(i,self.extended_inode(1))
            self.assertIsInstance(caught.exception.__cause__,SquashFSXAttrIDError)
    def test_missing_xattr_table_for_inode_is_rejected(self):
        d,i=self.xattr_image(absent=True)
        with d:
            with self.assertRaises(SquashFSXAttrInodeError) as caught:read_inode_xattrs(i,self.extended_inode(0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSXAttrTableError)
    def test_physical_inode_parsing_is_lazy(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            with patch.object(i,'read_metadata_block',wraps=i.read_metadata_block) as reads:
                inode=self.parsed_extended_inode(i,0); self.assertEqual(inode.body.xattr_id,0); self.assertNotIn(128,[call.args[0] for call in reads.call_args_list])
    def test_parsing_inode_does_not_eagerly_parse_xattr_list(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            with patch.object(i,'read_metadata_block',wraps=i.read_metadata_block) as reads:
                self.extended_inode(0); self.assertNotIn(128,[call.args[0] for call in reads.call_args_list])
    def test_read_inode_xattrs_accesses_list_when_requested(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            inode=self.extended_inode(0)
            with patch.object(i,'read_metadata_block',wraps=i.read_metadata_block) as reads:
                read_inode_xattrs(i,inode); self.assertIn(128,[call.args[0] for call in reads.call_args_list])
    def test_sentinel_xattr_decodes_to_none(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:self.assertIsNone(self.parsed_extended_inode(i,0xffffffff).body.xattr_id)
    def test_valid_id_zero_remains_zero(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:self.assertEqual(self.parsed_extended_inode(i,0).body.xattr_id,0)
    def test_sentinel_is_never_resolved_as_table_id(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            with patch.object(i,'read_metadata_block',wraps=i.read_metadata_block) as reads:
                self.assertIsNone(read_inode_xattrs(i,self.extended_inode(0xffffffff)))
                self.assertEqual(reads.call_count,0)
    def test_id_table_error_is_wrapped_through_inode_api(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,4096,b'\0\0')
            with self.assertRaises(SquashFSXAttrInodeError) as caught:read_inode_xattrs(i,self.extended_inode(0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSXAttrIDError)
    def test_list_metadata_error_is_wrapped_through_inode_api(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,128,b'\0\0')
            with self.assertRaises(SquashFSXAttrInodeError) as caught:read_inode_xattrs(i,self.extended_inode(0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSXAttrEntryError)
    def test_inode_error_preserves_exact_cause_type(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,128,b'\0\0')
            with self.assertRaises(SquashFSXAttrInodeError) as caught:read_inode_xattrs(i,self.extended_inode(0))
            self.assertIsInstance(caught.exception.__cause__,SquashFSXAttrEntryError)
    def test_inode_without_xattr_id_ignores_malformed_metadata(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,128,b'\0\0')
            self.assertIsNone(read_inode_xattrs(i,self.extended_inode(0xffffffff)))
    def test_inode_with_xattr_id_fails_for_malformed_selected_list(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            self.patch(i,128,b'\0\0')
            with self.assertRaises(SquashFSXAttrInodeError):read_inode_xattrs(i,self.extended_inode(0))
    def test_nonxattr_basic_inode_behavior_is_unchanged(self):
        d,i=self.list_image(((0,b'a',b'v'),))
        with d:
            body=SquashFSBasicRegularInode(SquashFSInodeHeader(2,0,0,0,0,1),0,0,0,0); inode=SquashFSInode(SquashFSMetadataReference(0,0),body.header,body)
            self.assertIsInstance(inode.body,SquashFSBasicRegularInode)

if __name__ == "__main__":
    unittest.main()
