"""
CFO Macro RD — updater framework.

This first deployable version deliberately separates:
1) publication automation (fully configured in GitHub Actions), and
2) source extraction (integrated source-by-source after validating each official
   download/API contract).

Why: government pages can change HTML/download URLs. A failed extraction must never
silently overwrite the last good CFO snapshot.

Run: python scripts/update_data.py
"""
from pathlib import Path
from datetime import datetime, timezone
import json, requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "current.json"

OFFICIAL_SOURCES = {
    "bcrd": "https://www.bancentral.gov.do/",
    "dgii_itbis": "https://dgii.gov.do/estadisticas/Operaciones-Recaudaciones-ITBIS/Paginas/default.aspx",
    "hacienda": "https://www.hacienda.gob.do/estadisticas-fiscales/",
}

def healthcheck(url):
    r = requests.get(url, timeout=30, headers={"User-Agent":"CFO-Macro-RD/1.0"})
    r.raise_for_status()
    return r.status_code

def main():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    checks = {}
    for name, url in OFFICIAL_SOURCES.items():
        try:
            checks[name] = {"ok": healthcheck(url) == 200}
        except Exception as exc:
            checks[name] = {"ok": False, "error": str(exc)[:160]}
    payload["automation_check_utc"] = datetime.now(timezone.utc).isoformat()
    payload["source_health"] = checks
    # Important: keep last validated values until an extractor passes validation.
    DATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(checks, indent=2))

if __name__ == "__main__":
    main()
