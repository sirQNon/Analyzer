"""Recursive directory extraction from an EXT4 image."""

from pathlib import Path

from file_extractor import FileExtractor
from file_info import FileInfo


class DirectoryExtractor:
    """Extract a directory tree using the project's EXT4 APIs."""

    DIRECTORY_TYPE = 2
    FILE_TYPE = 1

    def __init__(self, fs, exclude=None):
        self.fs = fs
        self.exclude = set(exclude or ())
        self.file_info = FileInfo(fs)
        self.file_extractor = FileExtractor(fs)

    def extract(self, path: str, output_dir: Path):
        """Extract ``path`` while preserving its image-relative structure."""
        inode = self.fs.path_to_inode(path)

        if inode is None:
            raise FileNotFoundError(path)

        source_path = self._normalise_path(path)
        info = self.file_info.get_info(source_path)

        if info["type"] != "directory":
            raise NotADirectoryError(source_path)

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        self._directories = 0
        self._files = 0
        self._bytes = 0
        self._extracted_files = set()
        destination = output_dir / source_path.lstrip("/")
        destination.mkdir(parents=True, exist_ok=True)
        self._directories = 1

        print("[DIR]")
        print(source_path)
        print()

        for entry in self.fs.iter_directory_tree(
            inode,
            source_path,
            excluded_names=self.exclude,
        ):
            destination = output_dir / entry["path"].lstrip("/")

            if entry["type"] == self.DIRECTORY_TYPE:
                destination.mkdir(parents=True, exist_ok=True)
                self._directories += 1

                print("[DIR]")
                print(entry["path"])
                print()
                continue

            if entry["type"] != self.FILE_TYPE:
                continue

            if entry["inode"] in self._extracted_files:
                continue

            print("[FILE]")
            print(entry["path"])
            print(destination)
            print()

            result = self.file_extractor.extract_file(entry["path"], destination)
            self._extracted_files.add(entry["inode"])
            self._files += 1
            self._bytes += result["size"]

        report = {
            "directories": self._directories,
            "files": self._files,
            "bytes": self._bytes,
        }

        print("Directories:")
        print(report["directories"])
        print()
        print("Files:")
        print(report["files"])
        print()
        print("Bytes:")
        print(report["bytes"])

        return report

    @staticmethod
    def _normalise_path(path: str) -> str:
        return "/" if path == "/" else "/" + path.strip("/")
