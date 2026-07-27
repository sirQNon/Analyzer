from pathlib import Path

SIGNATURES = {
    b"EFI PART": "GPT Header",
    b"UBI#": "UBI Volume",
    b"hsqs": "SquashFS (little endian)",
    b"sqsh": "SquashFS (big endian)",
    b"\x53\xEF": "EXT Superblock Magic",
    b"U-Boot": "U-Boot String",
    b"FIT": "Flattened Image Tree",
    b"\x27\x05\x19\x56": "uImage Header",
    b"\xD0\x0D\xFE\xED": "Device Tree Blob",
    b"\x7FELF": "ELF Executable",
    b"-----BEGIN CERTIFICATE-----": "PEM Certificate",
    b"-----BEGIN RSA PRIVATE KEY-----": "RSA Private Key",
    b"ssh-rsa": "SSH RSA Key",
    b"ubnt": "Ubiquiti String",
    b"UniFi": "UniFi String",
}


def scan_signatures(path: Path, max_read_mb: int = 32):
    """
    Ищет известные сигнатуры в первых max_read_mb мегабайтах файла.
    """

    max_bytes = max_read_mb * 1024 * 1024

    results = []

    with open(path, "rb") as f:

        data = f.read(max_bytes)

    for signature, name in SIGNATURES.items():

        pos = data.find(signature)

        if pos != -1:

            results.append((name, pos))

    return results