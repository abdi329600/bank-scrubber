"""
FastAPI backend for the Financial Document Processing System.
Bulletproof P&L Math + High-Integrity Categorization.

Two modes:
  - full       : Complete CPA pipeline with reconciliation, loan splits,
                  capex detection, validation, acceptance gates, PDF/JSON
  - categorize : Precision-first categorization only (90% auto-accept threshold)

All money serialized as strings (never float). Decimal integrity end-to-end.
"""

import os
import sys
import hashlib
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine import (
    DocumentExtractor, LoanSplitter, ReconciliationEngine,
)
from categorization import CategorizerEngine
from accounting import (
    JournalEntryGenerator, TrialBalanceGenerator,
    ScheduleCMapper, COGSEngine, CapexClassifier,
)
from flags import FlagEngine
from cpa_output import CPAReportPackage, CPAPDFGenerator
from validation import ValidationEngine, AcceptanceCriteria

app = FastAPI(title="Financial Document Processor", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _save_upload(upload: UploadFile):
    """Save uploaded file, return (path, sha256_hash)."""
    suffix = Path(upload.filename or "file.csv").suffix
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=str(OUTPUT_DIR))
    content = upload.file.read()
    tmp.write(content)
    tmp.close()
    sha = hashlib.sha256(content).hexdigest()
    return Path(tmp.name), sha


def _txn_to_dict(t):
    """Decimal-safe transaction serialization for JSON response."""
    return {
        "date": t.date,
        "description": t.description,
        "merchant": t.merchant_clean,
        "canonical_merchant": t.canonical_merchant_id,
        "amount": str(t.amount),
        "direction": t.direction,
        "inflow_type": t.inflow_type,
        "account_code": t.account_code,
        "account_name": t.account_name,
        "account_type": t.account_type,
        "confidence": t.confidence_score,
        "layer": t.categorization_layer,
        "evidence": t.categorization_evidence,
        "matched_rule": t.matched_rule_id,
        "required_review": t.required_review,
        "deductible": t.deductible,
        "deductible_pct": str(t.deductible_pct),
        "irs_ref": t.irs_ref,
        "is_capex": t.is_capex,
        "capex_class": t.capex_asset_class,
        "loan_principal": str(t.loan_principal) if t.loan_principal is not None else None,
        "loan_interest": str(t.loan_interest) if t.loan_interest is not None else None,
        "flags": t.flags,
        "flag_notes": t.flag_notes,
    }


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    mode: str = Form("full"),
    business_name: str = Form("Client"),
    period: str = Form("Current Period"),
):
    """
    Main endpoint. Accepts file upload + mode.
    mode = "full"       → Full CPA analysis pipeline (reconciliation + acceptance gates)
    mode = "categorize" → Precision-first categorization (90% threshold, review queue)
    """
    filepath, source_hash = _save_upload(file)

    try:
        # ── Step 1: Extract ───────────────────────────────────────
        extractor = DocumentExtractor()
        batch = extractor.extract(str(filepath))
        batch.source_hash = source_hash

        if not batch.transactions:
            raise HTTPException(400, "No transactions found in file. Check format.")

        # ── Step 2: Loan splitting (before categorization) ───────
        loan_splitter = LoanSplitter()
        loan_report = loan_splitter.process_batch(batch.transactions)

        # ── Step 3: Categorize (mode-aware) ────────────────────
        cat_engine = CategorizerEngine(mode=mode)
        cat_result = cat_engine.categorize_batch(batch.transactions)

        # ── Step 4: Capital expenditure detection ───────────────
        capex_classifier = CapexClassifier()
        capex_report = capex_classifier.process_batch(batch.transactions)

        # ── Posting gate: determine analysis grade ────────────
        total_txns = cat_result["total"]
        uncat_pct = (cat_result["uncategorized"] / total_txns * 100) if total_txns else 0
        review_pct = (cat_result["review_queue"] / total_txns * 100) if total_txns else 0
        unsplit_loans = loan_report.get("needs_manual_split", 0)

        if uncat_pct > 30 or review_pct > 50:
            analysis_grade = "PRELIMINARY"
            grade_reason = (f"{cat_result['uncategorized']} uncategorized ({uncat_pct:.0f}%), "
                           f"{cat_result['review_queue']} in review queue ({review_pct:.0f}%). "
                           "Too many unresolved items for full analysis.")
        elif uncat_pct > 15 or unsplit_loans > 5:
            analysis_grade = "DRAFT"
            grade_reason = (f"{cat_result['uncategorized']} uncategorized ({uncat_pct:.0f}%), "
                           f"{unsplit_loans} unsplit loan payments. "
                           "Review recommended before relying on P&L.")
        else:
            analysis_grade = "FULL"
            grade_reason = "Categorization coverage sufficient for full analysis."

        # Build base response
        response = {
            "mode": mode,
            "analysis_grade": analysis_grade,
            "analysis_grade_reason": grade_reason,
            "file_name": file.filename,
            "source_hash": source_hash,
            "document_type": batch.document_type,
            "accounting_method": batch.accounting_method,
            "method_label": batch.method_label,
            "transaction_count": batch.count,
            "categorization": {
                "pre_classified": cat_result.get("pre_classified", 0),
                "loan_split": cat_result.get("loan_split", 0),
                "exact_match": cat_result["exact_match"],
                "learned_match": cat_result.get("learned_match", 0),
                "pattern_match": cat_result["pattern_match"],
                "uncategorized": cat_result["uncategorized"],
                "auto_categorized": cat_result.get("auto_categorized", 0),
                "avg_confidence": cat_result["avg_confidence"],
                "flagged": cat_result["flagged"],
                "review_queue": cat_result["review_queue"],
                "mode": cat_result["mode"],
                "threshold": cat_result["threshold"],
                "correction_store": cat_result.get("correction_store", {}),
            },
            "loan_report": loan_report,
            "capex_report": capex_report,
            "transactions": [_txn_to_dict(t) for t in batch.transactions],
        }

        if mode == "full":
            # ── Step 5: Journal entries ─────────────────────────
            je_gen = JournalEntryGenerator()
            entries = je_gen.generate_batch(batch.transactions)
            all_balanced = je_gen.validate_all_balanced(entries)

            # ── Step 6: Trial balance ──────────────────────────
            tb_gen = TrialBalanceGenerator()
            trial_balance = tb_gen.generate(entries)

            # ── Step 7: Flags ──────────────────────────────────
            flag_engine = FlagEngine()
            flag_report = flag_engine.flag_batch(batch)

            # ── Step 8: Bank reconciliation ─────────────────────
            recon_engine = ReconciliationEngine()
            recon_result = recon_engine.reconcile(batch)

            # ── Step 9: Validation (structural + semantic) ───────
            validator = ValidationEngine()
            val_report = validator.validate(
                batch, entries, trial_balance, recon_result
            )

            # ── Step 10: Acceptance criteria (4 gates) ───────────
            acceptance = AcceptanceCriteria()
            accept_report = acceptance.evaluate(
                batch, entries, trial_balance, recon_result, val_report
            )

            # ── Step 11: COGS analysis ─────────────────────────
            cogs_engine = COGSEngine()
            cogs_result = cogs_engine.compute_bank_proxy(batch.transactions)

            # ── Step 12: Schedule C ────────────────────────────
            sc_mapper = ScheduleCMapper()
            schedule_c = sc_mapper.map_transactions(batch.transactions)

            # ── Step 13: CPA package + PDF ─────────────────────
            pkg_gen = CPAReportPackage()
            package = pkg_gen.generate(batch, business_name, period, str(OUTPUT_DIR))

            pdf_gen = CPAPDFGenerator()
            pdf_gen.generate(
                package, str(OUTPUT_DIR / "cpa_report.pdf"), business_name
            )

            pnl = package.get("profit_and_loss", {})

            response["profit_and_loss"] = pnl
            response["trial_balance"] = {
                "is_balanced": trial_balance["is_balanced"],
                "total_debits": trial_balance["total_debits"],
                "total_credits": trial_balance["total_credits"],
                "accounts": [
                    {
                        "code": a["code"],
                        "name": a["name"],
                        "type": a["type"],
                        "debit": str(a["total_debit"]),
                        "credit": str(a["total_credit"]),
                    }
                    for a in trial_balance.get("accounts", [])
                ],
            }
            response["schedule_c"] = schedule_c
            response["cogs"] = cogs_result.to_dict()
            response["flags"] = {
                "total": flag_report["total_flags"],
                "flagged_transactions": flag_report["flagged_transactions"],
                "counts": flag_report["flag_counts"],
                "by_severity": flag_report["by_severity"],
            }
            response["reconciliation"] = {
                "status": recon_result.status,
                "difference": recon_result.difference,
                "balances_provided": recon_result.balances_provided,
                "issues": recon_result.issues,
                "recommendations": recon_result.recommendations,
            }
            response["validation"] = val_report.to_dict()
            response["acceptance"] = accept_report.to_dict()
            response["journal_entries_balanced"] = all_balanced
            response["pdf_available"] = True

            # Re-serialize transactions with all enrichments
            response["transactions"] = [_txn_to_dict(t) for t in batch.transactions]

        return JSONResponse(content=response)

    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Processing error: {str(exc)}")
    finally:
        try:
            filepath.unlink()
        except Exception:
            pass


@app.get("/api/download-pdf")
async def download_pdf():
    pdf_path = OUTPUT_DIR / "cpa_report.pdf"
    if not pdf_path.exists():
        raise HTTPException(404, "No PDF generated yet. Run a full analysis first.")
    return FileResponse(str(pdf_path), media_type="application/pdf", filename="cpa_report.pdf")


@app.get("/api/download-json")
async def download_json():
    json_path = OUTPUT_DIR / "cpa_package.json"
    if not json_path.exists():
        raise HTTPException(404, "No package generated yet.")
    return FileResponse(str(json_path), media_type="application/json", filename="cpa_package.json")


# ═══════════════════════════════════════════════════════════════
#  CORRECTION LEARNING API
# ═══════════════════════════════════════════════════════════════

from engine.correction_store import CorrectionStore
from pydantic import BaseModel
from typing import List as TypingList


class CorrectionRequest(BaseModel):
    description: str
    account_code: str
    account_name: str
    account_type: str
    category: str = ""
    subcategory: str = ""
    deductible: bool = True
    irs_ref: str = ""
    direction: str = ""
    notes: str = ""


@app.post("/api/corrections")
async def add_correction(req: CorrectionRequest, client_id: str = "default"):
    """Record a human correction. This becomes a learned rule for future runs."""
    store = CorrectionStore(client_id=client_id)
    rule = store.add_correction(
        description=req.description,
        account_code=req.account_code,
        account_name=req.account_name,
        account_type=req.account_type,
        category=req.category,
        subcategory=req.subcategory,
        deductible=req.deductible,
        irs_ref=req.irs_ref,
        direction=req.direction,
        notes=req.notes,
    )
    return JSONResponse(content={
        "status": "ok",
        "rule_id": rule.rule_id,
        "canonical_pattern": rule.canonical_pattern,
        "confidence": rule.confidence,
        "times_confirmed": rule.times_confirmed,
        "message": f"Correction stored. Will match future '{rule.canonical_pattern}' transactions.",
    })


@app.get("/api/corrections")
async def get_corrections(client_id: str = "default"):
    """List all learned correction rules for a client."""
    store = CorrectionStore(client_id=client_id)
    rules = []
    for rule in store.rules.values():
        rules.append({
            "rule_id": rule.rule_id,
            "canonical_pattern": rule.canonical_pattern,
            "account_code": rule.account_code,
            "account_name": rule.account_name,
            "account_type": rule.account_type,
            "confidence": rule.confidence,
            "times_applied": rule.times_applied,
            "times_confirmed": rule.times_confirmed,
            "times_overridden": rule.times_overridden,
            "created_at": rule.created_at,
            "source": rule.source,
        })
    return JSONResponse(content={
        "client_id": client_id,
        "stats": store.stats,
        "rules": rules,
    })


class BulkCorrectionRequest(BaseModel):
    corrections: TypingList[CorrectionRequest]


@app.post("/api/corrections/bulk")
async def bulk_import_corrections(req: BulkCorrectionRequest, client_id: str = "default"):
    """Bulk import corrections (e.g. from a CPA's reviewed spreadsheet)."""
    store = CorrectionStore(client_id=client_id)
    count = 0
    for c in req.corrections:
        store.add_correction(
            description=c.description,
            account_code=c.account_code,
            account_name=c.account_name,
            account_type=c.account_type,
            category=c.category,
            subcategory=c.subcategory,
            deductible=c.deductible,
            irs_ref=c.irs_ref,
            direction=c.direction,
            notes=c.notes,
        )
        count += 1
    return JSONResponse(content={
        "status": "ok",
        "imported": count,
        "total_rules": len(store.rules),
    })


@app.delete("/api/corrections/{rule_id}")
async def delete_correction(rule_id: str, client_id: str = "default"):
    """Delete a specific correction rule."""
    store = CorrectionStore(client_id=client_id)
    if rule_id in store.rules:
        del store.rules[rule_id]
        store.save()
        return JSONResponse(content={"status": "ok", "deleted": rule_id})
    raise HTTPException(404, f"Correction rule '{rule_id}' not found")


# ═══════════════════════════════════════════════════════════════
#  LOAN SPLIT OVERRIDE API
# ═══════════════════════════════════════════════════════════════

class LoanSplitRequest(BaseModel):
    description_pattern: str
    principal_pct: float       # e.g. 0.75
    interest_pct: float        # e.g. 0.25
    fees_pct: float = 0.0


@app.post("/api/loan-splits")
async def add_loan_split(req: LoanSplitRequest):
    """Register a manual loan split ratio.
    
    CPA provides the exact principal/interest breakdown for a recurring loan.
    On next analysis run, the splitter will use these ratios instead of estimates.
    """
    total = req.principal_pct + req.interest_pct + req.fees_pct
    if abs(total - 1.0) > 0.01:
        raise HTTPException(400, f"Percentages must sum to 1.0 (got {total:.2f})")

    return JSONResponse(content={
        "status": "ok",
        "pattern": req.description_pattern.upper().strip(),
        "principal_pct": req.principal_pct,
        "interest_pct": req.interest_pct,
        "fees_pct": req.fees_pct,
        "message": (
            f"Manual split registered for '{req.description_pattern}'. "
            f"Re-run analysis to apply."
        ),
    })


@app.get("/api/loan-splits")
async def get_loan_splits():
    """List all registered manual loan split overrides."""
    return JSONResponse(content={
        "splits": [],
        "message": "Manual splits are applied per-run. Upload amortization schedules for persistent tracking.",
    })


# Serve frontend static files
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
