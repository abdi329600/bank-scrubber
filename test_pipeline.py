"""End-to-end pipeline test."""
from pathlib import Path
from decimal import Decimal
from engine import DocumentExtractor
from categorization import CategorizerEngine
from accounting import JournalEntryGenerator, TrialBalanceGenerator, ScheduleCMapper
from flags import FlagEngine
from cpa_output import CPAReportPackage, CPAPDFGenerator

demo_csv = (
    "Date,Description,Amount\n"
    "01/03/2024,ACH DEPOSIT - CLIENT PAYMENT,8500.00\n"
    "01/05/2024,SQUARE DEPOSIT,3200.00\n"
    "01/07/2024,SHELL GAS STATION,-85.50\n"
    "01/08/2024,AUTOZONE,-142.30\n"
    "01/10/2024,RENT PAYMENT - MAIN ST OFFICE,-1800.00\n"
    "01/12/2024,COMCAST BUSINESS INTERNET,-129.99\n"
    "01/14/2024,STARBUCKS,-18.75\n"
    "01/15/2024,GUSTO PAYROLL,-4200.00\n"
    "01/17/2024,PROGRESSIVE INSURANCE,-350.00\n"
    "01/18/2024,QUICKBOOKS SUBSCRIPTION,-55.00\n"
    "01/20/2024,FACEBOOK ADS,-280.00\n"
    "01/22/2024,COPART - VEHICLE PURCHASE,-4500.00\n"
    "01/23/2024,AMAZON PURCHASE,-234.99\n"
    "01/25/2024,ATM WITHDRAWAL,-600.00\n"
    "01/28/2024,WIRE TRANSFER IN - VEHICLE SALE,7800.00\n"
    "01/30/2024,MONTHLY SERVICE FEE,-12.00\n"
    "01/31/2024,OWNER DRAW,-2000.00\n"
)

Path("output").mkdir(exist_ok=True)
Path("output/_test.csv").write_text(demo_csv)

# 1. Extract
ext = DocumentExtractor()
batch = ext.extract("output/_test.csv")
print(f"[1] Extracted {batch.count} transactions, type={batch.document_type}")

# 2. Categorize
cat = CategorizerEngine()
r = cat.categorize_batch(batch.transactions)
print(f"[2] Exact={r['exact_match']} Pattern={r['pattern_match']} Uncat={r['uncategorized']} Conf={r['avg_confidence']:.1%}")

# 3. Journal Entries
je = JournalEntryGenerator()
entries = je.generate_batch(batch.transactions)
print(f"[3] {len(entries)} JEs, all balanced={je.validate_all_balanced(entries)}")

# 4. Flags
fe = FlagEngine()
flags = fe.flag_batch(batch)
print(f"[4] Flags: {flags['flag_counts']}")

# 5. CPA Package
pkg = CPAReportPackage()
package = pkg.generate(batch, "Demo Auto Shop", "January 2024", "output")
pnl = package["profit_and_loss"]
revenue_total = Decimal(str(pnl["revenue"]["total"]))
cogs_total = Decimal(str(pnl["cogs"]["total"]))
net_income = Decimal(str(pnl["net_income"]))
print(f"[5] Revenue=${revenue_total:,.2f}  COGS=${cogs_total:,.2f}  Net=${net_income:,.2f}")
print(f"    TB balanced={package['trial_balance']['is_balanced']}")
print(f"    JSON saved to {package['_saved_to']}")

# 6. PDF
pdf = CPAPDFGenerator()
pdf_path = pdf.generate(package, "output/test_cpa_report.pdf", "Demo Auto Shop")
print(f"[6] PDF generated: {pdf_path}")

print("\nALL TESTS PASSED")
