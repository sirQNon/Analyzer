"""Extract files from an EXT4 image using an existing ``Ext4Image``."""

import hashlib
from pathlib import Path

from ext4 import Ext4Image


class FileExtractor:
    """Write files resolved and read by an ``Ext4Image`` to the host disk."""

    def __init__(self, fs: Ext4Image):
        self.fs = fs

    def get_sha256(self, source_path: str) -> str:
        """Return the SHA-256 checksum of a file stored in the image.

        This keeps consumers that only need file content metadata from having
        to create a temporary extracted copy on the host filesystem.
        """
        inode = self.fs.path_to_inode(source_path)

        if inode is None:
            raise FileNotFoundError(source_path)

        return hashlib.sha256(self.fs.read_file(inode)).hexdigest()

    def extract_file(
        self,
        source_path: str,
        destination_path: Path,
    ):
        inode = self.fs.path_to_inode(source_path)

        if inode is None:
            raise FileNotFoundError(source_path)

        data = self.fs.read_file(inode)
        destination_path = Path(destination_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        with open(destination_path, "wb") as output:
            output.write(data)

        return {
            "source": source_path,
            "destination": str(destination_path),
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
