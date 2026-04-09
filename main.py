"""
Financial Document Processing System v3.0
==========================================
Run:  python main.py
F5 in VSCode works too (launch.json pre-configured).

Privacy: zero network calls, zero external APIs, 100% local.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from colorama import init, Fore, Style
from scrubber import DocumentProcessor
from engine import DocumentExtractor
from categorization import CategorizerEngine
from accounting import JournalEntryGenerator, TrialBalanceGenerator, ScheduleCMapper
from flags import FlagEngine
from cpa_output import CPAReportPackage, CPAPDFGenerator

init(autoreset=True)


# ════════════════════════════════════════════════════════════════ #
#  UI helpers                                                      #
# ════════════════════════════════════════════════════════════════ #


def banner():
    print(Fore.CYAN + Style.BRIGHT + """
  ╔═══════════════════════════════════════════════════════╗
  ║   FINANCIAL DOCUMENT PROCESSING SYSTEM  v3.0          ║
  ║   Scrubber + P&L + CPA Workpapers + Flags             ║
  ║   100% Local  •  Zero Network  •  Audit-Ready          ║
  ╚═══════════════════════════════════════════════════════╝""")


def sep(c="-", w=57):
    print(Fore.CYAN + c * w)


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    value = input(Fore.YELLOW + f"  {prompt}{hint}: " + Style.RESET_ALL).strip()
    return value or default


def confirm(prompt: str, default: bool = True) -> bool:
    hint = "(Y/n)" if default else "(y/N)"
    ans = ask(f"{prompt} {hint}", "y" if default else "n").lower()
    return ans in ("y", "yes", "")


def print_result(r: dict):
    if r["success"]:
        print(Fore.GREEN + f"\n  ✔  Scrubbed successfully")
        print(f"     Source  → {r['source_file']}")
        print(f"     TXT     → {r['output_text']}")
        if r.get("output_pdf"):
            print(f"     PDF     → {r['output_pdf']}")
        print(f"     Report  → {r['output_report']}")
        print(f"     Redacted  {r['detections_count']} sensitive item(s)\n")
        for label, count in r.get("detections_summary", {}).items():
            print(f"     • {label:<35} {count:>3}")
    else:
        print(Fore.RED + f"\n  ✘  {r['error']}")


# ════════════════════════════════════════════════════════════════ #
#  Menu actions                                                    #
# ════════════════════════════════════════════════════════════════ #


def single_file(proc: DocumentProcessor):
    sep()
    print(Style.BRIGHT + "  PROCESS SINGLE FILE")
    sep()
    path = ask("Path to statement  (PDF / TXT / CSV)")
    if not path:
        print(Fore.RED + "  No path given.")
        return
    r = proc.process_file(path)
    print_result(r)
    if r.get("success") and confirm("  View full report?"):
        print(Fore.WHITE + "\n" + r["report"])


def batch_folder(proc: DocumentProcessor):
    sep()
    print(Style.BRIGHT + "  BATCH PROCESS FOLDER")
    sep()
    folder = ask("Folder path")
    if not folder or not Path(folder).is_dir():
        print(Fore.RED + "  Invalid folder.")
        return

    results = proc.process_directory(folder)
    ok = [r for r in results if r["success"]]
    fail = [r for r in results if not r["success"]]

    print(Fore.GREEN + f"\n  ✔  {len(ok)} succeeded")
    if fail:
        print(Fore.RED + f"  ✘  {len(fail)} failed")
        for r in fail:
            print(f"      {r.get('source_file', '?')} → {r['error']}")

    total = sum(r.get("detections_count", 0) for r in ok)
    print(f"\n  Total sensitive items redacted: {total}\n")
    for r in ok:
        print_result(r)


def manage_custom(proc: DocumentProcessor):
    sep()
    print(Style.BRIGHT + "  CUSTOM REDACTION TERMS")
    sep()

    terms = proc.detector.custom_terms
    if terms:
        for i, t in enumerate(terms, 1):
            print(f"  {i}. {t}")
    else:
        print(Fore.YELLOW + "  (none defined)")

    print("\n  1  Add term    2  Remove term    3  Back")
    c = ask("Choice", "3")

    if c == "1":
        t = ask("Term to redact (e.g. client full name, company, case ID)")
        if t:
            proc.detector.add_custom_term(t)
            proc.save_config()
            print(Fore.GREEN + f"  ✔  Added '{t}'")

    elif c == "2":
        if not terms:
            print(Fore.YELLOW + "  Nothing to remove.")
            return
        idx = ask("Number to remove")
        try:
            removed = proc.detector.custom_terms.pop(int(idx) - 1)
            proc.save_config()
            print(Fore.GREEN + f"  ✔  Removed '{removed}'")
        except (ValueError, IndexError):
            print(Fore.RED + "  Invalid selection.")


def security_info(_proc):
    sep("=")
    print(Fore.CYAN + Style.BRIGHT + """
  PRIVACY & SECURITY DETAILS
  ═══════════════════════════════════════════════════════

  WHERE YOUR DATA GOES
  ────────────────────
  ✅ Nowhere. Everything runs on this machine only.
  ✅ No internet connection is made at any point.
  ✅ No API keys, no cloud services, no telemetry.
  ✅ No accounts or logins required.
  ✅ Original files are NEVER modified or deleted.
  ✅ Scrubbed output goes to /output only.

  HOW IT WORKS (technical)
  ────────────────────────
  1. Your file is read from disk into RAM as plain text.
  2. Python regex patterns scan the text string in memory.
  3. Matched spans are replaced with ██ REDACTED ██ tokens.
  4. The new string is written to /output as a .txt file.
  5. RAM is freed when the function returns.
  → At no point does any data touch a network socket.

  WHAT IS REDACTED
  ────────────────
  • Account & routing numbers     • SSNs
  • Credit / debit card numbers   • IBANs
  • Phone numbers                 • Email addresses
  • Street addresses              • Dates of birth
  • IP addresses                  • Passport numbers
  • Driver licence numbers        • Your custom terms

  WHAT TO DO WITH OUTPUT FILES
  ────────────────────────────
  ☐ Review the _SCRUBBED.txt before sharing
  ☐ Delete _REPORT.txt after your review
  ☐ Store /output on an encrypted drive
  ☐ Never commit /output to git (enforced by .gitignore)

  AUDIT TRAIL
  ───────────
  Each _REPORT.txt records what was redacted, confidence
  scores, and a checklist — no actual sensitive values
  are stored in the report.
  ═══════════════════════════════════════════════════════
""")
    input(Fore.YELLOW + "  Press Enter to return to menu...")


def run_demo(proc: DocumentProcessor):
    sep()
    print(Style.BRIGHT + "  DEMO — NO REAL FILES NEEDED")
    sep()

    sample = """
FIRST NATIONAL BANK  —  ACCOUNT STATEMENT
Period: January 1 – January 31 2024
══════════════════════════════════════════════════════

Customer      : Jonathan R. Blackwell III
Address       : 7821 Crescent Drive, Austin, TX 78701
Account No    : 000123456789
Routing No    : 021000021
Phone         : (512) 555-9087
Email         : j.blackwell@privateemail.com
SSN on file   : 523-88-4471
Date of Birth : 06/14/1978
IP last login : 192.168.1.104

TRANSACTIONS
──────────────────────────────────────────────────────
01/03  DIRECT DEPOSIT – ACME HOLDINGS LLC   +12,500.00
01/06  WIRE TRANSFER OUT – REF#882211        -5,000.00
01/09  AMAZON PRIME                             -14.99
01/15  ATM WITHDRAWAL                          -400.00
01/22  VENMO – SARAH BLACKWELL                 -250.00
01/31  CLOSING BALANCE                      $41,837.52
══════════════════════════════════════════════════════
Visa ending 4532 • Card number: 4532 0151 1234 5670
IBAN: GB29NWBK60161331926819
"""

    tmp = Path("output/_DEMO_statement.txt")
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(sample, encoding="utf-8")

    r = proc.process_file(tmp)
    print_result(r)

    if r.get("success"):
        print(Fore.WHITE + Style.BRIGHT + "\n  ── SCRUBBED OUTPUT ─────────────────────────────────\n")
        print(Path(r["output_text"]).read_text(encoding="utf-8"))
        print(Fore.WHITE + Style.BRIGHT + "\n  ── REPORT ──────────────────────────────────────────\n")
        print(r["report"])


# ════════════════════════════════════════════════════════════════ #
#  Main loop                                                       #
# ════════════════════════════════════════════════════════════════ #


# ════════════════════════════════════════════════════════════════ #
#  Financial Document Processing actions                            #
# ════════════════════════════════════════════════════════════════ #


def analyze_document(_proc):
    sep()
    print(Style.BRIGHT + "  FINANCIAL DOCUMENT ANALYSIS")
    sep()
    path = ask("Path to bank statement (CSV / TXT / PDF)")
    if not path or not Path(path).exists():
        print(Fore.RED + "  File not found.")
        return

    business = ask("Business name", "Client")
    period = ask("Period label (e.g. January 2024)", "Current Period")

    print(Fore.CYAN + "\n  [1/5] Extracting transactions...")
    extractor = DocumentExtractor()
    try:
        batch = extractor.extract(path)
    except Exception as exc:
        print(Fore.RED + f"  Extraction error: {exc}")
        return

    if not batch.transactions:
        print(Fore.RED + "  No transactions found. Check file format.")
        return
    print(Fore.GREEN + f"  Found {batch.count} transactions")
    print(f"  Document type: {batch.document_type}")

    print(Fore.CYAN + "  [2/5] Categorizing with 3-layer engine...")
    engine = CategorizerEngine()
    cat_result = engine.categorize_batch(batch.transactions)
    print(Fore.GREEN + f"  Exact match: {cat_result['exact_match']}")
    print(f"  Pattern match: {cat_result['pattern_match']}")
    print(f"  Uncategorized: {cat_result['uncategorized']}")
    print(f"  Avg confidence: {cat_result['avg_confidence']:.1%}")

    print(Fore.CYAN + "  [3/5] Generating journal entries...")
    je_gen = JournalEntryGenerator()
    entries = je_gen.generate_batch(batch.transactions)
    balanced = je_gen.validate_all_balanced(entries)
    status = Fore.GREEN + "BALANCED" if balanced else Fore.RED + "OUT OF BALANCE"
    print(f"  {len(entries)} journal entries — {status}")

    print(Fore.CYAN + "  [4/5] Running flag engine...")
    flag_engine = FlagEngine()
    flag_report = flag_engine.flag_batch(batch)
    fc = flag_report['flag_counts']
    if fc:
        print(Fore.YELLOW + f"  {flag_report['flagged_transactions']} flagged transactions:")
        for flag_name, count in fc.items():
            print(f"     {flag_name}: {count}")
    else:
        print(Fore.GREEN + "  No flags raised.")

    print(Fore.CYAN + "  [5/5] Building CPA package...")
    pkg_gen = CPAReportPackage()
    package = pkg_gen.generate(batch, business, period, "output")

    # Generate PDF
    pdf_gen = CPAPDFGenerator()
    pdf_path = pdf_gen.generate(package, "output/cpa_report.pdf", business)

    sep("=")
    print(Fore.GREEN + Style.BRIGHT + "\n  ANALYSIS COMPLETE")
    sep()

    pnl = package.get('profit_and_loss', {})
    print(f"  Revenue:        ${pnl.get('revenue',{}).get('total',0):>12,.2f}")
    print(f"  COGS:           ${pnl.get('cogs',{}).get('total',0):>12,.2f}")
    print(f"  Gross Profit:   ${pnl.get('gross_profit',0):>12,.2f}  ({pnl.get('gross_margin_pct',0)}%)")
    print(f"  OPEX:           ${pnl.get('operating_expenses',{}).get('total',0):>12,.2f}")
    print(f"  Net Income:     ${pnl.get('net_income',0):>12,.2f}")
    sep()
    print(f"  Flagged items:  {flag_report['flagged_transactions']}")
    print(f"  Trial balance:  {'BALANCED' if package.get('trial_balance',{}).get('is_balanced') else 'OUT OF BALANCE'}")
    print(f"  JSON package:   {package.get('_saved_to', '')}")
    print(f"  PDF report:     {pdf_path}")
    sep()

    # Show Schedule C if desired
    if confirm("  View Schedule C mapping?", default=False):
        sc_mapper = ScheduleCMapper()
        sc = package.get('schedule_c_map', {})
        for line in sc_mapper.generate_text(sc):
            print(f"  {line}")

    # Show trial balance if desired
    if confirm("  View Trial Balance?", default=False):
        tb_gen = TrialBalanceGenerator()
        tb = package.get('trial_balance', {})
        for line in tb_gen.generate_summary(tb):
            print(f"  {line}")

    # Show flagged items
    if flag_report['flagged_transactions'] > 0 and confirm("  View flagged items?", default=False):
        for t in flag_report.get('flagged_list', [])[:20]:
            print(f"  {t.date}  {t.description[:40]:<40} ${float(t.amount):>10,.2f}")
            for note in t.flag_notes:
                print(Fore.YELLOW + f"           {note}")


def run_fdp_demo(_proc):
    sep()
    print(Style.BRIGHT + "  FDP DEMO — SAMPLE BUSINESS TRANSACTIONS")
    sep()

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

    tmp = Path("output/_DEMO_transactions.csv")
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(demo_csv, encoding="utf-8")

    print(Fore.CYAN + "  Created demo file with 17 transactions")
    print(Fore.CYAN + "  Running full pipeline...\n")

    # Full pipeline
    extractor = DocumentExtractor()
    batch = extractor.extract(str(tmp))
    print(Fore.GREEN + f"  Extracted {batch.count} transactions")

    engine = CategorizerEngine()
    cat_result = engine.categorize_batch(batch.transactions)
    print(Fore.GREEN + f"  Categorized: {cat_result['auto_categorized']} auto, "
          f"{cat_result['uncategorized']} need review")
    print(f"  Avg confidence: {cat_result['avg_confidence']:.1%}")

    flag_engine = FlagEngine()
    flag_report = flag_engine.flag_batch(batch)
    print(Fore.YELLOW + f"  Flags raised: {flag_report['total_flags']}")

    pkg_gen = CPAReportPackage()
    package = pkg_gen.generate(batch, "Demo Auto Shop", "January 2024", "output")

    pdf_gen = CPAPDFGenerator()
    pdf_path = pdf_gen.generate(package, "output/demo_cpa_report.pdf", "Demo Auto Shop")

    sep("=")
    print(Fore.GREEN + Style.BRIGHT + "\n  DEMO RESULTS")
    sep()
    pnl = package.get('profit_and_loss', {})
    print(f"  Revenue:        ${pnl.get('revenue',{}).get('total',0):>12,.2f}")
    print(f"  COGS:           ${pnl.get('cogs',{}).get('total',0):>12,.2f}")
    print(f"  Gross Profit:   ${pnl.get('gross_profit',0):>12,.2f}")
    print(f"  OPEX:           ${pnl.get('operating_expenses',{}).get('total',0):>12,.2f}")
    print(f"  Net Income:     ${pnl.get('net_income',0):>12,.2f}")
    sep()
    fc = flag_report['flag_counts']
    for flag_name, count in fc.items():
        print(Fore.YELLOW + f"  {flag_name}: {count}")
    sep()
    print(f"  JSON:  {package.get('_saved_to', '')}")
    print(f"  PDF:   {pdf_path}")
    print(Fore.GREEN + "\n  Demo complete!\n")


MENU = {
    "1": ("Scrub a single file",              single_file),
    "2": ("Batch scrub a folder",             batch_folder),
    "3": ("Analyze document (Full FDP)",      analyze_document),
    "4": ("Run FDP demo (sample data)",       run_fdp_demo),
    "5": ("Manage custom redaction terms",    manage_custom),
    "6": ("Privacy & security information",   security_info),
    "7": ("Run scrubber demo",                run_demo),
    "8": ("Quit",                             None),
}


def main():
    banner()

    # Ensure config directory and default config exist
    Path("config").mkdir(exist_ok=True)
    cfg = Path("config/settings.json")
    if not cfg.exists():
        cfg.write_text(
            json.dumps({"custom_terms": [], "keep_last_four": True}, indent=2)
        )

    # Ensure output + input directories exist
    Path("output").mkdir(exist_ok=True)
    Path("input").mkdir(exist_ok=True)

    proc = DocumentProcessor(
        config_path="config/settings.json",
        output_dir="output",
        keep_last_four=True,
    )

    print(f"  Output folder : {Path('output').absolute()}")
    print(f"  Config file   : {cfg.absolute()}\n")

    while True:
        sep("=")
        print(Style.BRIGHT + "  MAIN MENU")
        sep()
        for k, (label, _) in MENU.items():
            print(f"  {Fore.CYAN}{k}{Style.RESET_ALL}  {label}")
        sep()

        choice = ask("Select", "1")

        if choice not in MENU:
            print(Fore.RED + "  Invalid — try again.")
            continue

        label, action = MENU[choice]

        if action is None:
            print(Fore.CYAN + "\n  Session closed. Stay secure. 🔒\n")
            break

        try:
            action(proc)
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\n  (cancelled — back to menu)")
        except Exception as exc:
            print(Fore.RED + f"\n  Error: {exc}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
