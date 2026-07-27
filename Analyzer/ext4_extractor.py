from pathlib import Path

from ext4 import Ext4Image
from analyzers import ConfigAnalyzer, UDMConfigAnalyzer
from directory_extractor import DirectoryExtractor
from file_extractor import FileExtractor
from file_info import FileInfo

ROOT = Path(__file__).resolve().parent.parent

IMAGE = ROOT / "root.img"

print("IMAGE =", IMAGE)
print("EXISTS =", IMAGE.exists())

fs = Ext4Image(IMAGE)

fs.read_superblock()
print(fs.superblock)
fs.read_group_descriptors()

OUTPUT = ROOT / "Extracted"

OUTPUT.mkdir(exist_ok=True)

def extract_directory(inode, image_path, output_path):

    entries = fs.read_directory(inode)

    for entry in entries:

        if entry["name"] in (".", ".."):
            continue

        src = image_path + "/" + entry["name"]
        dst = output_path / entry["name"]

        print(src)
        print("inode =", entry["inode"], "type =", entry["type"])
        if entry["name"] == "rootfs":

            raw = fs.read_inode(entry["inode"])

            header = fs.parse_extent_header(raw)

            print(header)

            extents = fs.extents.get_extents(raw)

            print("EXTENTS =", len(extents))

            for e in extents:
                print(e)

print("=" * 60)
print("EXT4 EXTRACTOR")
print("=" * 60)
print()

extract_directory(
    2,
    "",
    OUTPUT,
)

extractor = FileExtractor(fs)

result = extractor.extract_file(
    "/rootfs",
    OUTPUT / "rootfs",
)

print(result)

info = FileInfo(fs)

print(info.get_info("/rootfs"))

print("=" * 60)
print("CONFIG ANALYZER")
print("=" * 60)

analyzer = ConfigAnalyzer(fs)

files = analyzer.analyze()

print(f"Found {len(files)} configuration files")

for item in files[:20]:
    print(item)

if len(files) > 20:
    print(f"... and {len(files) - 20} more")

DirectoryExtractor(fs).extract("/", OUTPUT)

print("=" * 50)
print("UDM CONFIG ANALYZER")
print("=" * 50)

analyzer = UDMConfigAnalyzer(fs)
results = analyzer.analyze()

print(f"Found {len(results)} configuration files")

for item in results[:20]:
    print(item)

if len(results) > 20:
    print(f"... and {len(results) - 20} more")
