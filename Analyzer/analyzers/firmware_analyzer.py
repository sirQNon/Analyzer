"""Firmware-archive analyzer."""

from utils import ExtensionAnalyzer


class FirmwareAnalyzer(ExtensionAnalyzer):
    """Find firmware images and archive containers."""

    EXTENSIONS = frozenset({".bin", ".img", ".tar", ".tar.gz", ".tgz", ".zip"})
