"""
processor.py
============
Orchestrates: read file → detect → redact → write outputs.

Privacy guarantee
-----------------
- Files are read in binary/text mode locally.
- Extracted text is held in RAM only.
- Outputs are written to the local /output directory.
- No subprocess, socket, urllib, requests, or http call is made here.
"""

import json
from pathlib import Path
from typing import List, Dict

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

from .detector import SensitiveDataDetector
from .redactor import TextRedactor
from .pdf_writer import generate_scrubbed_pdf


class DocumentProcessor:

    SUPPORTED = {".pdf", ".txt", ".csv", ".text"}

    def __init__(
        self,
        config_path: str = "config/settings.json",
        output_dir: str = "output",
        keep_last_four: bool = True,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.config_path = config_path
        self.config = self._load_config(config_path)

        custom_terms = self.config.get("custom_terms", [])
        self.detector = SensitiveDataDetector(custom_terms)
        self.redactor = TextRedactor(keep_last_four=keep_last_four)

    # ── config ──────────────────────────────────────────────────

    def _load_config(self, path: str) -> dict:
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_config(self) -> None:
        Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)
        self.config["custom_terms"] = self.detector.custom_terms
        Path(self.config_path).write_text(
            json.dumps(self.config, indent=2),
            encoding="utf-8",
        )

    # ── text extraction ─────────────────────────────────────────

    def _extract_pdf(self, path: Path) -> str:
        if not PDF_SUPPORT:
            raise RuntimeError(
                "pdfplumber not installed — run: pip install pdfplumber"
            )
        pages = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
        return "\n\n".join(pages)

    def _extract_plain(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def extract_text(self, path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            return self._extract_pdf(path)
        return self._extract_plain(path)

    # ── core processing ─────────────────────────────────────────

    def process_file(self, filepath) -> Dict:
        fp = Path(filepath)

        if not fp.exists():
            return {"success": False, "error": f"File not found: {fp}"}
        if fp.suffix.lower() not in self.SUPPORTED:
            return {"success": False, "error": f"Unsupported type: {fp.suffix}"}

        try:
            original = self.extract_text(fp)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        detections = self.detector.detect(original)
        redacted = self.redactor.redact(original, detections)
        report = self.redactor.generate_report(
            original, redacted, detections, filename=fp.name
        )

        stem = fp.stem
        out_scrubbed = self.output_dir / f"{stem}_SCRUBBED.txt"
        out_report = self.output_dir / f"{stem}_REPORT.txt"
        out_pdf = self.output_dir / f"{stem}_SCRUBBED.pdf"

        out_scrubbed.write_text(redacted, encoding="utf-8")
        out_report.write_text(report, encoding="utf-8")

        summary = self.detector.summary(detections)

        # Generate PDF (scrubbed content + report in one file)
        try:
            generate_scrubbed_pdf(
                scrubbed_text=redacted,
                report_text=report,
                output_path=out_pdf,
                source_filename=fp.name,
                detections_summary=summary,
            )
            pdf_path = str(out_pdf)
        except Exception as exc:
            print(f"[WARN] PDF generation failed: {exc}")
            pdf_path = None

        return {
            "success": True,
            "source_file": str(fp),
            "output_text": str(out_scrubbed),
            "output_pdf": pdf_path,
            "output_report": str(out_report),
            "detections_count": len(detections),
            "detections_summary": summary,
            "report": report,
        }

    def process_directory(self, directory) -> List[Dict]:
        d = Path(directory)
        files = [
            f for f in d.iterdir()
            if f.is_file() and f.suffix.lower() in self.SUPPORTED
        ]
        return [self.process_file(f) for f in files]
