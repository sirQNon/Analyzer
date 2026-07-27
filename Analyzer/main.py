# ==========================================================
# IMPORTS
# ==========================================================

from pathlib import Path

from analyzers import (
    CertificateAnalyzer,
    ConfigAnalyzer,
    DatabaseAnalyzer,
    FirmwareAnalyzer,
    LogAnalyzer,
)
from ext4 import Ext4Image
from extractor import extract_partition
from gpt import read_gpt
from scanner import deep_scan
from verify import (
    verify,
    first_difference,
)
from report import ReportBuilder

# ==========================================================
# PATHS
# ==========================================================

ROOT = Path(__file__).resolve().parent.parent

WHOLE = ROOT / "whole-002.img"

OUTPUT = ROOT / "extracted"

# ==========================================================
# VERIFY
# ==========================================================

def verify_images(parts):

    for p in parts:

        print("=" * 60)
        print(f"Partition : {p['name']}")

        extracted = extract_partition(WHOLE, p, OUTPUT)

        original = ROOT / f"{p['name']}.img"

        if original.exists():

            result = verify(original, extracted)

            if result["match"]:

                print("VERIFY : PASS")

            else:

                print("VERIFY : FAIL")

                print("Original :", result["original"])
                print("Extracted:", result["extracted"])

                diff = first_difference(original, extracted)

                if diff:

                    pos, a, b = diff

                    print(f"First difference : 0x{pos:X}")
                    print(f"Original byte    : 0x{a:02X}")
                    print(f"Extracted byte   : 0x{b:02X}")

        else:

            print("Original image not found.")

# ==========================================================
# SCANNER
# ==========================================================

def scan_images():

    print()
    print("=" * 70)
    print("DEEP SCAN")
    print("=" * 70)
    print()

    for image in (
        "boot.img",
        "recovery.img",
        "root.img",
        "persistent.img",
        "overlay.img",
    ):

        file = ROOT / image

        if file.exists():
            deep_scan(file)

# ==========================================================
# MAIN
# ==========================================================


def main():
    project_root = Path(__file__).resolve().parent.parent
    image_path = project_root / "root.img"
    report_path = Path(__file__).resolve().parent / "report.json"

    fs = Ext4Image(image_path)
    analyzers = {
        "config": ConfigAnalyzer(fs),
        "certificates": CertificateAnalyzer(fs),
        "databases": DatabaseAnalyzer(fs),
        "logs": LogAnalyzer(fs),
        "firmware": FirmwareAnalyzer(fs),
    }
    results = {name: analyzer.analyze() for name, analyzer in analyzers.items()}
    report = ReportBuilder(image_path).build(results)
    ReportBuilder.save_json(report, report_path)

if __name__ == "__main__":
    main()
