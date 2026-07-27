"""Build and save analysis reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


AnalysisResults = Mapping[str, Sequence[dict[str, object]]]


@dataclass(frozen=True)
class ReportBuilder:
    """Create a serializable report for one analyzed image."""

    image: Path

    def build(self, results: AnalysisResults) -> dict[str, object]:
        """Build a report from results returned by the registered analyzers."""
        files = {name: list(items) for name, items in results.items()}
        per_analyzer = {
            name: {
                "files": len(items),
                "bytes": sum(int(item["size"]) for item in items),
            }
            for name, items in files.items()
        }
        total_files = sum(statistics["files"] for statistics in per_analyzer.values())
        total_bytes = sum(statistics["bytes"] for statistics in per_analyzer.values())

        return {
            "image": str(self.image),
            "statistics": {
                "analyzers": per_analyzer,
                "total_files": total_files,
                "total_bytes": total_bytes,
            },
            "summary": {
                "analyzers": len(files),
                "files": total_files,
                "bytes": total_bytes,
            },
            "files": files,
        }

    @staticmethod
    def save_json(report: Mapping[str, object], output_path: Path) -> Path:
        """Save a report as UTF-8 JSON and return its path."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)

        return output_path
