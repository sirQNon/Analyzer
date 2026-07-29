"""Stage 1 regression test for the extracted UDM SquashFS image."""

import struct
import tempfile
import unittest
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
    DIRECTORY_ENTRY_SIZE,
    DIRECTORY_ENTRY_STRUCT,
    DIRECTORY_HEADER_SIZE,
    DIRECTORY_HEADER_STRUCT,
    DIRECTORY_NAME_MAX,
    DIRECTORY_POSITION_OFFSET,
    INODE_HEADER_SIZE,
    INODE_HEADER_STRUCT,
    METADATA_UNCOMPRESSED_BIT,
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
    SquashFSDirectoryEntry,
    SquashFSDirectoryError,
    SquashFSDirectoryHeader,
    SquashFSDirectoryReaderError,
    SquashFSDirectoryRecord,
    SquashFSInodeHeader,
    SquashFSDataBlockDecompressionError,
    SquashFSDataBlockSizeError,
    SquashFSDataBlockTruncatedError,
    SquashFSFragmentFileUnsupportedError,
    SquashFSMalformedBlockListError,
    SquashFSImage,
    SquashFSMetadataError,
    SquashFSMetadataReference,
    SquashFSMetadataStream,
    SquashFSMetadataStreamError,
    SquashFSUnsupportedInodeTypeError,
    SquashFSSymlinkError,
    basic_regular_file_block_count,
    decode_metadata_reference,
    directory_entry_reference,
    parse_basic_directory_inode,
    parse_basic_symlink_inode,
    parse_directory_entry,
    parse_directory_header,
    parse_inode_header,
    parse_regular_file_block_size_entry,
    read_basic_regular_file,
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
        for inode_type in (9, 99):
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

    def test_fragment_backed_regular_file_is_rejected_and_empty_file_is_empty(self):
        fragment_metadata = self.regular_inode_bytes(1, fragment=7)
        directory, image, stream = self.make_image((fragment_metadata,), b"")
        with directory:
            with self.assertRaises(SquashFSFragmentFileUnsupportedError):
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


if __name__ == "__main__":
    unittest.main()
