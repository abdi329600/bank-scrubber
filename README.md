# Bank Statement Scrubber v2.0

**100% local. Zero network. Audit-ready.**

## Privacy

- All processing happens on YOUR machine only
- Zero internet connections made at any point
- No API keys, no cloud, no telemetry
- Original files are never modified or deleted
- Output goes to `/output` only (gitignored)

## Quick Start

```bash
cd bank_scrubber
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

## VSCode

Press **F5** — `launch.json` is pre-configured.

## What Gets Redacted

| Type | Example output |
|---|---|
| Account number | `██ ACCOUNT-XXXX6789 ██` |
| SSN | `██ SSN-REDACTED ██` |
| Credit card | `██ CARD-XXXX5670 ██` |
| Email | `██ EMAIL-REDACTED ██` |
| Phone | `██ PHONE-REDACTED ██` |
| Address | `██ ADDRESS-REDACTED ██` |
| IBAN | `██ IBAN-REDACTED ██` |
| Custom term | `██ REDACTED ██` |

## Output Files

| File | Purpose |
|---|---|
| `output/NAME_SCRUBBED.txt` | Safe to share |
| `output/NAME_REPORT.txt` | Audit log — delete after review |

## Security Checklist

- [ ] Review scrubbed output before sending
- [ ] Delete report files after review
- [ ] Store output on encrypted drive
- [ ] Never commit `/output` or `/input` to git
