"""Shared EXT4 file discovery for extension-based analyzers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from ext4 import Ext4Image
from file_extractor import FileExtractor
from file_info import FileInfo


@dataclass(frozen=True)
class FileMatch:
    """Metadata returned for a discovered file."""

    path: str
    size: int
    sha256: str


class ExtensionAnalyzer:
    """Base class for analyzers that find files by extension."""

    EXTENSIONS: frozenset[str] = frozenset()

    def __init__(self, fs: Ext4Image):
        self.fs = fs
        self.file_info = FileInfo(fs)
        self.file_extractor = FileExtractor(fs)

    def analyze(self) -> list[dict[str, object]]:
        """Return matching regular files from the image root."""
        matches: list[FileMatch] = []
        extensions = tuple(extension.lower() for extension in self.EXTENSIONS)
        self._collect_matches(extensions, matches)
        return [asdict(match) for match in sorted(matches, key=lambda item: item.path)]

    def _collect_matches(
        self,
        extensions: tuple[str, ...],
        matches: list[FileMatch],
    ) -> None:
        for entry in self.fs.iter_directory_tree():
            if not self._matches_extension(entry["name"], extensions):
                continue

            info = self.file_info.get_info(entry["path"])

            if info["type"] != "file":
                continue

            matches.append(FileMatch(
                path=entry["path"],
                size=info["size"],
                sha256=self.file_extractor.get_sha256(entry["path"]),
            ))

    @staticmethod
    def _matches_extension(name: str, extensions: Iterable[str]) -> bool:
        lower_name = name.lower()
        return any(lower_name.endswith(extension) for extension in extensions)
