"""Configuration-file analyzer."""

from utils import ExtensionAnalyzer


class ConfigAnalyzer(ExtensionAnalyzer):
    """Find JSON, YAML, and common configuration files."""

    EXTENSIONS = frozenset({
        ".json", ".yaml", ".yml", ".conf", ".cfg",
    })
