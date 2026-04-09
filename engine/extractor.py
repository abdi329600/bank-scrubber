"""
extractor.py
============
Extraction pipeline orchestrator.
Classify → Extract → Normalize → Validate.
100% local — no network calls.
"""

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional

try:
    import pdfplumber
    PDF_OK = True
except ImportError:
    PDF_OK = False

try:
    from dateutil import parser as dateutil_parser
    DATEUTIL_OK = True
except ImportError:
    DATEUTIL_OK = False

from .transaction import Transaction, TransactionBatch, _cents
from .document_classifier import DocumentClassifier, DocumentType


def _parse_amount(raw: str) -> Optional[Decimal]:
    if not raw:
        return None
    cleaned = raw.strip().replace("$", "").replace(",", "").replace(" ", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_date(raw: str) -> str:
    if not raw:
        return ""
    if DATEUTIL_OK:
        try:
            return dateutil_parser.parse(raw, dayfirst=False).strftime("%Y-%m-%d")
        except (ValueError, OverflowError):
            pass
    return raw.strip()


def _clean_merchant(description: str) -> str:
    desc = description.upper().strip()
    for prefix in ["POS PURCHASE", "POS DEBIT", "DEBIT CARD",
                   "ACH DEBIT", "ACH CREDIT", "WIRE TRANSFER", "CHECK", "ATM"]:
        if desc.startswith(prefix):
            desc = desc[len(prefix):].strip(" -#")
    desc = re.sub(r"\s+#?\d{4,}$", "", desc)
    desc = re.sub(r"\s+REF\s*#?\S+$", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"\s+[A-Z]{2}\s+\d{5}$", "", desc)
    return desc.strip() or description.strip()


DATE_HEADERS = {"date", "posted date", "posting date", "trans date",
                "transaction date", "effective date", "post date"}
DESC_HEADERS = {"description", "memo", "details", "transaction",
                "narrative", "payee", "merchant", "name"}
AMOUNT_HEADERS = {"amount", "total", "sum"}
CREDIT_HEADERS = {"credit", "credits", "deposit", "deposits"}
DEBIT_HEADERS = {"debit", "debits", "withdrawal", "withdrawals", "charge"}


def _norm(h: str) -> str:
    return h.strip().lower().replace("_", " ")


class DocumentExtractor:

    def __init__(self):
        self.classifier = DocumentClassifier()

    def extract(self, filepath: str) -> TransactionBatch:
        fp = Path(filepath)
        if not fp.exists():
            raise FileNotFoundError(f"File not found: {fp}")

        ext = fp.suffix.lower()
        raw_text = self._get_text(fp, ext)
        classification = self.classifier.classify_with_fallback(raw_text)

        if ext == ".csv":
            txns = self._extract_csv(fp)
        elif ext == ".pdf":
            txns = self._extract_pdf(fp)
        elif ext in (".txt", ".text"):
            txns = self._extract_text(raw_text)
        else:
            raise ValueError(f"Unsupported: {ext}")

        for t in txns:
            t.source_document = fp.name
            if not t.merchant_clean:
                t.merchant_clean = _clean_merchant(t.description)

        batch = TransactionBatch(
            transactions=txns,
            source_document=fp.name,
            document_type=classification.document_type.value,
        )
        self._extract_metadata(raw_text, batch)
        return batch

    # ── Raw text ────────────────────────────────────────────────

    def _get_text(self, fp: Path, ext: str) -> str:
        if ext == ".pdf":
            if not PDF_OK:
                raise RuntimeError("pdfplumber not installed")
            pages = []
            with pdfplumber.open(fp) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        pages.append(t)
            return "\n\n".join(pages)
        return fp.read_text(encoding="utf-8", errors="replace")

    # ── CSV ─────────────────────────────────────────────────────

    def _extract_csv(self, fp: Path) -> List[Transaction]:
        rows = fp.read_text(encoding="utf-8", errors="replace").splitlines()
        if not rows:
            return []

        try:
            dialect = csv.Sniffer().sniff(rows[0], delimiters=",\t|;")
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(rows, dialect=dialect)
        if reader.fieldnames is None:
            return []

        hmap = {_norm(h): h for h in reader.fieldnames}
        date_col = self._find(hmap, DATE_HEADERS)
        desc_col = self._find(hmap, DESC_HEADERS)
        amt_col = self._find(hmap, AMOUNT_HEADERS)
        cr_col = self._find(hmap, CREDIT_HEADERS)
        dr_col = self._find(hmap, DEBIT_HEADERS)

        txns: List[Transaction] = []
        for row in reader:
            date = _parse_date(row.get(date_col, "")) if date_col else ""
            desc = row.get(desc_col, "").strip() if desc_col else ""
            if not desc:
                continue

            if amt_col:
                amt = _parse_amount(row.get(amt_col, ""))
                if amt is None:
                    continue
                direction = "CREDIT" if amt >= 0 else "DEBIT"
                amt = abs(amt)
            elif cr_col or dr_col:
                cr = _parse_amount(row.get(cr_col, "")) if cr_col else None
                dr = _parse_amount(row.get(dr_col, "")) if dr_col else None
                if cr and cr != 0:
                    amt, direction = abs(cr), "CREDIT"
                elif dr and dr != 0:
                    amt, direction = abs(dr), "DEBIT"
                else:
                    continue
            else:
                continue

            txns.append(Transaction(
                date=date, description=desc,
                amount=amt, direction=direction,
            ))
        return txns

    # ── PDF ─────────────────────────────────────────────────────

    def _extract_pdf(self, fp: Path) -> List[Transaction]:
        if not PDF_OK:
            raise RuntimeError("pdfplumber not installed")

        txns: List[Transaction] = []
        with pdfplumber.open(fp) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for t in self._parse_table(table):
                            t.source_page = page_num
                            txns.append(t)
                if not txns:
                    text = page.extract_text()
                    if text:
                        for t in self._extract_text(text):
                            t.source_page = page_num
                            txns.append(t)
        return txns

    # ── Plain text ──────────────────────────────────────────────

    def _extract_text(self, text: str) -> List[Transaction]:
        pattern = re.compile(
            r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"
            r"\s+"
            r"(.+?)"
            r"\s+"
            r"([+-]?\$?[\d,]+\.?\d{0,2})\s*$",
            re.MULTILINE,
        )
        txns: List[Transaction] = []
        for m in pattern.finditer(text):
            date = _parse_date(m.group(1))
            desc = m.group(2).strip()
            amt = _parse_amount(m.group(3))
            if amt is None or not desc:
                continue
            direction = "CREDIT" if amt >= 0 else "DEBIT"
            txns.append(Transaction(
                date=date, description=desc,
                amount=abs(amt), direction=direction,
            ))
        return txns

    # ── Table parser ────────────────────────────────────────────

    def _parse_table(self, table: list) -> List[Transaction]:
        if not table or len(table) < 2:
            return []
        headers = [_norm(str(h or "")) for h in table[0]]
        di = self._find_idx(headers, DATE_HEADERS)
        dsi = self._find_idx(headers, DESC_HEADERS)
        ai = self._find_idx(headers, AMOUNT_HEADERS)
        ci = self._find_idx(headers, CREDIT_HEADERS)
        dri = self._find_idx(headers, DEBIT_HEADERS)

        txns: List[Transaction] = []
        for row in table[1:]:
            if not row or all(not c for c in row):
                continue
            date = _parse_date(str(row[di] or "")) if di is not None else ""
            desc = str(row[dsi] or "").strip() if dsi is not None else ""
            if not desc:
                continue

            if ai is not None:
                amt = _parse_amount(str(row[ai] or ""))
                if amt is None:
                    continue
                direction = "CREDIT" if amt >= 0 else "DEBIT"
                amt = abs(amt)
            elif ci is not None or dri is not None:
                cr = _parse_amount(str(row[ci] or "")) if ci is not None else None
                dr = _parse_amount(str(row[dri] or "")) if dri is not None else None
                if cr and cr != 0:
                    amt, direction = abs(cr), "CREDIT"
                elif dr and dr != 0:
                    amt, direction = abs(dr), "DEBIT"
                else:
                    continue
            else:
                continue

            txns.append(Transaction(date=date, description=desc,
                                    amount=amt, direction=direction))
        return txns

    # ── Metadata extraction ─────────────────────────────────────

    def _extract_metadata(self, text: str, batch: TransactionBatch):
        text_l = text.lower()
        # Beginning balance
        m = re.search(r"(?:beginning|opening|previous)\s+balance[\s:$]*(\$?[\d,]+\.\d{2})", text_l)
        if m:
            batch.beginning_balance = _parse_amount(m.group(1))
        # Ending balance
        m = re.search(r"(?:ending|closing|new)\s+balance[\s:$]*(\$?[\d,]+\.\d{2})", text_l)
        if m:
            batch.ending_balance = _parse_amount(m.group(1))
        # Period
        m = re.search(r"(?:period|statement)\s*:?\s*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s*\d{4})", text_l)
        if m:
            batch.period_start = m.group(1).strip()
            batch.period_end = m.group(2).strip()
        # Account last 4
        m = re.search(r"account\s*#?\s*:?\s*\*{0,4}(\d{4})\b", text_l)
        if m:
            batch.account_number_last4 = m.group(1)

    # ── Util ────────────────────────────────────────────────────

    def _find(self, hmap: dict, aliases: set) -> Optional[str]:
        for a in aliases:
            if a in hmap:
                return hmap[a]
        return None

    def _find_idx(self, headers: list, aliases: set) -> Optional[int]:
        for i, h in enumerate(headers):
            if h in aliases:
                return i
        return None
