"""UniFi operating-system inventory analyzer."""

from __future__ import annotations

import re
from typing import Any

from ext4 import Ext4Image
from file_info import FileInfo


DIRECTORIES = ("/etc", "/usr", "/var", "/data", "/root", "/home", "/config", "/persistent", "/overlay", "/tmp")
SERVICES = ("podman", "docker", "systemd", "busybox", "dropbear", "ssh", "nginx", "mongodb", "postgres", "redis")
PACKAGES = ("python", "java", "node")
CONFIGURATION_FILES = ("passwd", "shadow", "group", "fstab", "hostname", "hosts", "resolv.conf", "os-release", "machine-id")
KERNEL_PATTERN = re.compile(r"Linux version\s+(\S+)")
BUSYBOX_PATTERN = re.compile(rb"BusyBox\s+v?(\d+(?:\.\d+)+)")
ARCHITECTURE_PATTERN = re.compile(rb"(?i)\b(aarch64|arm64|arm|mips64|mips|x86_64|i[3-6]86)\b")


class UniFiAnalyzer:
    """Identify UniFi OS structure and common services from an EXT4 image."""

    def __init__(self, fs: Ext4Image):
        self.fs = fs
        self.file_info = FileInfo(fs)

    def analyze(self) -> dict[str, object]:
        """Return a structured inventory of the operating system image."""
        entries = list(self.fs.iter_directory_tree())
        directory_paths = {
            entry["path"]
            for entry in entries
            if entry["type"] == 2
        }
        files_by_name: dict[str, list[str]] = {}

        for entry in entries:
            if entry["type"] == 2:
                continue

            files_by_name.setdefault(entry["name"].lower(), []).append(entry["path"])

        busybox_paths = files_by_name.get("busybox", [])
        busybox_data = self._read_bytes(busybox_paths[0]) if busybox_paths else None
        os_release = self._read_os_release(entries)
        kernel_version = self._kernel_version(entries)

        return {
            "system": {
                "distribution": os_release.get("PRETTY_NAME") or os_release.get("NAME"),
                "kernel_version": kernel_version,
                "architecture": self._architecture(busybox_data),
                "busybox_version": self._busybox_version(busybox_data),
            },
            "filesystem": {
                "directories": {
                    directory: directory in directory_paths
                    for directory in DIRECTORIES
                },
            },
            "services": self._component_inventory(SERVICES, files_by_name),
            "packages": self._component_inventory(PACKAGES, files_by_name),
            "configuration": {
                name: sorted(files_by_name.get(name, []))
                for name in CONFIGURATION_FILES
            },
            "security": {
                "passwd": bool(files_by_name.get("passwd")),
                "shadow": bool(files_by_name.get("shadow")),
                "group": bool(files_by_name.get("group")),
                "machine_id": bool(files_by_name.get("machine-id")),
                "ssh": bool(files_by_name.get("ssh")),
                "dropbear": bool(files_by_name.get("dropbear")),
            },
        }

    @staticmethod
    def _component_inventory(
        names: tuple[str, ...],
        files_by_name: dict[str, list[str]],
    ) -> dict[str, dict[str, object]]:
        return {
            name: {
                "present": bool(files_by_name.get(name)),
                "paths": sorted(files_by_name.get(name, [])),
            }
            for name in names
        }

    def _read_os_release(self, entries: list[dict[str, Any]]) -> dict[str, str]:
        paths = {entry["path"] for entry in entries}

        for path in ("/etc/os-release", "/usr/lib/os-release"):
            if path not in paths:
                continue

            data = self._read_bytes(path)

            if data is None:
                continue

            values: dict[str, str] = {}

            for line in data.decode("utf-8", errors="ignore").splitlines():
                if "=" not in line or line.startswith("#"):
                    continue

                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"')

            return values

        return {}

    def _kernel_version(self, entries: list[dict[str, Any]]) -> str | None:
        paths = {entry["path"] for entry in entries}

        if "/proc/version" in paths:
            data = self._read_bytes("/proc/version")

            if data is not None:
                match = KERNEL_PATTERN.search(data.decode("utf-8", errors="ignore"))

                if match:
                    return match.group(1)

        module_prefix = "/lib/modules/"

        for path in paths:
            if path.startswith(module_prefix):
                version = path[len(module_prefix):].split("/", 1)[0]

                if version:
                    return version

        return None

    def _read_bytes(self, path: str) -> bytes | None:
        try:
            info = self.file_info.get_info(path)
        except FileNotFoundError:
            return None

        if info["type"] != "file":
            return None

        return self.fs.read_file(info["inode"])

    @staticmethod
    def _busybox_version(data: bytes | None) -> str | None:
        if data is None:
            return None

        match = BUSYBOX_PATTERN.search(data)
        return match.group(1).decode("ascii") if match else None

    @staticmethod
    def _architecture(data: bytes | None) -> str | None:
        if data is None:
            return None

        match = ARCHITECTURE_PATTERN.search(data)

        if match is None:
            return None

        value = match.group(1).decode("ascii").lower()
        return "arm64" if value == "aarch64" else value
