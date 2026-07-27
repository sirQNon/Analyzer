"""Database-file analyzer."""

from utils import ExtensionAnalyzer


class DatabaseAnalyzer(ExtensionAnalyzer):
    """Find common database files."""

    EXTENSIONS = frozenset({".sqlite", ".sqlite3", ".db", ".mdb"})
