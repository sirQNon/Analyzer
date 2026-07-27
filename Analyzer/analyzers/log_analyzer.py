"""Log-file analyzer."""

from utils import ExtensionAnalyzer


class LogAnalyzer(ExtensionAnalyzer):
    """Find log and journal text files."""

    EXTENSIONS = frozenset({".log", ".txt", ".journal"})
