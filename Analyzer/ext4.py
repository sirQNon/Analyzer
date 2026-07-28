import struct
from pathlib import Path
from extent_tree import ExtentTree


EXT4_MAGIC = 0xEF53


class Ext4Image:

    def __init__(self, image):

        self.image = Path(image)
        self.superblock = None
        self.extents = ExtentTree(self)

    def read_superblock(self):

        with open(self.image, "rb") as f:

            f.seek(1024)
            sb = f.read(1024)

        magic = struct.unpack_from("<H", sb, 56)[0]

        if magic != EXT4_MAGIC:
            return None

        block_size = 1024 << struct.unpack_from("<I", sb, 24)[0]

        self.superblock = {
            "block_size": block_size,
            "inode_size": struct.unpack_from("<H", sb, 88)[0],
            "blocks_count": struct.unpack_from("<I", sb, 4)[0],
            "inodes_count": struct.unpack_from("<I", sb, 0)[0],
            "blocks_per_group": struct.unpack_from("<I", sb, 32)[0],
            "inodes_per_group": struct.unpack_from("<I", sb, 40)[0],
            "first_data_block": struct.unpack_from("<I", sb, 20)[0],
        }

        return self.superblock

    def print_superblock(self):

        if self.superblock is None:
            self.read_superblock()

        if self.superblock is None:

            print("Not EXT4")
            return

        print("=" * 60)
        print(self.image.name)
        print("=" * 60)

        for k, v in self.superblock.items():

            print(f"{k:20} : {v}")
    

        print()

    def read_group_descriptors(self):

        if self.superblock is None:
            self.read_superblock()

        block_size = self.superblock["block_size"]
        blocks = self.superblock["blocks_count"]
        per_group = self.superblock["blocks_per_group"]

        groups = (blocks + per_group - 1) // per_group

        if block_size == 1024:
            gdt_offset = 2048
        else:
            gdt_offset = block_size

        descriptors = []

        with open(self.image, "rb") as f:

            f.seek(gdt_offset)

            for _ in range(groups):

                desc = f.read(64)

                if len(desc) < 64:
                    break

                descriptors.append({

                    "block_bitmap": struct.unpack_from("<I", desc, 0)[0],

                    "inode_bitmap": struct.unpack_from("<I", desc, 4)[0],

                    "inode_table": struct.unpack_from("<I", desc, 8)[0],

                    "free_blocks": struct.unpack_from("<H", desc, 12)[0],

                    "free_inodes": struct.unpack_from("<H", desc, 14)[0],

                    "used_dirs": struct.unpack_from("<H", desc, 16)[0],
                })

        self.group_descriptors = descriptors

        return descriptors
    
    def read_inode(self, inode_number):

        if self.superblock is None:
            self.read_superblock()

        if not hasattr(self, "group_descriptors"):
            self.read_group_descriptors()

        inode_size = self.superblock["inode_size"]
        per_group = self.superblock["inodes_per_group"]
        block_size = self.superblock["block_size"]

        group = (inode_number - 1) // per_group
        index = (inode_number - 1) % per_group

        table_block = self.group_descriptors[group]["inode_table"]

        offset = table_block * block_size + index * inode_size

        with open(self.image, "rb") as f:

            f.seek(offset)

            inode = f.read(inode_size)

        return inode
    
    def parse_inode(self, inode):

        return {
            "mode": struct.unpack_from("<H", inode, 0)[0],
            "uid": struct.unpack_from("<H", inode, 2)[0],
            "gid": struct.unpack_from("<H", inode, 24)[0],
            "size": struct.unpack_from("<I", inode, 4)[0],
            "atime": struct.unpack_from("<I", inode, 8)[0],
            "ctime": struct.unpack_from("<I", inode, 12)[0],
            "mtime": struct.unpack_from("<I", inode, 16)[0],
            "links": struct.unpack_from("<H", inode, 26)[0],
            "blocks": struct.unpack_from("<I", inode, 28)[0],
            "flags": struct.unpack_from("<I", inode, 32)[0],
             # первые 60 байт — массив i_block
            "block": inode[40:100],
        }

    def get_inode(self, inode_number):

        raw = self.read_inode(inode_number)

        return self.parse_inode(raw)

    def read_directory(self, inode_number):

        raw_inode = self.read_inode(inode_number)

        info = self.parse_inode(raw_inode)

        extents = self.extents.get_extents(raw_inode)

        entries = []

        for extent in extents:

            block = self.read_block(extent["physical_block"])

            entries.extend(self.parse_directory(block))

        return entries
    
    def iter_directory_tree(self, inode_number=2, path="/", excluded_names=None):

        excluded_names = set(excluded_names or ())
        visited_directories = set()

        def traverse(current_inode, current_path):

            if current_inode in visited_directories:
                return

            visited_directories.add(current_inode)

            for entry in self.read_directory(current_inode):

                name = entry["name"]

                if name in (".", "..") or name in excluded_names:
                    continue

                base = current_path if current_path == "/" else current_path.rstrip("/") + "/"
                full_path = base + name
                item = dict(entry)
                item["path"] = full_path

                yield item

                if entry["type"] == 2:
                    yield from traverse(entry["inode"], full_path)

        yield from traverse(inode_number, path)

    def walk(self, inode_number=2, path="/", output_path=None):

        print("walk()", inode_number, path)

        outfile = Path(output_path) if output_path is not None else Path(__file__).parent / "tree.txt"

        for entry in self.iter_directory_tree(inode_number, path):

            with open(outfile, "a", encoding="utf-8") as out:
                out.write(entry["path"] + "\n")

            if entry["type"] == 2:
                print("walk()", entry["inode"], entry["path"] + "/")

    def parse_extent_header(self, inode):

        extent = inode[40:52]

        return {
            "magic": struct.unpack_from("<H", extent, 0)[0],
            "entries": struct.unpack_from("<H", extent, 2)[0],
            "max": struct.unpack_from("<H", extent, 4)[0],
            "depth": struct.unpack_from("<H", extent, 6)[0],
            "generation": struct.unpack_from("<I", extent, 8)[0],
        }
    def read_block(self, block_number):

        if self.superblock is None:
            self.read_superblock()

        block_size = self.superblock["block_size"]

        with open(self.image, "rb") as f:

            f.seek(block_number * block_size)

            return f.read(block_size)

    def parse_directory(self, block):

        offset = 0
        entries = []

        while offset < len(block):

            inode = struct.unpack_from("<I", block, offset)[0]
            rec_len = struct.unpack_from("<H", block, offset + 4)[0]

            if inode == 0:
                if rec_len == 0:
                    break

                offset += rec_len
                continue

            name_len = block[offset + 6]
            file_type = block[offset + 7]

            name = block[offset + 8:offset + 8 + name_len].decode(
                "utf-8",
                errors="ignore",
            )

            entries.append({
                "inode": inode,
                "type": file_type,
                "name": name,
            })

            offset += rec_len

        return entries

    def find_in_directory(self, dir_inode, name):

        entries = self.read_directory(dir_inode)

        for entry in entries:

            if entry["name"] == name:
                return entry["inode"]

        return None

    def path_to_inode(self, path):

        if path == "/":
            return 2

        inode = 2

        parts = [p for p in path.split("/") if p]

        for part in parts:

            inode = self.find_in_directory(inode, part)

            if inode is None:
                return None

        return inode

    def read_path(self, path):

        inode = self.path_to_inode(path)

        if inode is None:
            return None

        return self.read_file(inode)

    def extract_file(self, image_path, output_path):

        data = self.read_path(image_path)

        if data is None:
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(data)

        return True

    def parse_extent_header_block(self, block):

        return {
            "magic": struct.unpack_from("<H", block, 0)[0],
            "entries": struct.unpack_from("<H", block, 2)[0],
            "max": struct.unpack_from("<H", block, 4)[0],
            "depth": struct.unpack_from("<H", block, 6)[0],
            "generation": struct.unpack_from("<I", block, 8)[0],
        }

        #
        # Index node
        #
        entry = inode[52:64]

        index = self.parse_extent_index(entry)

        leaf_block = (index["leaf_hi"] << 32) | index["leaf_lo"]

        block = self.read_block(leaf_block)

        header = self.parse_extent_header_block(block)

        extents = []

        offset = 12

        for _ in range(header["entries"]):

            entry = block[offset:offset + 12]

            logical = struct.unpack_from("<I", entry, 0)[0]
            length = struct.unpack_from("<H", entry, 4)[0]
            start_hi = struct.unpack_from("<H", entry, 6)[0]
            start_lo = struct.unpack_from("<I", entry, 8)[0]

            extents.append({
                "logical_block": logical,
                "length": length,
                "physical_block": (start_hi << 32) | start_lo,
            })

            offset += 12

        return extents

    def read_file(self, inode_number):

        raw_inode = self.read_inode(inode_number)

        info = self.parse_inode(raw_inode)

        extents = self.extents.get_extents(raw_inode)

        data = bytearray()

        for extent in extents:

            start = extent["physical_block"]

            for i in range(extent["length"]):

                data.extend(self.read_block(start + i))

        return bytes(data[:info["size"]])

    def read_file_range(self, inode_number, offset, size):

        if not isinstance(offset, int) or isinstance(offset, bool):
            raise TypeError("offset must be an integer")

        if not isinstance(size, int) or isinstance(size, bool):
            raise TypeError("size must be an integer")

        if offset < 0:
            raise ValueError("offset must not be negative")

        if size < 0:
            raise ValueError("size must not be negative")

        raw_inode = self.read_inode(inode_number)
        info = self.parse_inode(raw_inode)

        if size == 0 or offset >= info["size"]:
            return b""

        if self.superblock is None:
            self.read_superblock()

        block_size = self.superblock["block_size"]
        read_size = min(size, info["size"] - offset)
        first_block = offset // block_size
        last_block = (offset + read_size - 1) // block_size
        extents = self.extents.get_extents(raw_inode)
        data = bytearray()

        for logical_block in range(first_block, last_block + 1):
            block_start = logical_block * block_size
            slice_start = max(offset, block_start) - block_start
            slice_end = min(offset + read_size, block_start + block_size) - block_start

            for extent in extents:
                extent_end = extent["logical_block"] + extent["length"]
                if extent["logical_block"] <= logical_block < extent_end:
                    physical_block = extent["physical_block"] + (
                        logical_block - extent["logical_block"]
                    )
                    data.extend(self.read_block(physical_block)[slice_start:slice_end])
                    break
            else:
                data.extend(b"\x00" * (slice_end - slice_start))

        return bytes(data)
        
    def print_groups(self):

        groups = self.read_group_descriptors()

        print("=" * 60)
        print("Group Descriptors")
        print("=" * 60)

        for i, g in enumerate(groups):

            print(
                f"{i:3} "
                f"IT={g['inode_table']:8} "
                f"IB={g['inode_bitmap']:8} "
                f"BB={g['block_bitmap']:8} "
                f"DIRS={g['used_dirs']:5}"
            )

        print()
