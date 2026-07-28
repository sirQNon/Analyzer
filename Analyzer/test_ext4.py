from pathlib import Path
from tempfile import TemporaryDirectory

import ext4
from ext4 import Ext4Image

LOG = open("analyzer_log.txt", "w", encoding="utf-8")

def log(*args):
    text = " ".join(str(x) for x in args)
    print(text)
    LOG.write(text + "\n")

print(ext4.__file__)
print(hasattr(ext4.Ext4Image, "parse_inode"))

ROOT = Path(__file__).resolve().parent.parent

for image in (
    "boot.img",
    "root.img",
    "persistent.img",
    "overlay.img",
):

    file = ROOT / image

    if file.exists():

        fs = Ext4Image(file)

        fs.print_superblock()
        fs.print_groups()

        inode = fs.read_inode(2)

        info = fs.parse_inode(inode)

        print("=" * 60)
        print("INODE #2")
        print("=" * 60)

        for k, v in info.items():
            print(f"{k:10} : {v}")

        extent = fs.parse_extent_header(inode)

        print("=" * 60)
        print("EXTENT HEADER")
        print("=" * 60)

        for k, v in extent.items():

            if k == "magic":
                print(f"{k:10} : 0x{v:04X}")
            else:
                print(f"{k:10} : {v}")

            print()

        extents = fs.extents.get_extents(inode)

        print("=" * 60)
        print("EXTENTS")
        print("=" * 60)

        for e in extents:
            print(e)

        extent = extents[0]

        block = fs.read_block(extent["physical_block"])

        print("=" * 60)
        print("ROOT DIRECTORY BLOCK")
        print("=" * 60)

        print(block[:128].hex())

        print()

        entries = fs.parse_directory(block)

        print("=" * 60)
        print("ROOT DIRECTORY")
        print("=" * 60)

        for e in entries:
            print(
                f"{e['inode']:8}  "
                f"{e['type']:2}  "
                f"{e['name']}"
            )

            print()


        print()
        print()
        print("=" * 60)
        print("FULL TREE")
        print("=" * 60)

        with TemporaryDirectory() as temporary_directory:
            fs.walk(output_path=Path(temporary_directory) / "tree.txt")

        print("=" * 60)
        print("READ FILE TEST")
        print("=" * 60)

        data = fs.read_file(2)

        print("bytes:", len(data))
        print(data[:64].hex())

        if image == "root.img":
            print("=" * 60)
            print("READ PATH TEST")
            print("=" * 60)

            data = fs.read_path("/rootfs")

            if data is None:
                print("File not found")
            else:
                print(data[:512].decode("utf-8", errors="ignore").encode("ascii", errors="backslashreplace").decode("ascii"))
