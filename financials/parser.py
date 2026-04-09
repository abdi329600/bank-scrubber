"""
parser.py
=========
Reads raw bank statement files (CSV, TXT, PDF) and extracts
a list of Transaction objects.

100% local — no network calls.
"""

import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional
from datetime import datetime

try:
    from dateutil import parser as dateutil_parser
    DATEUTIL = True
except ImportError:
    DATEUTIL = False

try:
    import pdfplumber
    PDF_OK = True
except ImportError:
    PDF_OK = False

from .categorizer import Transaction


# ── Helpers ─────────────────────────────────────────────────────

def _parse_amount(raw: str) -> Optional[Decimal]:
    """Parse a dollar amount string into a Decimal."""
    if not raw:
        return None
    cleaned = raw.strip().replace("$", "").replace(",", "").replace(" ", "")
    # Handle parenthesized negatives: (500.00) → -500.00
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_date(raw: str) -> str:
    """Normalize a date string to YYYY-MM-DD."""
    if not raw:
        return ""
    if DATEUTIL:
        try:
            return dateutil_parser.parse(raw, dayfirst=False).strftime("%Y-%m-%d")
        except (ValueError, OverflowError):
            pass
    # Fallback: return as-is
    return raw.strip()


def _infer_type(amount: Decimal) -> str:
    """Positive = credit (income), negative = debit (expense)."""
    return "credit" if amount >= 0 else "debit"


# ── CSV Parser ──────────────────────────────────────────────────

# Common column header aliases banks use
DATE_HEADERS = {"date", "posted date", "posting date", "trans date",
                "transaction date", "effective date", "post date"}
DESC_HEADERS = {"description", "memo", "details", "transaction",
                "narrative", "payee", "merchant", "name"}
AMOUNT_HEADERS = {"amount", "total", "sum"}
CREDIT_HEADERS = {"credit", "credits", "deposit", "deposits"}
DEBIT_HEADERS = {"debit", "debits", "withdrawal", "withdrawals", "charge"}


def _normalize_header(h: str) -> str:
    return h.strip().lower().replace("_", " ")


class StatementParser:
    """
    Auto-detects format and returns Transaction objects.
    Supports: CSV, TXT (tabular), PDF (table extraction).
    """

    def parse_file(self, filepath) -> List[Transaction]:
        fp = Path(filepath)
        ext = fp.suffix.lower()

        if ext == ".csv":
            return self.parse_csv(fp)
        elif ext == ".pdf":
            return self.parse_pdf(fp)
        elif ext in (".txt", ".text"):
            return self.parse_text(fp)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    # ── CSV ─────────────────────────────────────────────────────

    def parse_csv(self, filepath: Path) -> List[Transaction]:
        """Parse a bank-exported CSV into Transaction objects."""
        rows = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
        if not rows:
            return []

        # Detect delimiter
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(rows[0], delimiters=",\t|;")
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(rows, dialect=dialect)
        if reader.fieldnames is None:
            return []

        # Map headers
        header_map = {_normalize_header(h): h for h in reader.fieldnames}
        date_col = self._find_col(header_map, DATE_HEADERS)
        desc_col = self._find_col(header_map, DESC_HEADERS)
        amount_col = self._find_col(header_map, AMOUNT_HEADERS)
        credit_col = self._find_col(header_map, CREDIT_HEADERS)
        debit_col = self._find_col(header_map, DEBIT_HEADERS)

        transactions: List[Transaction] = []

        for row in reader:
            date = _parse_date(row.get(date_col, "")) if date_col else ""
            desc = row.get(desc_col, "").strip() if desc_col else ""

            # Single amount column
            if amount_col:
                amt = _parse_amount(row.get(amount_col, ""))
                if amt is None:
                    continue
                t_type = _infer_type(amt)
            # Separate credit/debit columns
            elif credit_col or debit_col:
                credit_val = _parse_amount(row.get(credit_col, "")) if credit_col else None
                debit_val = _parse_amount(row.get(debit_col, "")) if debit_col else None

                if credit_val and credit_val != 0:
                    amt = abs(credit_val)
                    t_type = "credit"
                elif debit_val and debit_val != 0:
                    amt = -abs(debit_val)
                    t_type = "debit"
                else:
                    continue
            else:
                continue

            if not desc:
                continue

            transactions.append(Transaction(
                date=date,
                description=desc,
                amount=amt,
                transaction_type=t_type,
            ))

        return transactions

    # ── Text ────────────────────────────────────────────────────

    def parse_text(self, filepath: Path) -> List[Transaction]:
        """
        Best-effort parse of plain text bank statements.
        Looks for lines with date + description + amount pattern.
        """
        text = filepath.read_text(encoding="utf-8", errors="replace")
        return self._extract_from_text(text)

    # ── PDF ─────────────────────────────────────────────────────

    def parse_pdf(self, filepath: Path) -> List[Transaction]:
        """Extract transactions from PDF tables, fall back to text."""
        if not PDF_OK:
            raise RuntimeError("pdfplumber not installed — run: pip install pdfplumber")

        transactions: List[Transaction] = []

        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                # Try table extraction first
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        transactions.extend(self._parse_table_rows(table))

                # Fall back to text if no tables found
                if not transactions:
                    page_text = page.extract_text()
                    if page_text:
                        transactions.extend(self._extract_from_text(page_text))

        return transactions

    # ── Shared helpers ──────────────────────────────────────────

    def _find_col(self, header_map: dict, aliases: set) -> Optional[str]:
        for alias in aliases:
            if alias in header_map:
                return header_map[alias]
        return None

    def _parse_table_rows(self, table: list) -> List[Transaction]:
        """Parse a pdfplumber table (list of lists) into Transactions."""
        if not table or len(table) < 2:
            return []

        # First row = headers
        headers = [_normalize_header(str(h or "")) for h in table[0]]
        date_idx = self._find_idx(headers, DATE_HEADERS)
        desc_idx = self._find_idx(headers, DESC_HEADERS)
        amt_idx = self._find_idx(headers, AMOUNT_HEADERS)
        credit_idx = self._find_idx(headers, CREDIT_HEADERS)
        debit_idx = self._find_idx(headers, DEBIT_HEADERS)

        transactions: List[Transaction] = []

        for row in table[1:]:
            if not row or all(not cell for cell in row):
                continue

            date = _parse_date(str(row[date_idx] or "")) if date_idx is not None else ""
            desc = str(row[desc_idx] or "").strip() if desc_idx is not None else ""

            if amt_idx is not None:
                amt = _parse_amount(str(row[amt_idx] or ""))
                if amt is None:
                    continue
                t_type = _infer_type(amt)
            elif credit_idx is not None or debit_idx is not None:
                cr = _parse_amount(str(row[credit_idx] or "")) if credit_idx is not None else None
                dr = _parse_amount(str(row[debit_idx] or "")) if debit_idx is not None else None
                if cr and cr != 0:
                    amt = abs(cr)
                    t_type = "credit"
                elif dr and dr != 0:
                    amt = -abs(dr)
                    t_type = "debit"
                else:
                    continue
            else:
                continue

            if desc:
                transactions.append(Transaction(
                    date=date,
                    description=desc,
                    amount=amt,
                    transaction_type=t_type,
                ))

        return transactions

    def _find_idx(self, headers: list, aliases: set) -> Optional[int]:
        for i, h in enumerate(headers):
            if h in aliases:
                return i
        return None

    def _extract_from_text(self, text: str) -> List[Transaction]:
        """
        Regex-based extraction from plain text.
        Pattern: date  description  +/-amount
        """
        # Match: MM/DD or MM/DD/YYYY  description  $amount or plain number
        pattern = re.compile(
            r"(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)"  # date
            r"\s+"
            r"(.+?)"                                     # description
            r"\s+"
            r"([+-]?\$?[\d,]+\.?\d{0,2})\s*$",           # amount
            re.MULTILINE,
        )

        transactions: List[Transaction] = []
        for m in pattern.finditer(text):
            date = _parse_date(m.group(1))
            desc = m.group(2).strip()
            amt = _parse_amount(m.group(3))

            if amt is None or not desc:
                continue

            transactions.append(Transaction(
                date=date,
                description=desc,
                amount=amt,
                transaction_type=_infer_type(amt),
            ))

        return transactions
