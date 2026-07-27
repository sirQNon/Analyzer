from pathlib import Path
import hashlib


def sha256(path: Path) -> str:

    h = hashlib.sha256()

    with open(path, "rb") as f:

        while True:

            data = f.read(1024 * 1024)

            if not data:
                break

            h.update(data)

    return h.hexdigest()


def verify(original: Path, extracted: Path):

    a = sha256(original)
    b = sha256(extracted)

    return {
        "match": a == b,
        "original": a,
        "extracted": b,
    }


def first_difference(file1: Path, file2: Path):

    chunk = 1024 * 1024
    offset = 0

    with open(file1, "rb") as a, open(file2, "rb") as b:

        while True:

            d1 = a.read(chunk)
            d2 = b.read(chunk)

            if not d1 and not d2:
                return None

            if d1 != d2:

                for i, (x, y) in enumerate(zip(d1, d2)):

                    if x != y:
                        return offset + i, x, y

            offset += len(d1)


def compare_files(file1: Path, file2: Path):

    chunk = 1024 * 1024

    total = 0
    different_blocks = 0
    different_bytes = 0

    with open(file1, "rb") as a, open(file2, "rb") as b:

        while True:

            d1 = a.read(chunk)
            d2 = b.read(chunk)

            if not d1 and not d2:
                break

            total += len(d1)

            if d1 != d2:

                different_blocks += 1

                different_bytes += sum(
                    x != y for x, y in zip(d1, d2)
                )

    return {
        "size": total,
        "different_blocks": different_blocks,
        "different_bytes": different_bytes,
    }