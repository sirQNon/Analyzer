import struct
import uuid
from pathlib import Path


def guid_from_bytes(data: bytes) -> str:
    return str(uuid.UUID(bytes_le=data))


def utf16_name(raw: bytes) -> str:
    return raw.decode("utf-16le", errors="ignore").rstrip("\x00")


def read_gpt(image: Path):

    with open(image, "rb") as f:

        f.seek(512)
        header = f.read(92)

        if header[:8] != b"EFI PART":
            return None

        part_lba = struct.unpack("<Q", header[72:80])[0]
        entries = struct.unpack("<I", header[80:84])[0]
        entry_size = struct.unpack("<I", header[84:88])[0]

        f.seek(part_lba * 512)

        partitions = []

        for index in range(entries):

            entry = f.read(entry_size)

            if entry[:16] == b"\x00" * 16:
                continue

            type_guid = guid_from_bytes(entry[0:16])
            part_guid = guid_from_bytes(entry[16:32])

            first_lba = struct.unpack("<Q", entry[32:40])[0]
            last_lba = struct.unpack("<Q", entry[40:48])[0]
            flags = struct.unpack("<Q", entry[48:56])[0]

            name = utf16_name(entry[56:128])

            partitions.append({
                "index": index + 1,
                "name": name,
                "type_guid": type_guid,
                "part_guid": part_guid,
                "first_lba": first_lba,
                "last_lba": last_lba,
                "flags": flags,
                "size_bytes": (last_lba - first_lba + 1) * 512,
                "size_mb": (last_lba - first_lba + 1) * 512 / 1024 / 1024
            })

        return partitions