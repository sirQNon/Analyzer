"""Content-aware analysis of UDM configuration files."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath

from ext4 import Ext4Image
from file_extractor import FileExtractor
from file_info import FileInfo


IP_PATTERN = re.compile(
    rb"(?<![\d.])(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
    rb"(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}(?![\d.])"
)
MAC_PATTERN = re.compile(rb"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])")
HOSTNAME_PATTERN = re.compile(
    rb"(?im)[\"']?hostname[\"']?\s*[:=]\s*[\"']?[a-z0-9][a-z0-9.-]*"
)
SECRET_WORDS = (b"password", b"passwd", b"secret", b"token", b"private_key", b"api_key")


@dataclass(frozen=True)
class UDMConfigResult:
    """One configuration file and its content-derived attributes."""

    path: str
    size: int
    sha256: str
    extension: str
    is_json: bool
    is_yaml: bool
    is_text: bool
    is_binary: bool
    json_valid: bool | None
    yaml_valid: bool | None
    encoding: str | None
    line_count: int
    empty_file: bool
    contains_password: bool
    contains_ip: bool
    contains_mac: bool
    contains_hostname: bool


class UDMConfigAnalyzer:
    """Inspect JSON, YAML, and CONF files found through the shared walker."""

    EXTENSIONS = frozenset({".json", ".yaml", ".yml", ".conf"})

    def __init__(self, fs: Ext4Image):
        self.fs = fs
        self.file_info = FileInfo(fs)
        self.file_extractor = FileExtractor(fs)

    def analyze(self) -> list[dict[str, object]]:
        """Return content-aware metadata for all supported configuration files."""
        results: list[UDMConfigResult] = []

        for entry in self.fs.iter_directory_tree():
            extension = PurePosixPath(entry["name"]).suffix.lower()

            if extension not in self.EXTENSIONS:
                continue

            info = self.file_info.get_info(entry["path"])

            if info["type"] != "file":
                continue

            data = self.fs.read_file(info["inode"])
            text, encoding = self._decode_text(data)
            is_text = text is not None
            is_json = extension == ".json"
            is_yaml = extension in {".yaml", ".yml"}

            results.append(UDMConfigResult(
                path=entry["path"],
                size=info["size"],
                sha256=self.file_extractor.get_sha256(entry["path"]),
                extension=extension,
                is_json=is_json,
                is_yaml=is_yaml,
                is_text=is_text,
                is_binary=not is_text,
                json_valid=self._validate_json(text) if is_json else None,
                yaml_valid=self._validate_yaml(text) if is_yaml else None,
                encoding=encoding,
                line_count=data.count(b"\n") + (1 if data else 0),
                empty_file=not data,
                contains_password=any(word in data.lower() for word in SECRET_WORDS),
                contains_ip=bool(IP_PATTERN.search(data)),
                contains_mac=bool(MAC_PATTERN.search(data)),
                contains_hostname=bool(HOSTNAME_PATTERN.search(data)),
            ))

        return [asdict(result) for result in sorted(results, key=lambda item: item.path)]

    @staticmethod
    def _decode_text(data: bytes) -> tuple[str | None, str | None]:
        if b"\x00" in data:
            return None, None

        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            try:
                return data.decode("utf-16"), "utf-16"
            except UnicodeDecodeError:
                return None, None

        try:
            return data.decode("utf-8-sig"), "utf-8"
        except UnicodeDecodeError:
            return None, None

    @staticmethod
    def _validate_json(text: str | None) -> bool:
        if text is None:
            return False

        try:
            json.loads(text)
        except (json.JSONDecodeError, TypeError, ValueError):
            return False

        return True

    @staticmethod
    def _validate_yaml(text: str | None) -> bool | None:
        if text is None:
            return False

        try:
            import yaml
        except ImportError:
            return None

        try:
            yaml.safe_load(text)
        except yaml.YAMLError:
            return False

        return True
