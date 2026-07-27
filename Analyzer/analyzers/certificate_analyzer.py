"""Certificate and key-file analyzer."""

from utils import ExtensionAnalyzer


class CertificateAnalyzer(ExtensionAnalyzer):
    """Find certificate, key, and PKCS container files."""

    EXTENSIONS = frozenset({".pem", ".crt", ".cer", ".key", ".p12", ".pfx"})
