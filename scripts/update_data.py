"""CFO Macro RD — BCRD updater v2.1

Reads the public BCRD homepage and updates only values that pass
label-based validation. If a field cannot be parsed, the last validated
value is kept. FX parsing is anchored to the "Tipo de cambio" block.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, re, requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "current.json"
BCRD = "https://www.bancentral.gov.do/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; CFOMacro-RD/2.1; +GitHub-Pages)"}

MONTHS = {
    "enero":"01","febrero":"02","marzo":"03","abril":"04","mayo":"05","junio":"06",
    "julio":"07","agosto":"08","septiembre":"09","octubre":"10","noviembre":"11","diciembre":"12"
}

def norm(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()

def period(month, year):
    return f"{year}-{MONTHS[month.lower()]}"

def set_series(payload, key, value, per, source="BCRD"):
    if value is None or per is None:
        return False
    payload["series"][key] = {"value": value, "period": per, "source": source}
    return True

def parse_fx(text):
    # Anchor tightly to BCRD's macro block:
    # "Tipo de cambio 8 de Septiembre 2026 Compra 58.6307 | Venta 58.8666"
    pat = (
        r"Tipo de cambio\s+(\d{1,2})\s+de\s+"
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
        r"\s+(\d{4}).{0,120}?Compra\s+(\d{1,3}\.\d{4}).{0,80}?Venta\s+(\d{1,3}\.\d{4})"
    )
    m = re.search(pat, text, re.I | re.S)
    if not m:
        return None
    day, month, year, buy, sell = m.groups()
    per = f"{year}-{MONTHS[month.lower()]}-{int(day):02d}"
    buy, sell = float(buy), float(sell)
    # Sanity checks for DOP/USD and spread direction.
    if not (30 < buy < 100 and 30 < sell < 100 and sell >= buy):
        return None
    return buy, sell, per

def find_pct(text, pattern):
    m = re.search(pattern, text, re.I | re.S)
    return float(m.group(1)) if m else None

def main():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    r = requests.get(BCRD, headers=UA, timeout=30)
    r.raise_for_status()
    text = norm(BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True))

    updated = []

    fx = parse_fx(text)
    if fx:
        buy, sell, per = fx
        if set_series(payload, "usd_dop_buy", buy, per): updated.append("usd_dop_buy")
        if set_series(payload, "usd_dop_sell", sell, per): updated.append("usd_dop_sell")

    # Monthly/other macro indicators, anchored to labels on the BCRD homepage.
    m = re.search(r"Inflación\s*\(variación %\)\s*(\w+)\s+(\d{4}).{0,160}?Interanual\s+(\d+(?:\.\d+)?)%", text, re.I|re.S)
    if m and m.group(1).lower() in MONTHS:
        if set_series(payload, "inflation_yoy", float(m.group(3)), period(m.group(1), m.group(2))):
            updated.append("inflation_yoy")

    m = re.search(r"Inflación subyacente\s*(\w+)\s+(\d{4}).{0,160}?Interanual\s+(\d+(?:\.\d+)?)%", text, re.I|re.S)
    if m and m.group(1).lower() in MONTHS:
        if set_series(payload, "core_inflation_yoy", float(m.group(3)), period(m.group(1), m.group(2))):
            updated.append("core_inflation_yoy")

    m = re.search(r"Tasa de política monetaria\s*(\w+)\s+(\d{4})\s+(\d+(?:\.\d+)?)%", text, re.I|re.S)
    if m and m.group(1).lower() in MONTHS:
        if set_series(payload, "policy_rate", float(m.group(3)), period(m.group(1), m.group(2))):
            updated.append("policy_rate")

    m = re.search(r"Tasas de interés\s*\(promedio ponderado\)\s*(\w+)\s+(\d{4}).{0,250}?Interbancaria\s+(\d+(?:\.\d+)?)%.{0,120}?Activa\s*B\.?M\.?\s+(\d+(?:\.\d+)?)%.{0,120}?Pasiva\s*B\.?M\.?\s+(\d+(?:\.\d+)?)%", text, re.I|re.S)
    if m and m.group(1).lower() in MONTHS:
        per = period(m.group(1), m.group(2))
        for key, val in [("interbank_rate", m.group(3)), ("active_rate", m.group(4)), ("passive_rate", m.group(5))]:
            if set_series(payload, key, float(val), per): updated.append(key)

    m = re.search(r"Préstamos privados.*?(\w+)\s+(\d{4}).{0,180}?Mon\.?\s*nacional\s+(\d+(?:\.\d+)?)%.{0,100}?Total\s+(\d+(?:\.\d+)?)%", text, re.I|re.S)
    if m and m.group(1).lower() in MONTHS:
        if set_series(payload, "private_credit_yoy", float(m.group(4)), period(m.group(1), m.group(2))):
            updated.append("private_credit_yoy")

    m = re.search(r"IMAE original.*?(\w+)\s+(\d{4})\s+(\d+(?:\.\d+)?)%", text, re.I|re.S)
    if m and m.group(1).lower() in MONTHS:
        if set_series(payload, "imae_yoy", float(m.group(3)), period(m.group(1), m.group(2))):
            updated.append("imae_yoy")

    # Audit metadata: distinguish a successful run from actual refreshed fields.
    payload["as_of"] = datetime.now(timezone.utc).date().isoformat()
    payload["status"] = "live-bcrd"
    payload["automation_check_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["updated_fields"] = updated
    payload["source_health"] = payload.get("source_health", {})
    payload["source_health"]["bcrd"] = {
        "ok": True,
        "url": BCRD,
        "http_status": r.status_code,
        "updated_fields": updated
    }

    DATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("BCRD update complete.")
    print("Updated fields:", ", ".join(updated) if updated else "none")
    if fx:
        print(f"FX validated: buy={fx[0]:.4f}, sell={fx[1]:.4f}, period={fx[2]}")
    else:
        print("FX not parsed; previous validated FX retained.")

if __name__ == "__main__":
    main()
