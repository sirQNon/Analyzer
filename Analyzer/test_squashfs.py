"""Stage 1 regression test for the extracted UDM SquashFS image."""

import struct
import tempfile
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from types import MappingProxyType
from unittest.mock import patch
from pathlib import Path

import zstandard
import squashfs

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
    SquashFSRegularFileError,
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
    decode_linux_file_capabilities, LinuxCapabilityRevision, LinuxCapabilityError,
    LinuxCapabilityTypeError, LinuxCapabilitySizeError, LinuxCapabilityRevisionError,
    LinuxCapabilityFlagsError, VFS_CAP_REVISION_1, VFS_CAP_REVISION_2,
    VFS_CAP_REVISION_3, VFS_CAP_FLAGS_EFFECTIVE,
    VFS_CAP_REVISION_MASK, VFS_CAP_FLAGS_MASK, XATTR_CAPS_SZ_1,
    XATTR_CAPS_SZ_2, XATTR_CAPS_SZ_3, LinuxCapabilitySet,
    VFS_CAP_U32_1, VFS_CAP_U32_2,
    LINUX_CAPABILITY_NAMES, LINUX_CAP_LAST_KNOWN,
    XAttrSemanticKind, XAttrSemanticError, XAttrSemanticTypeError,
    XAttrSemanticDecoderError, UnknownXAttrSemanticValue, XAttrSemanticDecoder,
    XAttrSemanticValueResolutionError, DecodedXAttr, XATTR_SEMANTIC_DECODERS,
    decode_xattr_semantic, read_and_decode_xattr,
    SquashFSNodeType, SquashFSInodeIdentity, SquashFSFilesystem,
    SquashFSPathNode, SquashFSDirectoryNode, SquashFSRegularFileNode,
    SquashFSSymlinkNode, SquashFSUnsupportedNode,
    SquashFSDirectoryListing, SquashFSDirectoryReadError, SquashFSChildInodeError,
    SquashFSDirectoryEntryError, list_children,
    SquashFSFilesystemGraphError, SquashFSRootError, SquashFSNodeTypeError,
    SquashFSPathError, SquashFSPathNotFoundError, SquashFSNotDirectoryError,
    SquashFSDuplicateNameError, SquashFSDirectoryCycleError,
    SquashFSFilesystemIndexError, SquashFSNodeContentError,
    SquashFSFilesystemIndex, open_filesystem, get_root, lookup_path,
    walk_filesystem, build_filesystem_index, node_for_path, paths_for_inode,
    read_node_bytes, read_node_symlink, read_node_xattrs,
)


ROOT = Path(__file__).resolve().parent.parent
ROOTFS = ROOT / "Extracted" / "rootfs"

class LinuxFileCapabilitiesStage21BTest(unittest.TestCase):
    def decode(self, revision, words=(0,0,0,0), root=None, flags=0):
        values=[revision|flags,*words[:2]]
        if revision != VFS_CAP_REVISION_1: values.extend(words[2:4])
        if revision == VFS_CAP_REVISION_3: values.append(root if root is not None else 0)
        return decode_linux_file_capabilities(struct.pack('<'+'I'*len(values),*values))
    def test_revisions_masks_and_sets(self):
        one=self.decode(VFS_CAP_REVISION_1,(3,4)); self.assertEqual((one.revision,one.permitted.capability_numbers,one.inheritable.capability_numbers),(LinuxCapabilityRevision.REVISION_1,(0,1),(2,)))
        two=self.decode(VFS_CAP_REVISION_2,(1,0,0,0x80000000),flags=VFS_CAP_FLAGS_EFFECTIVE); self.assertEqual((two.effective,two.inheritable.capability_numbers),(True,(63,)))
    def test_revision3_rootids_and_rootfs_fixture(self):
        self.assertEqual(self.decode(VFS_CAP_REVISION_3,root=0xffffffff).root_id,0xffffffff)
        value=decode_linux_file_capabilities(bytes.fromhex('0100000200200000000000000000000000000000')); self.assertEqual((value.revision,value.effective,value.permitted.raw_mask,value.permitted.capability_numbers,value.root_id),(LinuxCapabilityRevision.REVISION_2,True,0x2000,(13,),None))
    def test_bytes_like_is_copied_and_models_frozen(self):
        raw=bytearray(struct.pack('<III',VFS_CAP_REVISION_1,1,0)); value=decode_linux_file_capabilities(memoryview(raw)); raw[4]=0
        self.assertEqual(value.permitted.raw_mask,1)
        with self.assertRaises(AttributeError): value.raw_flags=0
        with self.assertRaises(AttributeError): value.permitted.raw_mask=0
    def test_errors_are_typed(self):
        for raw,error in (('x',LinuxCapabilityTypeError),(b'',LinuxCapabilitySizeError),(b'\0',LinuxCapabilitySizeError),(struct.pack('<I',0x99000000),LinuxCapabilityRevisionError),(struct.pack('<III',VFS_CAP_REVISION_1|2,0,0),LinuxCapabilityFlagsError),(struct.pack('<IIIII',VFS_CAP_REVISION_1,0,0,0,0),LinuxCapabilitySizeError)):
            with self.assertRaises(error) as caught: decode_linux_file_capabilities(raw)
            self.assertIsInstance(caught.exception,LinuxCapabilityError)
    def test_repeated_results_and_independent_sets(self):
        raw=struct.pack('<IIIII',VFS_CAP_REVISION_2,5,0,0,0); self.assertEqual(decode_linux_file_capabilities(raw),decode_linux_file_capabilities(raw))
    def test_constants_sizes_and_all_exact_size_mismatches(self):
        self.assertEqual((VFS_CAP_REVISION_MASK,VFS_CAP_FLAGS_MASK,XATTR_CAPS_SZ_1,XATTR_CAPS_SZ_2,XATTR_CAPS_SZ_3),(0xff000000,0x00ffffff,12,20,24))
        for revision,size in ((VFS_CAP_REVISION_1,20),(VFS_CAP_REVISION_2,12),(VFS_CAP_REVISION_3,20)):
            with self.assertRaises(LinuxCapabilitySizeError): decode_linux_file_capabilities(struct.pack('<I',revision)+b'\0'*(size-4))
    def test_flags_masks_and_direct_model_invariants(self):
        with self.assertRaises(LinuxCapabilityFlagsError): decode_linux_file_capabilities(struct.pack('<III',VFS_CAP_REVISION_1|VFS_CAP_FLAGS_EFFECTIVE|2,0,0))
        with self.assertRaises(ValueError): LinuxCapabilitySet(-1,(),(),())
        with self.assertRaises(ValueError): LinuxCapabilitySet(3,(1,0,1),(),())
    def test_every_structural_constant_has_linux_value(self):
        self.assertEqual((VFS_CAP_REVISION_MASK,VFS_CAP_REVISION_1,VFS_CAP_REVISION_2,VFS_CAP_REVISION_3),(0xff000000,0x01000000,0x02000000,0x03000000))
        self.assertEqual((VFS_CAP_FLAGS_MASK,VFS_CAP_FLAGS_EFFECTIVE,VFS_CAP_U32_1,VFS_CAP_U32_2),(0x00ffffff,1,1,2))
        self.assertEqual((XATTR_CAPS_SZ_1,XATTR_CAPS_SZ_2,XATTR_CAPS_SZ_3),(12,20,24))
    def test_zero_sets_effective_clear_and_raw_fields(self):
        for revision in (VFS_CAP_REVISION_1,VFS_CAP_REVISION_2,VFS_CAP_REVISION_3):
            value=self.decode(revision,root=0); self.assertFalse(value.effective); self.assertEqual((value.permitted.raw_mask,value.inheritable.raw_mask),(0,0)); self.assertEqual(value.root_id,0 if revision==VFS_CAP_REVISION_3 else None)
            self.assertEqual((value.raw_magic_etc,value.raw_flags,value.raw_value,type(value.raw_value)),(revision,0,bytes(value.raw_value),bytes))
    def test_revision2_independence_and_revision_ranges(self):
        value=self.decode(VFS_CAP_REVISION_2,(0,2,0x80000000,0)); self.assertEqual((value.permitted.capability_numbers,value.inheritable.capability_numbers),((63,),(1,)))
        self.assertTrue(all(bit <= 31 for bit in self.decode(VFS_CAP_REVISION_1,(0xffffffff,0xffffffff)).permitted.capability_numbers))
        self.assertEqual(self.decode(VFS_CAP_REVISION_3,(0,0,0x80000000,0)).permitted.capability_numbers,(63,))
    def test_bytearray_and_all_short_lengths(self):
        raw=bytearray(struct.pack('<III',VFS_CAP_REVISION_1,1,0)); value=decode_linux_file_capabilities(raw); raw[4]=0
        self.assertEqual((value.raw_value,value.permitted.raw_mask),(struct.pack('<III',VFS_CAP_REVISION_1,1,0),1))
        for raw in (b'\0',b'\0\0',b'\0\0\0'):
            with self.assertRaises(LinuxCapabilitySizeError): decode_linux_file_capabilities(raw)
        with self.assertRaises(LinuxCapabilityTypeError): decode_linux_file_capabilities(object())
    def test_trailing_data_and_controlled_unpack_cause(self):
        for revision in (VFS_CAP_REVISION_1,VFS_CAP_REVISION_2,VFS_CAP_REVISION_3):
            raw=self.decode(revision).raw_value+b'x'
            with self.assertRaises(LinuxCapabilitySizeError): decode_linux_file_capabilities(raw)
        valid=struct.pack('<IIIII',VFS_CAP_REVISION_2,0,0,0,0)
        with patch.object(squashfs.struct,'unpack',side_effect=struct.error('forced')):
            with self.assertRaises(LinuxCapabilitySizeError) as caught: decode_linux_file_capabilities(valid)
        self.assertIsInstance(caught.exception.__cause__,struct.error)


class XAttrSemanticDispatchStage22BTest(unittest.TestCase):
    RAW = struct.pack('<III', VFS_CAP_REVISION_1, 1, 0)

    def entry(self, full_name=b'security.capability'):
        return SquashFSXAttrEntry(
            2, decode_xattr_namespace(2), b'capability', full_name,
            b'inline', len(b'inline'), False, None,
        )

    def test_public_api_registry_and_descriptor_contract(self):
        self.assertTrue(callable(decode_xattr_semantic))
        self.assertEqual(tuple(XATTR_SEMANTIC_DECODERS), (b'security.capability',))
        descriptor = XATTR_SEMANTIC_DECODERS[b'security.capability']
        self.assertEqual(
            (descriptor.decoder_id, descriptor.kind, descriptor.decode),
            ('linux.security.capability', XAttrSemanticKind.LINUX_FILE_CAPABILITIES,
             decode_linux_file_capabilities),
        )
        with self.assertRaises(TypeError):
            XATTR_SEMANTIC_DECODERS[b'x'] = descriptor
        with self.assertRaises(AttributeError):
            descriptor.decoder_id = 'changed'

    def test_known_capability_result_and_raw_provenance(self):
        entry = self.entry()
        result = decode_xattr_semantic(entry, self.RAW)
        self.assertEqual(
            (result.entry, result.raw_value, result.kind, result.decoder_id, result.known),
            (entry, self.RAW, XAttrSemanticKind.LINUX_FILE_CAPABILITIES,
             'linux.security.capability', True),
        )
        self.assertIsInstance(result.semantic_value, squashfs.LinuxFileCapabilities)
        self.assertEqual(result.semantic_value, decode_linux_file_capabilities(self.RAW))
        with self.assertRaises(AttributeError):
            result.known = False

    def test_all_bytes_like_inputs_are_normalized_and_copied(self):
        for raw in (self.RAW, bytearray(self.RAW), memoryview(self.RAW)):
            result = decode_xattr_semantic(self.entry(), raw)
            self.assertEqual((result.raw_value, type(result.raw_value)), (self.RAW, bytes))
        mutable = bytearray(self.RAW)
        result = decode_xattr_semantic(self.entry(), mutable)
        mutable[4] = 0
        self.assertEqual(result.raw_value, self.RAW)

    def test_invalid_public_arguments_are_typed(self):
        for entry, raw in ((object(), self.RAW), (self.entry(), 'not-bytes'),
                           (self.entry(), object())):
            with self.assertRaises(XAttrSemanticTypeError) as caught:
                decode_xattr_semantic(entry, raw)
            self.assertIsInstance(caught.exception, XAttrSemanticError)
        invalid_name_entry = SquashFSXAttrEntry(
            2, decode_xattr_namespace(2), b'capability', 'security.capability',
            b'', 0, False, None,
        )
        with self.assertRaises(XAttrSemanticTypeError):
            decode_xattr_semantic(invalid_name_entry, self.RAW)

    def test_unknown_names_preserve_exact_binary_provenance(self):
        for full_name in (b'user.note', None, b'security.Capability',
                          b'security.capability.extra', b'trusted.capability',
                          b'\xff\x00name'):
            result = decode_xattr_semantic(self.entry(full_name), b'\x00\xffdata')
            self.assertEqual(
                (result.known, result.kind, result.decoder_id, result.raw_value),
                (False, XAttrSemanticKind.UNKNOWN, None, b'\x00\xffdata'),
            )
            self.assertIsInstance(result.semantic_value, UnknownXAttrSemanticValue)
            self.assertEqual(
                (result.semantic_value.full_name, result.semantic_value.raw_value),
                (full_name, b'\x00\xffdata'),
            )

    def test_unknown_and_known_results_are_immutable_and_equal(self):
        unknown = decode_xattr_semantic(self.entry(b'user.note'), b'value')
        self.assertEqual(unknown, decode_xattr_semantic(self.entry(b'user.note'), b'value'))
        self.assertEqual(decode_xattr_semantic(self.entry(), self.RAW),
                         decode_xattr_semantic(self.entry(), self.RAW))
        with self.assertRaises(AttributeError):
            unknown.semantic_value.raw_value = b'changed'

    def test_capability_failure_is_wrapped_with_original_cause(self):
        with self.assertRaises(XAttrSemanticDecoderError) as caught:
            decode_xattr_semantic(self.entry(), b'')
        self.assertIsInstance(caught.exception.__cause__, LinuxCapabilityError)
        self.assertNotIsInstance(caught.exception, LinuxCapabilityError)

    def test_direct_model_and_descriptor_invariants_reject_invalid_states(self):
        entry = self.entry()
        unknown = UnknownXAttrSemanticValue(entry.full_name, b'value')
        capability = decode_linux_file_capabilities(self.RAW)
        with self.assertRaises(ValueError):
            UnknownXAttrSemanticValue('text', b'value')
        with self.assertRaises(ValueError):
            UnknownXAttrSemanticValue(entry.full_name, bytearray(b'value'))
        with self.assertRaises(ValueError):
            DecodedXAttr(object(), b'value', XAttrSemanticKind.LINUX_FILE_CAPABILITIES,
                         'id', True, capability)
        with self.assertRaises(ValueError):
            DecodedXAttr(entry, bytearray(b'value'), XAttrSemanticKind.LINUX_FILE_CAPABILITIES,
                         'id', True, capability)
        with self.assertRaises(ValueError):
            DecodedXAttr(entry, b'value', 'not-a-kind', 'id', True, capability)
        with self.assertRaises(ValueError):
            DecodedXAttr(entry, b'value', XAttrSemanticKind.LINUX_FILE_CAPABILITIES,
                         'id', 1, capability)
        with self.assertRaises(ValueError):
            DecodedXAttr(entry, b'value', XAttrSemanticKind.UNKNOWN, None, True, unknown)
        with self.assertRaises(ValueError):
            DecodedXAttr(entry, b'value', XAttrSemanticKind.LINUX_FILE_CAPABILITIES,
                         None, True, object())
        with self.assertRaises(ValueError):
            DecodedXAttr(entry, b'value', XAttrSemanticKind.LINUX_FILE_CAPABILITIES,
                         'id', True, unknown)
        with self.assertRaises(ValueError):
            DecodedXAttr(entry, b'value', XAttrSemanticKind.UNKNOWN, 'x', False, unknown)
        with self.assertRaises(ValueError):
            DecodedXAttr(entry, b'other', XAttrSemanticKind.UNKNOWN, None, False, unknown)
        with self.assertRaises(ValueError):
            DecodedXAttr(entry, b'value', XAttrSemanticKind.UNKNOWN, None, False, object())
        with self.assertRaises(ValueError):
            DecodedXAttr(self.entry(b'user.note'), b'value', XAttrSemanticKind.UNKNOWN,
                         None, False, unknown)
        for args in (('', XAttrSemanticKind.LINUX_FILE_CAPABILITIES, lambda value: value),
                     ('id', XAttrSemanticKind.UNKNOWN, lambda value: value),
                     ('id', XAttrSemanticKind.LINUX_FILE_CAPABILITIES, object())):
            with self.assertRaises(ValueError):
                XAttrSemanticDecoder(*args)

    def test_dispatcher_has_no_transport_or_host_access(self):
        with (patch.object(squashfs, 'read_xattr_out_of_line_value',
                           side_effect=AssertionError('OOL access')),
              patch.object(squashfs, 'read_xattr_list',
                           side_effect=AssertionError('list access')),
              patch.object(squashfs, 'read_inode_xattrs',
                           side_effect=AssertionError('inode access'))):
            self.assertTrue(decode_xattr_semantic(self.entry(), self.RAW).known)


class XAttrSemanticTransportStage22C2Test(unittest.TestCase):
    RAW = struct.pack('<III', VFS_CAP_REVISION_1, 1, 0)

    def target_image(self, payload):
        target = struct.pack('<I', len(payload)) + payload
        directory = tempfile.TemporaryDirectory(); path = Path(directory.name) / 'semantic-ool.sqfs'
        xstart = 128; idmeta = xstart + 2 + len(target) + 16; table = idmeta + 18; end = table + 24
        raw = bytearray(end)
        raw[:96] = struct.pack('<IIIIIHHHHHHQQQQQQQQ', SQUASHFS_MAGIC, 1, 0, 4096, 0, 6, 12, 0, 1, 4, 0, 0, end, 0, table, 0, 0, 0, 0)
        raw[xstart:xstart + 2] = struct.pack('<H', METADATA_UNCOMPRESSED_BIT | len(target))
        raw[xstart + 2:xstart + 2 + len(target)] = target
        raw[idmeta:idmeta + 2] = struct.pack('<H', METADATA_UNCOMPRESSED_BIT | 16)
        raw[idmeta + 2:idmeta + 18] = XATTR_ID_STRUCT.pack(0, 1, 0)
        raw[table:table + 16] = struct.pack('<QII', xstart, 1, 0)
        raw[table + 16:table + 24] = struct.pack('<Q', idmeta)
        path.write_bytes(raw)
        self.addCleanup(directory.cleanup)
        return SquashFSImage(path)

    @staticmethod
    def inline_entry(name=b'security.capability', value=RAW):
        return SquashFSXAttrEntry(2, decode_xattr_namespace(2), b'capability', name,
                                  value, len(value), False, None)

    @staticmethod
    def ool_entry(name=b'security.capability', reference=0):
        return SquashFSXAttrEntry(0x102, decode_xattr_namespace(2), b'capability', name,
                                  None, 8, True, reference)

    def test_public_inline_path_is_lazy_immutable_and_ignores_table(self):
        image = self.target_image(b'unused')
        entry = self.inline_entry(); before = entry; table = read_xattr_id_table(image)
        with (patch.object(squashfs, 'read_xattr_out_of_line_value', side_effect=AssertionError('OOL')),
              patch.object(squashfs, 'read_xattr_list', side_effect=AssertionError('list')),
              patch.object(squashfs, 'read_inode_xattrs', side_effect=AssertionError('inode')),
              patch.object(image, 'read_metadata_block', side_effect=AssertionError('metadata'))):
            result = read_and_decode_xattr(image, entry, table)
        self.assertIsInstance(result, DecodedXAttr)
        self.assertEqual((result.entry, result.raw_value, result.known), (entry, self.RAW, True))
        self.assertEqual(entry, before)
        self.assertEqual(result, read_and_decode_xattr(image, entry, table))
        self.assertEqual(result, read_and_decode_xattr(image, entry))
        with self.assertRaises(AttributeError): result.raw_value = b'changed'

    def test_inline_unknown_and_malformed_states_are_typed(self):
        image = self.target_image(b'unused')
        unknown = read_and_decode_xattr(image, self.inline_entry(b'user.note', b'\0\xff'))
        self.assertEqual((unknown.known, unknown.kind, unknown.raw_value),
                         (False, XAttrSemanticKind.UNKNOWN, b'\0\xff'))
        malformed = (
            SquashFSXAttrEntry(2, decode_xattr_namespace(2), b'n', b'security.n', None, 0, False, None),
            SquashFSXAttrEntry(2, decode_xattr_namespace(2), b'n', b'security.n', b'x', 1, False, 0),
            SquashFSXAttrEntry(2, decode_xattr_namespace(2), b'n', b'security.n', bytearray(b'x'), 1, False, None),
        )
        for entry in malformed:
            with self.assertRaises(XAttrSemanticValueResolutionError) as caught:
                read_and_decode_xattr(image, entry)
            self.assertIsNone(caught.exception.__cause__)

    def test_physical_ool_capability_reuses_table_once_and_preserves_entry(self):
        image = self.target_image(self.RAW); table = read_xattr_id_table(image)
        entry = self.ool_entry(); before = entry; table_before = table
        with patch('squashfs.read_xattr_out_of_line_value', wraps=read_xattr_out_of_line_value) as resolver:
            result = read_and_decode_xattr(image, entry, table)
        self.assertEqual(resolver.call_count, 1)
        self.assertEqual(resolver.call_args.args, (image, entry, table))
        self.assertEqual((result.raw_value, result.known, result.entry), (self.RAW, True, entry))
        self.assertEqual((entry, entry.out_of_line_reference), (before, 0))
        self.assertEqual(table, table_before)
        self.assertIsInstance(result.semantic_value, squashfs.LinuxFileCapabilities)
        with self.assertRaises(AttributeError): result.raw_value = b'changed'

    def test_physical_ool_unknown_none_table_and_repeat_are_deterministic(self):
        image = self.target_image(b'\0\xffunknown'); entry = self.ool_entry(b'user.note')
        with patch('squashfs.read_xattr_id_table', wraps=read_xattr_id_table) as reads:
            first = read_and_decode_xattr(image, entry)
            second = read_and_decode_xattr(image, entry)
        self.assertEqual(reads.call_count, 2)
        self.assertEqual((first, second), (second, first))
        self.assertEqual((first.known, first.raw_value, first.semantic_value.full_name),
                         (False, b'\0\xffunknown', b'user.note'))
        self.assertEqual((entry.value, entry.out_of_line_reference), (None, 0))

    def test_wrapper_argument_and_ool_state_validation_is_typed(self):
        image = self.target_image(self.RAW); entry = self.ool_entry()
        for arguments in ((object(), entry, None), (image, object(), None),
                          (image, entry, object())):
            with self.assertRaises(XAttrSemanticTypeError):
                read_and_decode_xattr(*arguments)
        for malformed in (
            SquashFSXAttrEntry(0x102, decode_xattr_namespace(2), b'n', b'security.n', None, 8, True, None),
            SquashFSXAttrEntry(0x102, decode_xattr_namespace(2), b'n', b'security.n', b'x', 8, True, 0),
        ):
            with self.assertRaises(XAttrSemanticValueResolutionError):
                read_and_decode_xattr(image, malformed)

    def test_transport_and_semantic_errors_preserve_distinct_causes(self):
        image = self.target_image(self.RAW); entry = self.ool_entry()
        with patch('squashfs.read_xattr_out_of_line_value',
                   side_effect=SquashFSXAttrValueError('broken')):
            with self.assertRaises(XAttrSemanticValueResolutionError) as caught:
                read_and_decode_xattr(image, entry)
        self.assertIsInstance(caught.exception.__cause__, SquashFSXAttrValueError)
        bad_image = self.target_image(b'')
        with self.assertRaises(XAttrSemanticDecoderError) as caught:
            read_and_decode_xattr(bad_image, self.ool_entry())
        self.assertIsInstance(caught.exception.__cause__, LinuxCapabilityError)

    def test_wrapper_does_not_call_list_or_inode_transport(self):
        image = self.target_image(self.RAW)
        with (patch.object(squashfs, 'read_xattr_list', side_effect=AssertionError('list')),
              patch.object(squashfs, 'read_inode_xattrs', side_effect=AssertionError('inode'))):
            self.assertTrue(read_and_decode_xattr(image, self.ool_entry()).known)

    def test_existing_decoder_error_is_propagated_by_identity(self):
        image = self.target_image(b'unused'); expected = XAttrSemanticDecoderError('expected')
        with (patch.object(squashfs, 'decode_xattr_semantic', side_effect=expected) as decoder,
              patch.object(squashfs, 'read_xattr_out_of_line_value', side_effect=AssertionError('OOL'))):
            with self.assertRaises(XAttrSemanticDecoderError) as caught:
                read_and_decode_xattr(image, self.inline_entry())
        self.assertIs(caught.exception, expected); self.assertIsNone(caught.exception.__cause__)
        self.assertEqual(decoder.call_count, 1)

    def test_physical_ool_wrapper_reads_through_metadata_stream(self):
        image = self.target_image(self.RAW); entry = self.ool_entry()
        original = SquashFSMetadataStream.read
        with patch.object(SquashFSMetadataStream, 'read', autospec=True, wraps=original) as reads:
            result = read_and_decode_xattr(image, entry)
        self.assertGreaterEqual(reads.call_count, 2)
        self.assertEqual((result.raw_value, result.semantic_value.raw_value, entry.out_of_line_reference),
                         (self.RAW, self.RAW, 0))

    def test_decoded_semantic_result_snapshot_remains_immutable(self):
        source = bytes(self.RAW); image = self.target_image(source); table = read_xattr_id_table(image); entry = self.ool_entry()
        result = read_and_decode_xattr(image, entry, table); snapshot = (result, result.semantic_value, result.entry, result.raw_value, table)
        again = read_and_decode_xattr(image, entry, table)
        self.assertEqual((result, result.semantic_value, result.entry, result.raw_value, table), snapshot)
        self.assertEqual(result, again); self.assertEqual(result.semantic_value, again.semantic_value)
        with self.assertRaises(AttributeError): result.raw_value = b'x'
        with self.assertRaises(AttributeError): result.semantic_value.raw_value = b'x'


class XAttrSemanticROOTFSStage22DTest(unittest.TestCase):
    RAW=bytes.fromhex('0100000200200000000000000000000000000000')
    def image(self,payload): return XAttrSemanticTransportStage22C2Test.target_image(self,payload)
    def entry(self,name=b'security.capability',ref=0): return XAttrSemanticTransportStage22C2Test.ool_entry(name,ref)
    def live(self):
        image=SquashFSImage(ROOTFS); table=read_xattr_id_table(image); listing=read_xattr_list(image,read_xattr_id(image,0,table),table)
        return image,table,next(e for e in listing.entries if e.full_name==b'security.capability')
    def test_live_rootfs_capability_dispatch(self):
        image,table,entry=self.live(); result=read_and_decode_xattr(image,entry,table)
        self.assertEqual((type(result),result.known,result.kind,result.decoder_id,result.raw_value),(DecodedXAttr,True,XAttrSemanticKind.LINUX_FILE_CAPABILITIES,'linux.security.capability',self.RAW))
        value=result.semantic_value; self.assertEqual((value.revision,value.effective,value.permitted.raw_mask,value.permitted.capability_numbers,value.permitted.known_names,value.inheritable.capability_numbers,value.root_id),(LinuxCapabilityRevision.REVISION_2,True,0x2000,(13,),('CAP_NET_RAW',),(),None))
    def test_live_inline_avoids_ool_resolver(self):
        image,table,entry=self.live()
        with patch('squashfs.read_xattr_out_of_line_value',side_effect=AssertionError('OOL')) as resolver: result=read_and_decode_xattr(image,entry,table)
        self.assertEqual(resolver.call_count,0); self.assertEqual((entry.value,table,result.entry),(self.RAW,table,entry))
    def test_live_pure_wrapper_equality(self):
        image,table,entry=self.live(); self.assertEqual(read_and_decode_xattr(image,entry,table),decode_xattr_semantic(entry,entry.value))
    def test_synthetic_physical_ool_capability(self):
        image=self.image(self.RAW); table=read_xattr_id_table(image); entry=self.entry(); first=read_and_decode_xattr(image,entry,table); second=read_and_decode_xattr(image,entry)
        self.assertEqual((first.known,first.decoder_id,first.semantic_value,first,entry.out_of_line_reference),(True,'linux.security.capability',decode_linux_file_capabilities(self.RAW),second,0))
    def test_synthetic_unknown_inline(self):
        image=self.image(b'x'); entry=SquashFSXAttrEntry(0,decode_xattr_namespace(0),b'unknown',b'user.unknown',b'\0\xff',2,False,None); result=read_and_decode_xattr(image,entry)
        self.assertEqual((result.known,result.kind,result.decoder_id,result.semantic_value.full_name,result.raw_value),(False,XAttrSemanticKind.UNKNOWN,None,b'user.unknown',b'\0\xff'))
    def test_synthetic_unknown_ool(self):
        image=self.image(b'\0\xff'); entry=self.entry(b'user.unknown'); first=read_and_decode_xattr(image,entry); second=read_and_decode_xattr(image,entry)
        self.assertEqual((first,first.raw_value,entry.out_of_line_reference),(second,b'\0\xff',0))
    def test_exact_name_matching(self):
        image=self.image(b'x')
        for name in (b'Security.capability',b'security.capabilities',b'user.capability'):
            self.assertEqual(read_and_decode_xattr(image,SquashFSXAttrEntry(0,decode_xattr_namespace(0),b'n',name,b'x',1,False,None)).kind,XAttrSemanticKind.UNKNOWN)
    def test_transport_failure_chain(self):
        image=self.image(self.RAW); entry=self.entry()
        with patch('squashfs.read_xattr_out_of_line_value',side_effect=SquashFSXAttrValueError('bad')):
            with self.assertRaises(XAttrSemanticValueResolutionError) as caught: read_and_decode_xattr(image,entry)
        self.assertIsInstance(caught.exception.__cause__,SquashFSXAttrValueError)
    def test_semantic_failure_chain(self):
        image=self.image(b'');
        with self.assertRaises(XAttrSemanticDecoderError) as caught: read_and_decode_xattr(image,self.entry())
        self.assertIsInstance(caught.exception.__cause__,LinuxCapabilityError)
    def test_immutability_and_repeated_snapshots(self):
        image=self.image(self.RAW); table=read_xattr_id_table(image); entry=self.entry(); result=read_and_decode_xattr(image,entry,table); snapshot=(result,result.semantic_value,entry,table,result.raw_value)
        self.assertEqual((read_and_decode_xattr(image,entry,table),result.semantic_value,entry,table,result.raw_value),snapshot)
        with self.assertRaises(AttributeError): result.raw_value=b'x'
        with self.assertRaises(AttributeError): result.semantic_value.raw_value=b'x'


class SquashFSFilesystemRootStage23BTest(unittest.TestCase):
    def image(self, inode_type=BASIC_DIRECTORY_INODE_TYPE, inode_number=7):
        if inode_type == BASIC_DIRECTORY_INODE_TYPE:
            body = BASIC_DIRECTORY_INODE_BODY_STRUCT.pack(0, 2, 3, 0, 0)
        elif inode_type == EXTENDED_DIRECTORY_INODE_TYPE:
            body = EXTENDED_DIRECTORY_INODE_BODY_STRUCT.pack(0, 2, 3, 0, 0, 0, 0)
        elif inode_type == BASIC_REGULAR_INODE_TYPE:
            body = BASIC_REGULAR_INODE_BODY_STRUCT.pack(0, SQUASHFS_INVALID_FRAGMENT, 0, 0)
        elif inode_type == BASIC_SYMLINK_INODE_TYPE:
            body = BASIC_SYMLINK_INODE_BODY_STRUCT.pack(1, 0)
        else:
            body = b''
        inode = INODE_HEADER_STRUCT.pack(inode_type, 0, 0, 0, 0, inode_number) + body
        start = 96; raw = bytearray(start + 2 + len(inode))
        raw[:96] = struct.pack('<IIIIIHHHHHHQQQQQQQQ', SQUASHFS_MAGIC, 1, 0, 4096, 0, 6, 12, 0, 1, 4, 0, 0, len(raw), 0, SQUASHFS_INVALID_BLK, start, 0, 0, 0)
        raw[start:start + 2] = struct.pack('<H', METADATA_UNCOMPRESSED_BIT | len(inode)); raw[start + 2:] = inode
        directory = tempfile.TemporaryDirectory(); path = Path(directory.name) / 'root.sqfs'; path.write_bytes(raw); self.addCleanup(directory.cleanup)
        return SquashFSImage(path)

    def test_enum_identity_and_immutability(self):
        self.assertEqual(tuple(SquashFSNodeType), (SquashFSNodeType.DIRECTORY, SquashFSNodeType.REGULAR_FILE, SquashFSNodeType.SYMLINK, SquashFSNodeType.UNSUPPORTED))
        fs = open_filesystem(self.image()); identity = SquashFSInodeIdentity(fs.root_inode.reference, 7)
        self.assertEqual(identity, fs.root_identity)
        with self.assertRaises(AttributeError): identity.inode_number = 8
        with self.assertRaises(SquashFSFilesystemGraphError): SquashFSInodeIdentity(object(), 0)
        with self.assertRaises(SquashFSFilesystemGraphError): SquashFSInodeIdentity(identity.reference, -1)

    def test_basic_root_and_repeated_get_root(self):
        fs = open_filesystem(self.image()); first = get_root(fs); second = get_root(fs)
        self.assertEqual((first.raw_name, first.parent_path, first.absolute_path, first.node_type), (None, None, b'/', SquashFSNodeType.DIRECTORY))
        self.assertEqual((first.identity, first.inode), (fs.root_identity, fs.root_inode)); self.assertEqual(first, second)
        with self.assertRaises(AttributeError): first.absolute_path = b'/x'
        self.assertNotIn('parent', first.__dataclass_fields__)

    def test_extended_root(self):
        fs = open_filesystem(self.image(EXTENDED_DIRECTORY_INODE_TYPE, 11)); root = get_root(fs)
        self.assertIsInstance(fs.root_inode.body, SquashFSExtendedDirectoryInode)
        self.assertEqual((root.node_type, root.identity.inode_number), (SquashFSNodeType.DIRECTORY, 11))

    def test_errors_and_model_mismatch(self):
        with self.assertRaises(SquashFSFilesystemGraphError): open_filesystem(object())
        with self.assertRaises(SquashFSRootError): open_filesystem(self.image(BASIC_REGULAR_INODE_TYPE))
        with self.assertRaises(SquashFSRootError): open_filesystem(self.image(BASIC_SYMLINK_INODE_TYPE))
        fs = open_filesystem(self.image()); root = get_root(fs)
        with self.assertRaises(SquashFSNodeTypeError): SquashFSRegularFileNode(fs, root.identity, root.inode, None, None, b'/', SquashFSNodeType.REGULAR_FILE)
        with self.assertRaises(SquashFSFilesystemGraphError): SquashFSPathNode(fs, SquashFSInodeIdentity(root.identity.reference, 9), root.inode, None, None, b'/', SquashFSNodeType.DIRECTORY)

    def test_filesystem_and_root_identity_invariants(self):
        fs = open_filesystem(self.image()); root = get_root(fs)
        with self.assertRaises(AttributeError): fs.root_inode = root.inode
        with self.assertRaises(SquashFSFilesystemGraphError): SquashFSFilesystem(fs.image, fs.superblock, fs.inode_stream, fs.root_inode, SquashFSInodeIdentity(SquashFSMetadataReference(1, 0), root.identity.inode_number))
        with self.assertRaises(SquashFSFilesystemGraphError): SquashFSFilesystem(fs.image, fs.superblock, fs.inode_stream, fs.root_inode, SquashFSInodeIdentity(root.identity.reference, root.identity.inode_number + 1))
        with self.assertRaises(SquashFSFilesystemGraphError): SquashFSFilesystem(fs.image, fs.superblock, SquashFSMetadataStream(self.image(), 96), fs.root_inode, root.identity)

    def test_path_node_direct_invariant_matrix(self):
        fs = open_filesystem(self.image()); root = get_root(fs); i = root.identity; n = root.inode
        bad = ((object(), i, n, None, None, b'/'), (fs, object(), n, None, None, b'/'), (fs, i, object(), None, None, b'/'), (fs, i, n, b'', b'/', b'/x'), (fs, i, n, 'x', b'/', b'/x'), (fs, i, n, b'x', None, b'/x'), (fs, i, n, b'x', b'x', b'/x'), (fs, i, n, b'x', b'/', 'x'), (fs, i, n, b'x', b'/', b'x'), (fs, i, n, None, b'/', b'/'), (fs, i, n, None, None, b'/x'))
        for args in bad:
            with self.assertRaises(SquashFSFilesystemGraphError): SquashFSPathNode(*args, SquashFSNodeType.DIRECTORY)
        with self.assertRaises(SquashFSNodeTypeError): SquashFSDirectoryNode(fs, i, n, None, None, b'/', SquashFSNodeType.REGULAR_FILE)
        with self.assertRaises(SquashFSNodeTypeError): SquashFSSymlinkNode(fs, i, n, None, None, b'/', SquashFSNodeType.SYMLINK)
        with self.assertRaises(SquashFSNodeTypeError): SquashFSUnsupportedNode(fs, i, n, None, None, b'/', SquashFSNodeType.UNSUPPORTED)

    def test_root_failure_cause_matrix(self):
        image = self.image()
        for symbol, error in (('read_superblock', OSError('super')), ('SquashFSMetadataStream', ValueError('stream')), ('read_inode', SquashFSInodeError('inode'))):
            target = image if symbol == 'read_superblock' else squashfs
            with patch.object(target, symbol, side_effect=error):
                with self.assertRaises(SquashFSRootError) as caught: open_filesystem(image)
            self.assertIs(caught.exception.__cause__, error)
        with self.assertRaises(SquashFSRootError) as caught: open_filesystem(self.image(99))
        self.assertIsInstance(caught.exception.__cause__, SquashFSUnsupportedInodeTypeError)

    def test_synthetic_lazy_call_counts(self):
        image = self.image()
        names=('read_directory','read_inode_xattrs','read_and_decode_xattr','read_basic_regular_file','read_extended_regular_file','read_basic_symlink','read_extended_symlink','resolve_inode_number')
        with ExitStack() as stack:
            inode=stack.enter_context(patch.object(squashfs,'read_inode',wraps=squashfs.read_inode)); spies=[stack.enter_context(patch.object(squashfs,name)) for name in names]
            fs=open_filesystem(image); self.assertEqual(inode.call_count,1); get_root(fs); self.assertEqual(inode.call_count,1)
            self.assertTrue(all(spy.call_count == 0 for spy in spies))

    def test_real_rootfs_lazy_call_counts(self):
        image=SquashFSImage(ROOTFS); names=('read_directory','read_inode_xattrs','read_and_decode_xattr','read_basic_regular_file','read_extended_regular_file','read_basic_symlink','read_extended_symlink','resolve_inode_number')
        with ExitStack() as stack:
            inode=stack.enter_context(patch.object(squashfs,'read_inode',wraps=squashfs.read_inode)); spies=[stack.enter_context(patch.object(squashfs,name)) for name in names]
            fs=open_filesystem(image); root=get_root(fs)
            self.assertIsInstance(root.inode.body,SquashFSBasicDirectoryInode); self.assertEqual((root.absolute_path,root.identity),(b'/',fs.root_identity)); self.assertEqual(inode.call_count,1); self.assertTrue(all(spy.call_count==0 for spy in spies))

    def test_malformed_root_and_lazy_open(self):
        image = self.image(); image.read_superblock().root_inode
        with patch.object(squashfs, 'decode_metadata_reference', side_effect=ValueError('bad')):
            with self.assertRaises(SquashFSRootError) as caught: open_filesystem(image)
        self.assertIsInstance(caught.exception.__cause__, ValueError)
        image = self.image()
        with (patch.object(squashfs, 'read_directory', side_effect=AssertionError('directory')),
              patch.object(squashfs, 'read_inode_xattrs', side_effect=AssertionError('xattr')),
              patch.object(squashfs, 'read_basic_regular_file', side_effect=AssertionError('file')),
              patch.object(squashfs, 'read_basic_symlink', side_effect=AssertionError('symlink'))):
            fs = open_filesystem(image)
        with patch.object(squashfs, 'read_inode', side_effect=AssertionError('reread')):
            self.assertEqual(get_root(fs).absolute_path, b'/')

    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_real_rootfs(self):
        fs = open_filesystem(SquashFSImage(ROOTFS)); root = get_root(fs)
        self.assertIsInstance(fs.root_inode.body, SquashFSBasicDirectoryInode)
        self.assertEqual((root.absolute_path, root.identity.reference, root.identity.inode_number), (b'/', fs.root_inode.reference, fs.root_inode.header.inode_number))

class SquashFSDirectoryListingStage23C1Test(unittest.TestCase):
    def physical(self, records=(), extended=False):
        child_bytes=[]; offsets=[]; cursor=EXTENDED_DIRECTORY_INODE_SIZE if extended else BASIC_DIRECTORY_INODE_SIZE
        for name, kind, number, target in records:
            if target is not None: offsets.append(target); continue
            offsets.append(cursor)
            if kind == BASIC_REGULAR_INODE_TYPE: body=BASIC_REGULAR_INODE_BODY_STRUCT.pack(0,SQUASHFS_INVALID_FRAGMENT,0,0)
            elif kind == BASIC_DIRECTORY_INODE_TYPE: body=BASIC_DIRECTORY_INODE_BODY_STRUCT.pack(0,2,3,0,0)
            else: body=BASIC_SYMLINK_INODE_BODY_STRUCT.pack(1,0)
            raw=INODE_HEADER_STRUCT.pack(kind,0,0,0,0,number)+body; child_bytes.append(raw); cursor+=len(raw)
        entries=[]
        for (name,kind,number,_),offset in zip(records,offsets): entries.append(DIRECTORY_ENTRY_STRUCT.pack(offset,number-1,kind,len(name)-1)+name)
        table=(DIRECTORY_HEADER_STRUCT.pack(len(entries)-1,0,1)+b''.join(entries)) if entries else b''
        size=3+len(table)
        rootbody=(EXTENDED_DIRECTORY_INODE_BODY_STRUCT.pack(2,size,0,0,0,0,0) if extended else BASIC_DIRECTORY_INODE_BODY_STRUCT.pack(0,2,size,0,0))
        rtype=EXTENDED_DIRECTORY_INODE_TYPE if extended else BASIC_DIRECTORY_INODE_TYPE; root=INODE_HEADER_STRUCT.pack(rtype,0,0,0,0,1)+rootbody
        inode=root+b''.join(child_bytes); istart=96; dstart=istart+2+len(inode); raw=bytearray(dstart+2+len(table))
        raw[:96]=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,1,0,4096,0,6,12,0,1,4,0,0,len(raw),0,SQUASHFS_INVALID_BLK,istart,dstart,0,0)
        raw[istart:istart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(inode)); raw[istart+2:dstart]=inode; raw[dstart:dstart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(table)); raw[dstart+2:]=table
        d=tempfile.TemporaryDirectory(); p=Path(d.name)/'dir.sqfs'; p.write_bytes(raw); self.addCleanup(d.cleanup); return SquashFSImage(p)
    def test_physical_basic_directory_fixture(self):
        fs=open_filesystem(self.physical()); listing=list_children(fs,get_root(fs))
        self.assertEqual(listing.children,())
    def test_physical_extended_directory_fixture(self):
        image=self.physical(extended=True); fs=open_filesystem(image); self.assertEqual(list_children(fs,get_root(fs)).children,())
    def test_physical_mixed_children_fixture(self):
        image=self.physical(((b'f',2,2,None),(b'd',1,3,None),(b'l',3,4,None))); fs=open_filesystem(image); children=list_children(fs,get_root(fs)).children
        self.assertEqual(([x.raw_name for x in children],[type(x) for x in children]),([b'f',b'd',b'l'],[SquashFSRegularFileNode,SquashFSDirectoryNode,SquashFSSymlinkNode]))
    def test_physical_hardlink_duplicate_and_self_reference_fixtures(self):
        image=self.physical(((b'a',2,2,None),(b'b',2,2,BASIC_DIRECTORY_INODE_SIZE),(b'x',2,2,BASIC_DIRECTORY_INODE_SIZE),(b'x',2,2,BASIC_DIRECTORY_INODE_SIZE),(b'self',1,1,0))); fs=open_filesystem(image); children=list_children(fs,get_root(fs)).children
        self.assertEqual([x.raw_name for x in children],[b'a',b'b',b'x',b'x',b'self']); self.assertEqual(children[0].identity,children[1].identity); self.assertIsInstance(children[-1],SquashFSDirectoryNode)
    def test_malformed_child_names_are_rejected(self):
        fs=open_filesystem(self.physical(((b'a',2,2,None),))); root=get_root(fs); inode=fs.root_inode
        for name in (b'',b'a/b',b'a\0b',b'.',b'..'):
            record=SquashFSDirectoryRecord(1,2,name,fs.root_inode.reference)
            with patch.object(squashfs,'read_directory',return_value=[record]), patch.object(squashfs,'read_inode',return_value=inode):
                with self.assertRaises(SquashFSDirectoryEntryError) as caught: list_children(fs,root)
            self.assertIn('name',str(caught.exception))
    def test_invalid_utf8_child_name_is_preserved(self):
        image=self.physical(((b'\xff',2,2,None),)); fs=open_filesystem(image); child=list_children(fs,get_root(fs)).children[0]
        self.assertEqual((child.raw_name,child.absolute_path),(b'\xff',b'/\xff'))
    def test_child_inode_number_mismatch_is_rejected(self):
        fs=open_filesystem(self.physical(((b'a',2,2,None),))); root=get_root(fs); record=SquashFSDirectoryRecord(9,2,b'a',fs.root_inode.reference)
        with patch.object(squashfs,'read_directory',return_value=[record]), patch.object(squashfs,'read_inode',return_value=fs.root_inode):
            with self.assertRaises(SquashFSChildInodeError): list_children(fs,root)
    def test_child_reference_or_read_failure_is_wrapped(self):
        fs=open_filesystem(self.physical()); root=get_root(fs); error=SquashFSInodeError('child')
        with patch.object(squashfs,'read_directory',return_value=[SquashFSDirectoryRecord(2,2,b'a',SquashFSMetadataReference(1,0))]), patch.object(squashfs,'read_inode',side_effect=error):
            with self.assertRaises(SquashFSChildInodeError) as caught: list_children(fs,root)
        self.assertIs(caught.exception.__cause__,error)
    def test_directory_read_failure_preserves_cause(self):
        fs=open_filesystem(self.physical()); error=SquashFSDirectoryError('directory')
        with patch.object(squashfs,'read_directory',side_effect=error):
            with self.assertRaises(SquashFSDirectoryReadError) as caught: list_children(fs,get_root(fs))
        self.assertIs(caught.exception.__cause__,error)
    def test_unsupported_child_inode_is_wrapped(self):
        fs=open_filesystem(self.physical()); root=get_root(fs); error=SquashFSUnsupportedInodeTypeError('unsupported')
        with patch.object(squashfs,'read_directory',return_value=[SquashFSDirectoryRecord(2,99,b'x',SquashFSMetadataReference(1,0))]), patch.object(squashfs,'read_inode',side_effect=error):
            with self.assertRaises(SquashFSChildInodeError) as caught: list_children(fs,root)
        self.assertIs(caught.exception.__cause__,error)
    def test_public_directory_listing_arguments_are_typed(self):
        fs=open_filesystem(self.physical()); root=get_root(fs)
        for args in ((object(),root),(fs,object()),(open_filesystem(self.physical()),root)):
            with self.assertRaises(SquashFSFilesystemGraphError): list_children(*args)
    def test_child_reference_mismatch_is_rejected(self):
        fs=open_filesystem(self.physical()); root=get_root(fs); other=SquashFSInode(SquashFSMetadataReference(9,0),fs.root_inode.header,fs.root_inode.body)
        record=SquashFSDirectoryRecord(1,1,b'x',fs.root_inode.reference)
        with patch.object(squashfs,'read_directory',return_value=[record]), patch.object(squashfs,'read_inode',return_value=other):
            with self.assertRaisesRegex(SquashFSChildInodeError,'identity'): list_children(fs,root)
    def test_synthetic_listing_lazy_call_counts(self):
        fs=open_filesystem(self.physical(((b'f',2,2,None),(b'd',1,3,None),(b'l',3,4,None)))); root=get_root(fs); names=('read_inode_xattrs','read_and_decode_xattr','read_basic_regular_file','read_extended_regular_file','read_basic_symlink','read_extended_symlink','resolve_inode_number')
        with ExitStack() as stack:
            rd=stack.enter_context(patch.object(squashfs,'read_directory',wraps=squashfs.read_directory)); ri=stack.enter_context(patch.object(squashfs,'read_inode',wraps=squashfs.read_inode)); spies=[stack.enter_context(patch.object(squashfs,n)) for n in names]; children=list_children(fs,root).children
        self.assertEqual((rd.call_count,ri.call_count),(1,len(children))); self.assertTrue(all(x.call_count==0 for x in spies))
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_real_rootfs_listing_acceptance_matrix(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); root=get_root(fs); listing=list_children(fs,root); names=[x.raw_name for x in listing.children]; bin_node=next(x for x in listing.children if x.raw_name==b'bin')
        self.assertEqual((len(listing.children),listing.children[0].absolute_path),(13,b'/bin')); self.assertEqual(len(names),len(set(names))); self.assertIsInstance(bin_node,SquashFSDirectoryNode); self.assertEqual((bin_node.raw_name,bin_node.absolute_path),(b'bin',b'/bin')); self.assertEqual((root,fs),(get_root(fs),fs))
    def test_listing_rejects_child_parent_path_mismatch(self):
        fs=open_filesystem(self.physical()); root=get_root(fs); child=SquashFSDirectoryNode(fs,root.identity,root.inode,b'x',b'/other',b'/other/x',SquashFSNodeType.DIRECTORY)
        with self.assertRaisesRegex(SquashFSFilesystemGraphError,'children'): SquashFSDirectoryListing(b'/',(child,))
    def test_nested_directory_child_absolute_path(self):
        fs=open_filesystem(self.physical(((b'parent',1,1,0),))); root=get_root(fs); parent=list_children(fs,root).children[0]; record=SquashFSDirectoryRecord(1,1,b'child',fs.root_inode.reference)
        with patch.object(squashfs,'read_directory',return_value=[record]): child=list_children(fs,parent).children[0]
        self.assertEqual((parent.absolute_path,child.parent_path,child.absolute_path,child.raw_name),(b'/parent',b'/parent',b'/parent/child',b'child'))
    def test_list_children_rejects_non_directory_node(self):
        fs=open_filesystem(self.physical(((b'f',2,2,None),))); file=list_children(fs,get_root(fs)).children[0]
        with patch.object(squashfs,'read_directory') as reader:
            with self.assertRaisesRegex(SquashFSNodeTypeError,'not a directory'): list_children(fs,file)
        self.assertEqual(reader.call_count,0)
    def test_graph_errors_do_not_leak_lower_level_types(self):
        fs=open_filesystem(self.physical()); root=get_root(fs); cases=((SquashFSDirectoryError('d'),SquashFSDirectoryReadError,'read_directory'),(SquashFSInodeError('i'),SquashFSChildInodeError,'read_inode'))
        for error,typ,name in cases:
            extra=patch.object(squashfs,'read_directory',return_value=[SquashFSDirectoryRecord(1,1,b'a',fs.root_inode.reference)]) if name=='read_inode' else None
            with (extra or ExitStack()), patch.object(squashfs,name,side_effect=error):
                with self.assertRaises(typ) as caught: list_children(fs,root)
            self.assertIs(caught.exception.__cause__,error)
        record=SquashFSDirectoryRecord(1,1,b'',fs.root_inode.reference)
        with patch.object(squashfs,'read_directory',return_value=[record]),patch.object(squashfs,'read_inode',return_value=fs.root_inode):
            with self.assertRaises(SquashFSDirectoryEntryError): list_children(fs,root)
    def test_list_children_is_not_recursive(self):
        fs=open_filesystem(self.physical(((b'self',1,1,0),))); root=get_root(fs)
        with patch.object(squashfs,'read_directory',wraps=squashfs.read_directory) as rd,patch.object(squashfs,'read_inode',wraps=squashfs.read_inode) as ri:
            children=list_children(fs,root).children
        self.assertEqual((len(children),rd.call_count,ri.call_count),(1,1,1)); self.assertIsInstance(children[0],SquashFSDirectoryNode)
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_real_root_listing_order_types_and_identity(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); root=get_root(fs); listing=list_children(fs,root)
        self.assertEqual(len(listing.children),13); self.assertEqual(listing.directory_path,b'/')
        self.assertEqual(tuple(node.raw_name for node in listing.children),tuple(record.name for record in read_directory(SquashFSMetadataStream(fs.image,fs.superblock.directory_table_start),fs.root_inode.body)))
        self.assertIsInstance(next(node for node in listing.children if node.raw_name==b'bin'),SquashFSDirectoryNode)
        self.assertEqual(len({node.raw_name for node in listing.children}),len(listing.children))
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_real_root_listing_lazy_call_counts(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); root=get_root(fs); names=('read_inode_xattrs','read_and_decode_xattr','read_basic_regular_file','read_extended_regular_file','read_basic_symlink','read_extended_symlink','resolve_inode_number')
        with ExitStack() as stack:
            rd=stack.enter_context(patch.object(squashfs,'read_directory',wraps=squashfs.read_directory)); ri=stack.enter_context(patch.object(squashfs,'read_inode',wraps=squashfs.read_inode)); spies=[stack.enter_context(patch.object(squashfs,name)) for name in names]
            listing=list_children(fs,root)
        self.assertEqual((rd.call_count,ri.call_count),(1,len(listing.children))); self.assertTrue(all(x.call_count==0 for x in spies))
    def test_listing_model_validation_and_immutability(self):
        with self.assertRaises(SquashFSFilesystemGraphError): SquashFSDirectoryListing(b'x',())
        with self.assertRaises(SquashFSFilesystemGraphError): SquashFSDirectoryListing(b'/',[])
        listing=SquashFSDirectoryListing(b'/',()); self.assertEqual(listing,SquashFSDirectoryListing(b'/',()))
        with self.assertRaises(AttributeError): listing.children=()
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_public_arguments_and_directory_ownership(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); root=get_root(fs)
        with self.assertRaises(SquashFSFilesystemGraphError): list_children(object(),root)
        with self.assertRaises(SquashFSFilesystemGraphError): list_children(fs,object())
        with self.assertRaises(SquashFSFilesystemGraphError): list_children(open_filesystem(SquashFSImage(ROOTFS)),root)

class SquashFSPathLookupStage23C2Test(unittest.TestCase):
    def image(self, records=()):
        self.fixture = SquashFSDirectoryListingStage23C1Test(); return self.fixture.physical(records)

    def physical_tree(self, tree):
        """Build a compact physical SquashFS image with basic inode bodies."""
        nodes=[]
        def collect(name, value):
            node={'name':name,'value':value,'number':len(nodes)+1}; nodes.append(node)
            if isinstance(value, dict):
                for child_name, child_value in value.items(): collect(child_name,child_value)
            return node
        root=collect(None,tree)
        by_name={id(node['value']):node for node in nodes if isinstance(node['value'],dict)}
        offsets={}; cursor=0
        for node in nodes:
            offsets[id(node)]=cursor
            cursor += BASIC_DIRECTORY_INODE_SIZE if isinstance(node['value'],dict) else (BASIC_SYMLINK_INODE_SIZE if node['value']=='symlink' else BASIC_REGULAR_INODE_SIZE)
        directory_data=bytearray()
        for node in nodes:
            if not isinstance(node['value'],dict): continue
            node['directory_offset']=len(directory_data)
            entries=[]
            for name, value in node['value'].items():
                child=by_name[id(value)] if isinstance(value,dict) else next(x for x in nodes if x['value']==value)
                kind=BASIC_DIRECTORY_INODE_TYPE if isinstance(value,dict) else (BASIC_SYMLINK_INODE_TYPE if value=='symlink' else BASIC_REGULAR_INODE_TYPE)
                entries.append(DIRECTORY_ENTRY_STRUCT.pack(offsets[id(child)],child['number']-node['number'],kind,len(name)-1)+name)
            table=DIRECTORY_HEADER_STRUCT.pack(len(entries)-1,0,node['number'])+b''.join(entries) if entries else b''
            node['directory_size']=DIRECTORY_POSITION_OFFSET+len(table); directory_data.extend(table)
        inode=bytearray()
        for node in nodes:
            if isinstance(node['value'],dict): body=BASIC_DIRECTORY_INODE_BODY_STRUCT.pack(0,2,node['directory_size'],node['directory_offset'],0); kind=BASIC_DIRECTORY_INODE_TYPE
            elif node['value']=='symlink': body=BASIC_SYMLINK_INODE_BODY_STRUCT.pack(1,0); kind=BASIC_SYMLINK_INODE_TYPE
            else: body=BASIC_REGULAR_INODE_BODY_STRUCT.pack(0,SQUASHFS_INVALID_FRAGMENT,0,0); kind=BASIC_REGULAR_INODE_TYPE
            inode.extend(INODE_HEADER_STRUCT.pack(kind,0,0,0,0,node['number'])+body)
        istart=96; dstart=istart+2+len(inode); raw=bytearray(dstart+2+len(directory_data))
        raw[:96]=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,len(nodes),0,4096,0,6,12,0,1,4,0,0,len(raw),0,SQUASHFS_INVALID_BLK,istart,dstart,0,0)
        raw[istart:istart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(inode)); raw[istart+2:dstart]=inode
        raw[dstart:dstart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(directory_data)); raw[dstart+2:]=directory_data
        directory=tempfile.TemporaryDirectory(); path=Path(directory.name)/'tree.sqfs'; path.write_bytes(raw); self.addCleanup(directory.cleanup); return SquashFSImage(path)

    def tree(self):
        return self.physical_tree({b'wanted':{b'nested':{b'file':'file'}},b'unrelated':{b'sibling':'file'},b'link':'symlink',b'Case':'file',b'\xff':'file',b'file':'file'})

    def test_positive_physical_paths_and_node_immutability(self):
        fs=open_filesystem(self.tree())
        expected=((b'/',SquashFSDirectoryNode,None),(b'/wanted',SquashFSDirectoryNode,b'wanted'),(b'/wanted/nested',SquashFSDirectoryNode,b'nested'),(b'/wanted/nested/file',SquashFSRegularFileNode,b'file'),(b'/link',SquashFSSymlinkNode,b'link'),(b'/\xff',SquashFSRegularFileNode,b'\xff'))
        for path, kind, name in expected:
            node=lookup_path(fs,path); self.assertIsInstance(node,kind); self.assertEqual((node.raw_name,node.absolute_path),(name,path))
        self.assertEqual(lookup_path(fs,b'/wanted/nested/file'),lookup_path(fs,b'/wanted/nested/file'))
        with self.assertRaises(AttributeError): lookup_path(fs,b'/wanted').absolute_path=b'/changed'

    def test_exact_raw_matching_and_missing_paths(self):
        fs=open_filesystem(self.tree())
        for path in (b'/case',b'/Cas',b'/CaseX',b'/xCase',b'/\xfe',b'/missing',b'/wanted/missing',b'/wanted/nested/missing'):
            with self.assertRaises(SquashFSPathNotFoundError) as caught: lookup_path(fs,path)
            self.assertTrue(str(caught.exception))
        self.assertEqual(lookup_path(fs,b'/Case').raw_name,b'Case')
        self.assertEqual(lookup_path(fs,b'/\xff').raw_name,b'\xff')

    def test_syntax_matrix_is_typed_without_normalization(self):
        fs=open_filesystem(self.tree())
        for path in (b'',b'bin',b'//bin',b'/bin//ping',b'/bin/',b'/./bin',b'/bin/.',b'/../bin',b'/bin/..',b'/a\0b',b'/bin/\0x','/bin',bytearray(b'/bin'),memoryview(b'/bin'),object()):
            with self.assertRaises(SquashFSPathError) as caught: lookup_path(fs,path)
            self.assertIs(type(caught.exception),SquashFSPathError)

    def test_intermediate_regular_symlink_and_controlled_unsupported(self):
        fs=open_filesystem(self.tree())
        for path in (b'/file/child',b'/link/child'):
            with self.assertRaises(SquashFSNotDirectoryError): lookup_path(fs,path)
        unsupported=SimpleNamespace(raw_name=b'unknown',absolute_path=b'/unknown')
        with patch.object(squashfs,'list_children',return_value=SimpleNamespace(children=(unsupported,))):
            with self.assertRaises(SquashFSNotDirectoryError): lookup_path(fs,b'/unknown/child')

    def test_duplicate_same_and_different_inode_are_ambiguous(self):
        same_fixture=SquashFSDirectoryListingStage23C1Test(); different_fixture=SquashFSDirectoryListingStage23C1Test()
        same=open_filesystem(same_fixture.physical(((b'x',2,2,None),(b'x',2,2,BASIC_DIRECTORY_INODE_SIZE))))
        different=open_filesystem(different_fixture.physical(((b'x',2,2,None),(b'x',2,3,None))))
        for fs in (same,different):
            listing=list_children(fs,get_root(fs)); self.assertEqual([node.raw_name for node in listing.children],[b'x',b'x'])
            with self.assertRaises(SquashFSDuplicateNameError) as caught: lookup_path(fs,b'/x')
            self.assertIn("b'/'",str(caught.exception)); self.assertIn("b'x'",str(caught.exception))

    def test_typed_listing_and_child_failures_propagate_unchanged(self):
        fs=open_filesystem(self.tree()); root=get_root(fs)
        directory_error=SquashFSDirectoryReadError('directory')
        child_error=SquashFSChildInodeError('child')
        for error in (directory_error,child_error):
            with patch.object(squashfs,'list_children',side_effect=error):
                with self.assertRaises(type(error)) as caught: lookup_path(fs,b'/wanted')
            self.assertIs(caught.exception,error)
        for raw in (KeyError('k'),IndexError('i'),TypeError('t'),ValueError('v'),SquashFSDirectoryError('d')):
            with patch.object(squashfs,'read_directory',side_effect=raw):
                with self.assertRaises(SquashFSDirectoryReadError) as caught: lookup_path(fs,b'/wanted')
            self.assertIs(caught.exception.__cause__,raw)
        with patch.object(squashfs,'read_inode',side_effect=SquashFSInodeError('inode')):
            with self.assertRaises(SquashFSChildInodeError) as caught: lookup_path(fs,b'/wanted')
        self.assertIsInstance(caught.exception.__cause__,SquashFSInodeError)

    def test_lazy_lookup_expands_only_requested_directories(self):
        fs=open_filesystem(self.tree())
        names=('walk_filesystem','build_filesystem_index','read_basic_regular_file','read_extended_regular_file','read_basic_symlink','read_extended_symlink','read_inode_xattrs','read_and_decode_xattr','resolve_inode_number')
        with ExitStack() as stack:
            directory=stack.enter_context(patch.object(squashfs,'read_directory',wraps=squashfs.read_directory)); inode=stack.enter_context(patch.object(squashfs,'read_inode',wraps=squashfs.read_inode)); spies=[stack.enter_context(patch.object(squashfs,name)) for name in names]
            node=lookup_path(fs,b'/wanted/nested/file')
        self.assertEqual(node.absolute_path,b'/wanted/nested/file'); self.assertEqual(directory.call_count,3); self.assertEqual(inode.call_count,8); self.assertTrue(all(spy.call_count==0 for spy in spies))

    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_real_rootfs_lookup_matrix_and_lazy_reads(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); names=('read_basic_regular_file','read_extended_regular_file','read_basic_symlink','read_extended_symlink','read_inode_xattrs','read_and_decode_xattr')
        with ExitStack() as stack:
            directory=stack.enter_context(patch.object(squashfs,'read_directory',wraps=squashfs.read_directory)); spies=[stack.enter_context(patch.object(squashfs,name)) for name in names]
            root=lookup_path(fs,b'/'); directory_node=lookup_path(fs,b'/bin'); ping=lookup_path(fs,b'/bin/ping'); symlink=lookup_path(fs,b'/bin/sh')
        self.assertIsInstance(root,SquashFSDirectoryNode); self.assertIsInstance(directory_node,SquashFSDirectoryNode); self.assertIsInstance(ping,SquashFSRegularFileNode); self.assertIsInstance(symlink,SquashFSSymlinkNode)
        self.assertEqual(ping.identity,lookup_path(fs,b'/bin/ping').identity); self.assertLessEqual(directory.call_count,5); self.assertTrue(all(spy.call_count==0 for spy in spies))
        with self.assertRaises(SquashFSPathNotFoundError): lookup_path(fs,b'/definitely-missing-stage23-c2')


class SquashFSFilesystemTraversalStage23C3Test(unittest.TestCase):
    def image(self, records=()): self.fixture = SquashFSDirectoryListingStage23C1Test(); return self.fixture.physical(records)
    def tree(self): self.path_fixture=SquashFSPathLookupStage23C2Test(); return self.path_fixture.physical_tree({b'a':{b'file1':'file',b'sub':{b'file2':'file'}},b'b':{b'file3':'file'},b'link':'symlink'})
    def test_root_only_and_empty_traversal(self):
        empty_fixture=SquashFSPathLookupStage23C2Test(); self.empty_fixture=empty_fixture
        for image in (self.image(), empty_fixture.physical_tree({})):
            fs=open_filesystem(image); nodes=walk_filesystem(fs); self.assertEqual(nodes,(get_root(fs),)); self.assertIsInstance(nodes,tuple)
    def test_nested_depth_first_preorder_and_on_disk_order(self):
        nodes=walk_filesystem(open_filesystem(self.tree()))
        self.assertEqual([node.absolute_path for node in nodes],[b'/',b'/a',b'/a/file1',b'/a/sub',b'/a/sub/file2',b'/b',b'/b/file3',b'/link'])
    def test_symlink_is_yielded_and_never_followed(self):
        fs=open_filesystem(self.tree())
        with patch.object(squashfs,'read_basic_symlink') as basic, patch.object(squashfs,'read_extended_symlink') as extended:
            nodes=walk_filesystem(fs)
        self.assertIsInstance(nodes[-1],SquashFSSymlinkNode); self.assertEqual((basic.call_count,extended.call_count),(0,0))
    def test_hardlinked_regular_inode_is_yielded_at_all_paths(self):
        fs=open_filesystem(self.image(((b'a',2,2,None),(b'b',2,2,BASIC_DIRECTORY_INODE_SIZE))))
        nodes=walk_filesystem(fs); self.assertEqual([x.absolute_path for x in nodes],[b'/',b'/a',b'/b']); self.assertNotEqual(nodes[1].absolute_path,nodes[2].absolute_path); self.assertEqual(nodes[1].identity,nodes[2].identity)
    def test_self_directory_cycle_is_typed(self):
        fs=open_filesystem(self.image(((b'self',1,1,0),)))
        with self.assertRaises(SquashFSDirectoryCycleError) as caught: walk_filesystem(fs)
        self.assertIn("b'/self'",str(caught.exception)); self.assertIn('SquashFSInodeIdentity',str(caught.exception))
    def test_ancestor_directory_cycle_is_typed(self):
        fs=open_filesystem(self.tree()); root=get_root(fs); a=next(x for x in list_children(fs,root).children if x.raw_name==b'a'); b=next(x for x in list_children(fs,a).children if x.raw_name==b'sub')
        back=SquashFSDirectoryNode(fs,a.identity,a.inode,b'back',b.absolute_path,b.absolute_path+b'/back',SquashFSNodeType.DIRECTORY)
        original=squashfs.list_children
        def listings(filesystem,node): return SimpleNamespace(children=(back,)) if node.absolute_path==b.absolute_path else original(filesystem,node)
        with patch.object(squashfs,'list_children',side_effect=listings):
            with self.assertRaises(SquashFSDirectoryCycleError) as caught: walk_filesystem(fs)
        self.assertIn("b'/a/sub/back'",str(caught.exception)); self.assertIn(repr(a.identity),str(caught.exception))
    def test_duplicate_absolute_path_is_rejected(self):
        fs=open_filesystem(self.image(((b'x',2,2,None),(b'x',2,2,BASIC_DIRECTORY_INODE_SIZE))))
        with self.assertRaises(SquashFSDuplicateNameError): walk_filesystem(fs)
    def test_traversal_errors_preserve_public_boundaries(self):
        fs=open_filesystem(self.tree())
        for error in (SquashFSDirectoryReadError('directory'),SquashFSChildInodeError('child')):
            with patch.object(squashfs,'list_children',side_effect=error):
                with self.assertRaises(type(error)) as caught: walk_filesystem(fs)
            self.assertIs(caught.exception,error)
    def test_traversal_performs_no_content_or_xattr_reads(self):
        fs=open_filesystem(self.tree()); names=('read_basic_regular_file','read_extended_regular_file','read_basic_symlink','read_extended_symlink','read_inode_xattrs','read_and_decode_xattr','resolve_inode_number','read_node_bytes','read_node_symlink','read_node_xattrs','build_filesystem_index')
        with ExitStack() as stack:
            spies=[stack.enter_context(patch.object(squashfs,name)) for name in names]; walk_filesystem(fs)
        self.assertTrue(all(spy.call_count==0 for spy in spies))
    def test_repeated_traversal_is_deterministic_and_immutable(self):
        fs=open_filesystem(self.tree()); first=walk_filesystem(fs); second=walk_filesystem(fs); self.assertEqual(first,second)
        with self.assertRaises(TypeError): first[0]=second[0]
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_real_rootfs_traversal_matrix(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); names=('read_basic_regular_file','read_extended_regular_file','read_basic_symlink','read_extended_symlink','read_inode_xattrs','read_and_decode_xattr')
        with ExitStack() as stack:
            spies=[stack.enter_context(patch.object(squashfs,name)) for name in names]; nodes=walk_filesystem(fs)
        types={kind:sum(node.node_type.value==kind for node in nodes) for kind in ('directory','regular_file','symlink','unsupported')}
        self.assertEqual((len(nodes),types,max(node.absolute_path.count(b'/') for node in nodes)),(43433,{'directory':5329,'regular_file':35952,'symlink':2152,'unsupported':0},17)); self.assertEqual(sum(node.absolute_path==b'/bin/ping' for node in nodes),1); self.assertEqual(len({node.absolute_path for node in nodes}),len(nodes)); self.assertTrue(all(spy.call_count==0 for spy in spies))


class SquashFSFilesystemIndexStage23C3Test(unittest.TestCase):
    def image(self, records=()): self.fixture=SquashFSDirectoryListingStage23C1Test(); return self.fixture.physical(records)
    def tree(self): self.path_fixture=SquashFSPathLookupStage23C2Test(); return self.path_fixture.physical_tree({b'a':{b'one':'file'},b'b':{b'two':'file'},b'link':'symlink'})
    def test_index_model_invariants_and_immutability(self):
        fs=open_filesystem(self.image()); root=get_root(fs); paths=MappingProxyType({b'/':root}); reverse=MappingProxyType({root.identity:(b'/',)})
        index=SquashFSFilesystemIndex(root,(root,),paths,reverse); self.assertEqual(index,SquashFSFilesystemIndex(root,(root,),paths,reverse))
        with self.assertRaises(AttributeError): index.nodes=()
        with self.assertRaises(TypeError): index.paths[b'/x']=root
        for nodes, path_map, inode_map in (((root,root),paths,reverse),((root,root),MappingProxyType({b'/':root}),reverse),((root,),MappingProxyType({}),reverse),((root,),paths,MappingProxyType({}))):
            with self.assertRaises(SquashFSFilesystemIndexError): SquashFSFilesystemIndex(root,nodes,path_map,inode_map)
    def test_root_only_and_nested_index(self):
        fs=open_filesystem(self.tree()); index=build_filesystem_index(fs)
        self.assertEqual(index.nodes,walk_filesystem(fs)); self.assertEqual(index.paths[b'/'],index.root); self.assertIs(node_for_path(index,b'/a/one'),index.paths[b'/a/one']); self.assertEqual(set(index.paths),{node.absolute_path for node in index.nodes}); self.assertEqual(index,build_filesystem_index(fs))
    def test_node_for_path_validation_and_missing_paths(self):
        index=build_filesystem_index(open_filesystem(self.tree()))
        self.assertEqual(node_for_path(index,b'/').absolute_path,b'/')
        for path in (b'/missing',b'',b'a',b'//a',b'/a/',b'/./a',b'/a/..',b'/a\0b','/a',bytearray(b'/a'),memoryview(b'/a'),object()):
            with self.assertRaises((SquashFSPathError,SquashFSPathNotFoundError)): node_for_path(index,path)
    def test_paths_for_inode_validation_and_single_path(self):
        index=build_filesystem_index(open_filesystem(self.tree())); root=index.root
        self.assertEqual(paths_for_inode(index,root.identity),(b'/',)); self.assertEqual(paths_for_inode(index,SquashFSInodeIdentity(root.identity.reference,999999)),())
        with self.assertRaises(SquashFSFilesystemIndexError): paths_for_inode(index,object())
        with self.assertRaises(SquashFSFilesystemIndexError): paths_for_inode(object(),root.identity)
        self.assertEqual(paths_for_inode(index,root.identity),paths_for_inode(index,root.identity))
    def test_same_directory_hardlinks_are_reverse_indexed(self):
        fs=open_filesystem(self.image(((b'a',2,2,None),(b'b',2,2,BASIC_DIRECTORY_INODE_SIZE)))); index=build_filesystem_index(fs); a=node_for_path(index,b'/a'); b=node_for_path(index,b'/b')
        self.assertIsNot(a,b); self.assertEqual(a.identity,b.identity); self.assertEqual(paths_for_inode(index,a.identity),(b'/a',b'/b'))
    def test_cross_directory_hardlinks_preserve_traversal_order(self):
        index=build_filesystem_index(open_filesystem(self.tree())); one=node_for_path(index,b'/a/one'); two=node_for_path(index,b'/b/two')
        self.assertEqual(one.identity,two.identity); self.assertEqual(paths_for_inode(index,one.identity),(b'/a/one',b'/b/two')); self.assertEqual([node.absolute_path for node in index.nodes],[b'/',b'/a',b'/a/one',b'/b',b'/b/two',b'/link'])
    def test_duplicate_paths_and_cycles_are_rejected(self):
        duplicate_fixture=SquashFSDirectoryListingStage23C1Test(); cycle_fixture=SquashFSDirectoryListingStage23C1Test()
        duplicate=open_filesystem(duplicate_fixture.physical(((b'x',2,2,None),(b'x',2,2,BASIC_DIRECTORY_INODE_SIZE))))
        cycle=open_filesystem(cycle_fixture.physical(((b'self',1,1,0),)))
        with self.assertRaises(SquashFSDuplicateNameError): build_filesystem_index(duplicate)
        with self.assertRaises(SquashFSDirectoryCycleError): build_filesystem_index(cycle)
    def test_index_build_performs_no_content_or_xattr_reads(self):
        fs=open_filesystem(self.tree()); names=('read_basic_regular_file','read_extended_regular_file','read_basic_symlink','read_extended_symlink','read_inode_xattrs','read_and_decode_xattr','read_node_bytes','read_node_symlink','read_node_xattrs','resolve_inode_number','lookup_path')
        with ExitStack() as stack:
            spies=[stack.enter_context(patch.object(squashfs,name)) for name in names]; build_filesystem_index(fs)
        self.assertTrue(all(spy.call_count==0 for spy in spies))
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_real_rootfs_index_and_hardlink_groups(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); index=build_filesystem_index(fs); ping=node_for_path(index,b'/bin/ping'); repeated=[paths for paths in index.inode_paths.values() if len(paths)>1]
        self.assertEqual((len(index.nodes),len(index.paths),len(index.inode_paths),len(repeated)),(43433,43433,43427,5)); self.assertIsInstance(ping,SquashFSRegularFileNode); self.assertIn(b'/bin/ping',paths_for_inode(index,ping.identity)); self.assertEqual(repeated,[(b'/bin/bunzip2',b'/bin/bzcat',b'/bin/bzip2'),(b'/bin/gunzip',b'/bin/uncompress'),(b'/usr/bin/perl',b'/usr/bin/perl5.32.1'),(b'/usr/bin/perlbug',b'/usr/bin/perlthanks'),(b'/usr/bin/unzip',b'/usr/bin/zipinfo')])


class SquashFSFilesystemContentStage23DTest(unittest.TestCase):
    def tree(self): self.fixture=SquashFSPathLookupStage23C2Test(); return self.fixture.physical_tree({b'file':'file',b'link':'symlink'})
    def extended_symlink_tree(self, target=b'../target', *, extended=True):
        """A two-inode physical image: basic root directory and extended link."""
        root_size=BASIC_DIRECTORY_INODE_SIZE; child_ref=root_size
        link_type=EXTENDED_SYMLINK_INODE_TYPE if extended else BASIC_SYMLINK_INODE_TYPE
        record=DIRECTORY_ENTRY_STRUCT.pack(child_ref,1,link_type,len(b'link')-1)+b'link'
        directory=DIRECTORY_HEADER_STRUCT.pack(0,0,1)+record; directory_size=DIRECTORY_POSITION_OFFSET+len(directory)
        root=INODE_HEADER_STRUCT.pack(BASIC_DIRECTORY_INODE_TYPE,0,0,0,0,1)+BASIC_DIRECTORY_INODE_BODY_STRUCT.pack(0,2,directory_size,0,0)
        link_body=EXTENDED_SYMLINK_INODE_BODY_STRUCT.pack(1,len(target),0xffffffff) if extended else BASIC_SYMLINK_INODE_BODY_STRUCT.pack(1,len(target))
        link=INODE_HEADER_STRUCT.pack(link_type,0,0,0,0,2)+link_body+target
        inode=root+link; istart=96; dstart=istart+2+len(inode); raw=bytearray(dstart+2+len(directory))
        raw[:96]=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,2,0,4096,0,6,12,0,1,4,0,0,len(raw),0,SQUASHFS_INVALID_BLK,istart,dstart,0,0)
        raw[istart:istart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(inode)); raw[istart+2:dstart]=inode
        raw[dstart:dstart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(directory)); raw[dstart+2:]=directory
        directory_handle=tempfile.TemporaryDirectory(); path=Path(directory_handle.name)/'extended-link.sqfs'; path.write_bytes(raw); self.addCleanup(directory_handle.cleanup); return SquashFSImage(path)
    def extended_empty_regular_tree(self):
        """Physical root directory plus a parsed type-9 zero-length child inode."""
        root_size=BASIC_DIRECTORY_INODE_SIZE; record=DIRECTORY_ENTRY_STRUCT.pack(root_size,1,EXTENDED_REGULAR_INODE_TYPE,len(b'empty')-1)+b'empty'
        directory=DIRECTORY_HEADER_STRUCT.pack(0,0,1)+record; directory_size=DIRECTORY_POSITION_OFFSET+len(directory)
        root=INODE_HEADER_STRUCT.pack(BASIC_DIRECTORY_INODE_TYPE,0,0,0,0,1)+BASIC_DIRECTORY_INODE_BODY_STRUCT.pack(0,2,directory_size,0,0)
        empty=INODE_HEADER_STRUCT.pack(EXTENDED_REGULAR_INODE_TYPE,0,0,0,0,2)+EXTENDED_REGULAR_INODE_BODY_STRUCT.pack(0,0,0,1,SQUASHFS_INVALID_FRAGMENT,0,0)
        inode=root+empty; istart=96; dstart=istart+2+len(inode); raw=bytearray(dstart+2+len(directory))
        raw[:96]=struct.pack('<IIIIIHHHHHHQQQQQQQQ',SQUASHFS_MAGIC,2,0,4096,0,6,12,0,1,4,0,0,len(raw),0,SQUASHFS_INVALID_BLK,istart,dstart,0,0)
        raw[istart:istart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(inode)); raw[istart+2:dstart]=inode
        raw[dstart:dstart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(directory)); raw[dstart+2:]=directory
        directory_handle=tempfile.TemporaryDirectory(); path=Path(directory_handle.name)/'extended-empty.sqfs'; path.write_bytes(raw); self.addCleanup(directory_handle.cleanup); return SquashFSImage(path)
    def physical_ool_xattr_node(self, *, inline=False):
        """Attach a real one-entry OOL XAttr table to a compact graph image."""
        image=self.tree(); raw=bytearray(image.image.read_bytes()); payload=XAttrSemanticTransportStage22C2Test.RAW
        name=b'capability'; entry=struct.pack('<HH',0x2 if inline else 0x102,len(name))+name
        entry+=struct.pack('<I',len(payload) if inline else 8); entry+=payload if inline else struct.pack('<Q',len(entry)+8); metadata=entry if inline else entry+struct.pack('<I',len(payload))+payload
        xstart=len(raw); idmeta=xstart+2+len(metadata); table=idmeta+2+16; end=table+24
        raw.extend(b'\0'*(end-len(raw)))
        raw[xstart:xstart+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|len(metadata)); raw[xstart+2:idmeta]=metadata
        raw[idmeta:idmeta+2]=struct.pack('<H',METADATA_UNCOMPRESSED_BIT|16); raw[idmeta+2:table]=XATTR_ID_STRUCT.pack(0,1,len(entry))
        raw[table:table+16]=struct.pack('<QII',xstart,1,0); raw[table+16:end]=struct.pack('<Q',idmeta)
        raw[40:48]=struct.pack('<Q',end); raw[56:64]=struct.pack('<Q',table); image.image.write_bytes(raw)
        image.superblock=None; fs=open_filesystem(image); header=SquashFSInodeHeader(9,0,0,0,0,2)
        body=SquashFSExtendedRegularInode(header,0,0,0,1,SQUASHFS_INVALID_FRAGMENT,0,0); inode=SquashFSInode(SquashFSMetadataReference(0,0),header,body)
        identity=SquashFSInodeIdentity(inode.reference,2)
        return fs,SquashFSRegularFileNode(fs,identity,inode,b'xattr',b'/',b'/xattr',SquashFSNodeType.REGULAR_FILE)
    def test_wrong_node_types_and_xattr_free_node(self):
        fs=open_filesystem(self.tree()); file, link=list_children(fs,get_root(fs)).children
        with self.assertRaises(SquashFSNodeTypeError): read_node_bytes(fs,link)
        with self.assertRaises(SquashFSNodeTypeError): read_node_symlink(fs,file)
        self.assertIsNone(read_node_xattrs(fs,file))
    def test_empty_basic_regular_and_symlink_content_helpers(self):
        fs=open_filesystem(self.tree()); file, link=list_children(fs,get_root(fs)).children
        self.assertEqual(read_node_bytes(fs,file),b''); self.assertEqual(read_node_bytes(fs,file),b'')
        self.assertEqual(read_node_symlink(fs,link),''); self.assertEqual(read_node_symlink(fs,link),'')
        self.assertEqual((file.absolute_path,link.absolute_path),(b'/file',b'/link'))
    def test_content_reader_failures_are_wrapped_with_causes(self):
        fs=open_filesystem(self.tree()); file, link=list_children(fs,get_root(fs)).children
        for symbol,error,node,helper in (('read_basic_regular_file',SquashFSRegularFileError('file'),file,read_node_bytes),('read_basic_symlink',SquashFSSymlinkError('link'),link,read_node_symlink)):
            with patch.object(squashfs,symbol,side_effect=error):
                with self.assertRaises(SquashFSNodeContentError) as caught: helper(fs,node)
            self.assertIs(caught.exception.__cause__,error)
        foreign=open_filesystem(self.tree())
        with self.assertRaises(SquashFSFilesystemGraphError): read_node_bytes(foreign,file)
    def test_xattr_public_boundary_and_no_eager_graph_reads(self):
        fs=open_filesystem(self.tree()); file=lookup_path(fs,b'/file'); error=SquashFSXAttrInodeError('xattr')
        with patch.object(squashfs,'read_inode_xattrs',side_effect=error):
            with self.assertRaises(SquashFSNodeContentError) as caught: read_node_xattrs(fs,file)
        self.assertIs(caught.exception.__cause__,error)
        names=('read_node_bytes','read_node_symlink','read_node_xattrs','read_basic_regular_file','read_extended_regular_file','read_basic_symlink','read_extended_symlink','read_inode_xattrs','read_and_decode_xattr')
        with ExitStack() as stack:
            spies=[stack.enter_context(patch.object(squashfs,name)) for name in names]; fresh=open_filesystem(self.tree()); root=get_root(fresh); list_children(fresh,root); lookup_path(fresh,b'/file'); walk_filesystem(fresh); build_filesystem_index(fresh)
        self.assertTrue(all(spy.call_count==0 for spy in spies))
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_real_regular_wrappers_cover_basic_extended_and_fragment_nodes(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); nodes=walk_filesystem(fs); ping=lookup_path(fs,b'/bin/ping')
        payload=read_node_bytes(fs,ping); self.assertEqual((payload[:4],payload, ping),(b'\x7fELF',read_node_bytes(fs,ping),lookup_path(fs,b'/bin/ping')))
        extended=next(node for node in nodes if isinstance(node,SquashFSRegularFileNode) and isinstance(node.inode.body,SquashFSExtendedRegularInode))
        self.assertEqual(read_node_bytes(fs,extended),read_node_bytes(fs,extended))
        fragment=next(node for node in nodes if isinstance(node,SquashFSRegularFileNode) and getattr(node.inode.body,'fragment',SQUASHFS_INVALID_FRAGMENT)!=SQUASHFS_INVALID_FRAGMENT)
        self.assertEqual(read_node_bytes(fs,fragment),read_node_bytes(fs,fragment))
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_ping_xattr_semantics(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); ping=lookup_path(fs,b'/bin/ping'); values=read_node_xattrs(fs,ping)
        entry=next(item for item in values.entries if item.full_name==b'security.capability'); decoded=read_and_decode_xattr(fs.image,entry)
        value=decoded.semantic_value
        self.assertIsInstance(ping,SquashFSRegularFileNode); self.assertFalse(entry.out_of_line); self.assertEqual((entry.value.hex(),decoded.known,decoded.decoder_id,value.effective,value.permitted.raw_mask,value.permitted.capability_numbers,value.permitted.known_names,value.inheritable.capability_numbers,value.root_id),('0100000200200000000000000000000000000000',True,'linux.security.capability',True,0x2000,(13,),('CAP_NET_RAW',),(),None)); self.assertEqual(decoded,read_and_decode_xattr(fs.image,entry))
    def test_node_wrapper_physical_ool_xattr_and_semantic_snapshots(self):
        fs,node=self.physical_ool_xattr_node(); before=(node,node.inode,fs.superblock)
        listing=read_node_xattrs(fs,node); entry=listing.entries[0]; decoded=read_and_decode_xattr(fs.image,entry)
        snapshot=(listing,listing.entries,entry,decoded,decoded.semantic_value,decoded.raw_value,node,node.inode,fs.superblock)
        self.assertEqual((entry.full_name,entry.out_of_line,entry.value,entry.out_of_line_reference,decoded.known,decoded.raw_value,decoded.semantic_value.permitted.known_names),(b'security.capability',True,None,len(struct.pack('<HH',0x102,len(b'capability'))+b'capability'+struct.pack('<I',8)+struct.pack('<Q',0)),True,XAttrSemanticTransportStage22C2Test.RAW,('CAP_CHOWN',)))
        self.assertEqual(read_and_decode_xattr(fs.image,read_node_xattrs(fs,node).entries[0]),decoded)
        self.assertEqual((listing,listing.entries,entry,decoded,decoded.semantic_value,decoded.raw_value,node,node.inode,fs.superblock),snapshot); self.assertEqual((node,node.inode,fs.superblock),before)
        with self.assertRaises(AttributeError): entry.value=b'changed'
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_extended_regular_physical_content(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); node=next(n for n in walk_filesystem(fs) if isinstance(n,SquashFSRegularFileNode) and isinstance(n.inode.body,SquashFSExtendedRegularInode))
        payload=read_node_bytes(fs,node); self.assertGreater(len(payload),0); self.assertEqual(payload,read_node_bytes(fs,node)); self.assertEqual(node,lookup_path(fs,node.absolute_path))
    def test_extended_symlink_physical_wrapper_path(self):
        for target in (b'../relative',b'/absolute//target'):
            fs=open_filesystem(self.extended_symlink_tree(target)); node=lookup_path(fs,b'/link')
            self.assertIsInstance(node,SquashFSSymlinkNode); self.assertIsInstance(node.inode.body,SquashFSExtendedSymlinkInode)
            self.assertEqual((read_node_symlink(fs,node),read_node_symlink(fs,node),node.absolute_path),(target.decode(),target.decode(),b'/link'))
    def test_extended_symlink_error_chain(self):
        fs=open_filesystem(self.extended_symlink_tree()); node=lookup_path(fs,b'/link'); error=SquashFSSymlinkError('malformed')
        with patch.object(squashfs,'read_extended_symlink',side_effect=error):
            with self.assertRaises(SquashFSNodeContentError) as caught: read_node_symlink(fs,node)
        self.assertIs(caught.exception.__cause__,error)
    def test_unknown_inline_and_ool_semantic_results(self):
        inline=XAttrSemanticTransportStage22C2Test.inline_entry(b'user.note',b'inline'); image=XAttrSemanticTransportStage22C2Test.target_image(self,b'ool')
        ool=XAttrSemanticTransportStage22C2Test.ool_entry(b'user.note')
        self.assertEqual((read_and_decode_xattr(image,inline).known,read_and_decode_xattr(image,ool).known),(False,False))
    def test_semantic_decoder_and_ool_error_chains(self):
        image=XAttrSemanticTransportStage22C2Test.target_image(self,XAttrSemanticTransportStage22C2Test.RAW); entry=XAttrSemanticTransportStage22C2Test.ool_entry()
        with patch.object(squashfs,'read_xattr_out_of_line_value',side_effect=SquashFSXAttrValueError('bad')):
            with self.assertRaises(XAttrSemanticValueResolutionError) as caught: read_and_decode_xattr(image,entry)
        self.assertIsInstance(caught.exception.__cause__,SquashFSXAttrValueError)
        with self.assertRaises(XAttrSemanticDecoderError) as caught: read_and_decode_xattr(XAttrSemanticTransportStage22C2Test.target_image(self,b''),entry)
        self.assertIsInstance(caught.exception.__cause__,LinuxCapabilityError)
    def test_node_xattr_public_error_boundary(self):
        fs,node=self.physical_ool_xattr_node(); error=SquashFSXAttrInodeError('bad')
        with patch.object(squashfs,'read_inode_xattrs',side_effect=error):
            with self.assertRaises(SquashFSNodeContentError) as caught: read_node_xattrs(fs,node)
        self.assertIs(caught.exception.__cause__,error)
    def test_content_and_xattr_snapshots_are_immutable(self):
        fs,node=self.physical_ool_xattr_node(); listing=read_node_xattrs(fs,node); entry=listing.entries[0]; result=read_and_decode_xattr(fs.image,entry)
        snapshot=(fs,node,listing,entry,result,result.semantic_value,result.raw_value)
        self.assertEqual(snapshot,(fs,node,read_node_xattrs(fs,node),read_node_xattrs(fs,node).entries[0],read_and_decode_xattr(fs.image,entry),result.semantic_value,result.raw_value))
        for value,attribute in ((node,'absolute_path'),(listing,'entries'),(entry,'value'),(result,'raw_value')):
            with self.assertRaises(AttributeError): setattr(value,attribute,b'changed')
    def test_extended_empty_regular_file_through_node_wrapper(self):
        fs=open_filesystem(self.tree()); base=lookup_path(fs,b'/file'); header=SquashFSInodeHeader(9,0,0,0,0,2); body=SquashFSExtendedRegularInode(header,0,0,0,1,SQUASHFS_INVALID_FRAGMENT,0,0); inode=SquashFSInode(base.inode.reference,header,body); node=SquashFSRegularFileNode(fs,SquashFSInodeIdentity(inode.reference,2),inode,b'empty',b'/',b'/empty',SquashFSNodeType.REGULAR_FILE)
        snapshot=(fs,node,node.inode); self.assertEqual((read_node_bytes(fs,node),read_node_bytes(fs,node)),(b'',b'')); self.assertEqual((fs,node,node.inode),snapshot)
    def test_extended_regular_binary_payload_is_exact(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); node=lookup_path(fs,b'/bin/ping'); payload=read_node_bytes(fs,node)
        self.assertIsInstance(node.inode.body,SquashFSExtendedRegularInode); self.assertEqual(payload,read_extended_regular_file(fs.image,fs.inode_stream,node.inode)); self.assertEqual(payload[:4],b'\x7fELF')
    def test_extended_fragment_backed_file_reconstructs_exactly(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); node=next(n for n in walk_filesystem(fs) if isinstance(n,SquashFSRegularFileNode) and isinstance(n.inode.body,SquashFSExtendedRegularInode) and n.inode.body.fragment!=SQUASHFS_INVALID_FRAGMENT)
        snapshot=(fs,node,node.inode); payload=read_node_bytes(fs,node); self.assertEqual((payload,read_node_bytes(fs,node),len(payload)),(read_extended_regular_file(fs.image,fs.inode_stream,node.inode),payload,node.inode.body.file_size)); self.assertEqual((fs,node,node.inode),snapshot)
    def test_extended_regular_reader_error_preserves_cause(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); node=lookup_path(fs,b'/bin/ping'); error=SquashFSRegularFileError('extended')
        with patch.object(squashfs,'read_extended_regular_file',side_effect=error):
            with self.assertRaises(SquashFSNodeContentError) as caught: read_node_bytes(fs,node)
        self.assertIs(caught.exception.__cause__,error)
    def test_regular_read_preserves_filesystem_and_node_snapshots(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); basic=next(n for n in walk_filesystem(fs) if isinstance(n,SquashFSRegularFileNode) and isinstance(n.inode.body,SquashFSBasicRegularInode)); extended=lookup_path(fs,b'/bin/ping'); snapshot=(fs,basic,basic.inode,extended,extended.inode)
        read_node_bytes(fs,basic); read_node_bytes(fs,extended); self.assertEqual((fs,basic,basic.inode,extended,extended.inode),snapshot)
        with self.assertRaises(AttributeError): fs.image=None
    def test_basic_symlink_relative_absolute_and_empty_targets(self):
        for target in (b'../relative',b'/absolute//target',b''):
            fs=open_filesystem(self.extended_symlink_tree(target,extended=False)); node=lookup_path(fs,b'/link'); snapshot=(fs,node,node.inode)
            self.assertIsInstance(node.inode.body,SquashFSBasicSymlinkInode); self.assertEqual((read_node_symlink(fs,node),read_node_symlink(fs,node)),(target.decode(),target.decode())); self.assertEqual((fs,node,node.inode),snapshot)
    def test_read_node_symlink_rejects_foreign_filesystem_node(self):
        first=open_filesystem(self.extended_symlink_tree(b'x',extended=False)); second=open_filesystem(self.extended_symlink_tree(b'y',extended=False)); node=lookup_path(first,b'/link')
        with self.assertRaises(SquashFSFilesystemGraphError): read_node_symlink(second,node)
    def test_symlink_reads_preserve_filesystem_and_node_snapshots(self):
        for extended in (False,True):
            fs=open_filesystem(self.extended_symlink_tree(b'../x',extended=extended)); node=lookup_path(fs,b'/link'); snapshot=(fs,node,node.inode); read_node_symlink(fs,node); read_node_symlink(fs,node); self.assertEqual((fs,node,node.inode),snapshot)
    def test_inline_node_xattrs_with_table_and_none(self):
        fs,node=self.physical_ool_xattr_node(inline=True); table=read_xattr_id_table(fs.image); snapshot=(node,table,table.metadata_block_offsets)
        first=read_node_xattrs(fs,node,table); second=read_node_xattrs(fs,node)
        self.assertEqual((first.entries[0].full_name,first.entries[0].value,first.entries[0].out_of_line,first,second),(b'security.capability',XAttrSemanticTransportStage22C2Test.RAW,False,second,first)); self.assertEqual((node,table,table.metadata_block_offsets),snapshot)
    def test_read_node_xattrs_reuses_supplied_table(self):
        fs,node=self.physical_ool_xattr_node(); table=read_xattr_id_table(fs.image)
        with patch.object(squashfs,'read_inode_xattrs',wraps=read_inode_xattrs) as reader: result=read_node_xattrs(fs,node,table)
        self.assertEqual((reader.call_args.args,(result.entries[0].full_name,table)),((fs.image,node.inode,table),(b'security.capability',table)))
    def test_invalid_table_and_inode_xattr_id_are_typed(self):
        fs,node=self.physical_ool_xattr_node()
        for bad_table in (object(),):
            with self.assertRaises(SquashFSNodeContentError): read_node_xattrs(fs,node,bad_table)
        bad=SquashFSExtendedRegularInode(node.inode.header,0,0,0,1,SQUASHFS_INVALID_FRAGMENT,0,1); inode=SquashFSInode(node.inode.reference,node.inode.header,bad); foreign=SquashFSRegularFileNode(fs,SquashFSInodeIdentity(inode.reference,2),inode,b'bad',b'/',b'/bad',SquashFSNodeType.REGULAR_FILE)
        with self.assertRaises(SquashFSNodeContentError) as caught: read_node_xattrs(fs,foreign)
        self.assertIsInstance(caught.exception.__cause__,SquashFSXAttrInodeError)
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_real_ping_capability_snapshots_remain_immutable(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); node=lookup_path(fs,b'/bin/ping'); table=read_xattr_id_table(fs.image); listing=read_node_xattrs(fs,node,table); entry=next(x for x in listing.entries if x.full_name==b'security.capability'); result=read_and_decode_xattr(fs.image,entry,table); snapshot=(node,listing,entry,entry.value,result,result.semantic_value,table,table.metadata_block_offsets)
        again=read_and_decode_xattr(fs.image,read_node_xattrs(fs,node,table).entries[0],table); self.assertEqual((entry.value.hex(),result,again,(node,listing,entry,entry.value,result,result.semantic_value,table,table.metadata_block_offsets)),('0100000200200000000000000000000000000000',again,result,snapshot))
        with self.assertRaises(AttributeError): result.semantic_value.raw_value=b'changed'
    def test_physical_extended_empty_regular_file_via_lookup(self):
        filesystem=open_filesystem(self.extended_empty_regular_tree()); snapshots=(filesystem,filesystem.root_inode)
        with (patch.object(squashfs,'read_extended_regular_file',wraps=read_extended_regular_file) as extended,
              patch.object(squashfs,'read_basic_regular_file',wraps=read_basic_regular_file) as basic,
              patch.object(squashfs,'read_inode_xattrs',wraps=read_inode_xattrs) as xattrs,
              patch.object(squashfs,'read_basic_symlink',wraps=read_basic_symlink) as symlink):
            node=lookup_path(filesystem,b'/empty'); value=read_node_bytes(filesystem,node); repeated=read_node_bytes(filesystem,node)
        self.assertIsInstance(node,SquashFSRegularFileNode); self.assertIsInstance(node.inode.body,SquashFSExtendedRegularInode)
        self.assertEqual((node.absolute_path,node.raw_name,node.inode.body.file_size,value,repeated),(b'/empty',b'empty',0,b'',b''))
        self.assertEqual((extended.call_count,basic.call_count,xattrs.call_count,symlink.call_count),(2,0,0,0)); self.assertEqual((filesystem,filesystem.root_inode),snapshots)
        with self.assertRaises(AttributeError): node.absolute_path=b'/changed'


class SquashFSFilesystemROOTFSStage23DTest(unittest.TestCase):
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_final_api_facts(self):
        fs=open_filesystem(SquashFSImage(ROOTFS)); root=get_root(fs); listing=list_children(fs,root); index=build_filesystem_index(fs)
        self.assertEqual((len(listing.children),listing.children[0].absolute_path),(13,b'/bin'))
        self.assertEqual((len(index.nodes),len(index.paths)),(43433,43433))


class LinuxCapabilityNamesStage21C1Test(unittest.TestCase):
    def test_mapping_is_complete_immutable_and_exact(self):
        self.assertEqual(tuple(LINUX_CAPABILITY_NAMES),tuple(range(LINUX_CAP_LAST_KNOWN+1))); self.assertEqual((LINUX_CAPABILITY_NAMES[0],LINUX_CAPABILITY_NAMES[13],LINUX_CAPABILITY_NAMES[40]),('CAP_CHOWN','CAP_NET_RAW','CAP_CHECKPOINT_RESTORE'))
        self.assertEqual(len(set(LINUX_CAPABILITY_NAMES.values())),len(LINUX_CAPABILITY_NAMES))
        with self.assertRaises(TypeError): LINUX_CAPABILITY_NAMES[0]='x'
    def test_known_unknown_and_rootfs_classification(self):
        value=decode_linux_file_capabilities(bytes.fromhex('0100000200200000000000000000000000000000')); self.assertEqual((value.permitted.known_names,value.permitted.unknown_numbers),(('CAP_NET_RAW',),()))
        future=decode_linux_file_capabilities(struct.pack('<IIIII',VFS_CAP_REVISION_2,0,0,1<<9,0)); self.assertEqual((future.permitted.known_names,future.permitted.unknown_numbers), ((),(41,)))
    def test_direct_invariants_and_repeated_results(self):
        with self.assertRaises(ValueError): LinuxCapabilitySet(1,(0,),(),())
        with self.assertRaises(ValueError): LinuxCapabilitySet(1,(0,),('CAP_NET_RAW',),())
        raw=struct.pack('<IIIII',VFS_CAP_REVISION_2,1,0,0,0); self.assertEqual(decode_linux_file_capabilities(raw),decode_linux_file_capabilities(raw))
    def test_direct_zero_and_mixed_invariants(self):
        self.assertEqual(LinuxCapabilitySet(0,(),(),()),LinuxCapabilitySet(0,(),(),()))
        self.assertEqual(LinuxCapabilitySet((1<<0)|(1<<41),(0,41),('CAP_CHOWN',),(41,)).unknown_numbers,(41,))
        for args in ((1,(0,),(),()),((1<<41),(41),(),()),(1,(0,),('CAP_CHOWN',),(41,))):
            with self.assertRaises(ValueError): LinuxCapabilitySet(*args)
    def test_zero_mixed_ordering_and_revision_classification(self):
        zero=decode_linux_file_capabilities(struct.pack('<IIIII',VFS_CAP_REVISION_2,0,0,0,0)); self.assertEqual((zero.permitted.capability_numbers,zero.permitted.known_names,zero.permitted.unknown_numbers), ((),(),()))
        mixed=decode_linux_file_capabilities(struct.pack('<IIIII',VFS_CAP_REVISION_2,(1<<0)|(1<<13),0,1<<9,0)); self.assertEqual((mixed.permitted.capability_numbers,mixed.permitted.known_names,mixed.permitted.unknown_numbers),((0,13,41),('CAP_CHOWN','CAP_NET_RAW'),(41,)))

class LinuxFileCapabilitiesRootFSStage21DTest(unittest.TestCase):
    RAW=bytes.fromhex('0100000200200000000000000000000000000000')
    def assert_fixture(self, raw):
        value=decode_linux_file_capabilities(raw)
        self.assertEqual((value.revision,value.effective,value.raw_magic_etc,value.raw_flags),(LinuxCapabilityRevision.REVISION_2,True,0x02000001,1))
        self.assertEqual((value.permitted.raw_mask,value.permitted.capability_numbers,value.permitted.known_names,value.permitted.unknown_numbers),(0x2000,(13,),('CAP_NET_RAW',),()))
        self.assertEqual((value.inheritable.raw_mask,value.inheritable.capability_numbers,value.root_id,value.raw_value),(0,(),None,raw))
        self.assertEqual(value,decode_linux_file_capabilities(raw))
    def test_embedded_rootfs_regression_fixture(self): self.assert_fixture(self.RAW)
    @unittest.skipUnless(ROOTFS.is_file(), 'UDM Pro ROOTFS fixture is unavailable')
    def test_live_rootfs_capability_value_matches_observation(self):
        image=SquashFSImage(ROOTFS); table=read_xattr_id_table(image); listing=read_xattr_list(image,read_xattr_id(image,0,table),table); entry=next(item for item in listing.entries if item.full_name==b'security.capability')
        self.assertFalse(entry.out_of_line); self.assertEqual(entry.value,self.RAW); self.assert_fixture(entry.value)

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
