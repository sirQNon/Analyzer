from pathlib import Path
import hashlib


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


def extract_partition(image: Path, partition: dict, output_dir: Path):

    output_dir.mkdir(exist_ok=True)

    outfile = output_dir / f"{partition['name']}.img"

    start = partition["first_lba"] * 512
    end = (partition["last_lba"] + 1) * 512
    size = end - start

    with open(image, "rb") as src:
        src.seek(start)

        with open(outfile, "wb") as dst:

            remaining = size

            while remaining > 0:

                chunk = src.read(min(1024 * 1024, remaining))

                if not chunk:
                    break

                dst.write(chunk)

                remaining -= len(chunk)

    return outfile