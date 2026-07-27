from pathlib import Path
import re
import time

PATTERNS = {
    "PEM Certificate": b"-----BEGIN CERTIFICATE-----",
    "RSA Private Key": b"-----BEGIN RSA PRIVATE KEY-----",
    "EC Private Key": b"-----BEGIN EC PRIVATE KEY-----",
    "OpenSSH Key": b"-----BEGIN OPENSSH PRIVATE KEY-----",
    "SQLite": b"SQLite format 3",
    "GZIP": b"\x1f\x8b\x08",
    "XZ": b"\xfd7zXZ",
    "ZIP": b"PK\x03\x04",
    "USTAR": b"ustar",
    "JSON": b"{",
    "XML": b"<?xml",
    "UBNT": b"ubnt",
    "UniFi": b"UniFi",
}

MAC_REGEX = re.compile(rb"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")


def deep_scan(path):

    path = Path(path)

    print("=" * 70)
    print(f"Deep Scan : {path.name}")
    print("=" * 70)

    start = time.time()

    counts = {}

    chunk_size = 4 * 1024 * 1024
    overlap = 512

    with open(path, "rb") as f:

        previous = b""

        while True:

            chunk = f.read(chunk_size)

            if not chunk:
                break

            data = previous + chunk

            for name, pattern in PATTERNS.items():
                counts[name] = counts.get(name, 0) + data.count(pattern)

            counts["MAC"] = counts.get("MAC", 0) + len(MAC_REGEX.findall(data))

            previous = data[-overlap:]

    elapsed = time.time() - start

    print()

    for name in sorted(counts):

        if counts[name]:
            print(f"{name:<20} {counts[name]}")

    print()
    print(f"Elapsed : {elapsed:.2f} sec")
    print()