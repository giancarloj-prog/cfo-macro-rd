"""CFO Macro RD — BCRD automatic updater (V2).

Reads the public BCRD macroeconomic homepage and updates only values that pass
label-based validation. If a field cannot be parsed, the last validated value is
kept. This fail-safe behavior is intentional for a CFO dashboard.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, re, requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "current.json"
BCRD = "https://www.bancentral.gov.do/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; CFO-Macro-RD/2.0; +GitHub-Pages)"}

MONTHS = {
    "enero":"01","febrero":"02","marzo":"03","abril":"04","mayo":"05","junio":"06",
    "julio":"07","agosto":"08","septiembre":"09","octubre":"10","noviembre":"11","diciembre":"12"
}

def norm(s):
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()

def period(month, year):
    return f"{year}-{MONTHS[month.lower()]}"

def get_float(pattern, text, flags=re.I):
    m = re.search(pattern, text, flags)
    return float(m.group(1).replace(",", "")) if m else None

def set_series(payload, key, value, per, source="BCRD"):
    if value is None:
        return False
    payload.setdefault("series", {})[key] = {"value": value, "period": per, "source": source}
    return True

def fetch_bcrd():
    r = requests.get(BCRD, timeout=40, headers=UA)
    r.raise_for_status()
    return norm(BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True))

def update_from_home(payload, text):
    updated = []

    # Inflation block
    m = re.search(r"Inflación\s*\(variación %\)\s*(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(20\d{2})(.*?)(?:Inflación subyacente)", text, re.I)
    if m:
        per = period(m.group(1), m.group(2)); block = m.group(3)
        for key,label in [("inflation_yoy","Interanual"),("inflation_ytd","Acumulada"),("inflation_monthly","Mensual")]:
            v=get_float(label+r"\s*([+-]?\d+(?:\.\d+)?)%",block)
            if set_series(payload,key,v,per): updated.append(key)

    m = re.search(r"Inflación subyacente\s*(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(20\d{2})(.*?)(?:Monetarias|Tasa de política monetaria)", text, re.I)
    if m:
        per = period(m.group(1), m.group(2)); block=m.group(3)
        v=get_float(r"Interanual\s*([+-]?\d+(?:\.\d+)?)%",block)
        if set_series(payload,"core_inflation_yoy",v,per): updated.append("core_inflation_yoy")

    # Policy rate
    m=re.search(r"Tasa de política monetaria\s*(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(20\d{2})\s*([0-9.]+)%",text,re.I)
    if m and set_series(payload,"policy_rate",float(m.group(3)),period(m.group(1),m.group(2))): updated.append("policy_rate")

    # Weighted rates
    m=re.search(r"Tasas de interés\s*\(promedio ponderado\)\s*(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(20\d{2})(.*?)(?:Préstamos privados)",text,re.I)
    if m:
        per=period(m.group(1),m.group(2)); block=m.group(3)
        for key,label in [("interbank_rate","Interbancaria"),("active_rate",r"Activa\s*B\.?M\.?") ,("passive_rate",r"Pasiva\s*B\.?M\.? ")]:
            v=get_float(label+r"\s*([0-9.]+)%",block)
            if key=="passive_rate" and v is None: v=get_float(r"Pasiva\s*B\.?M\.?\s*([0-9.]+)%",block)
            if set_series(payload,key,v,per): updated.append(key)

    # Private credit
    m=re.search(r"Préstamos privados\s*\(variación % interanual\)\s*(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(20\d{2})(.*?)(?:Sector real|IMAE)",text,re.I)
    if m:
        v=get_float(r"Total\s*([0-9.]+)%",m.group(3)); per=period(m.group(1),m.group(2))
        if set_series(payload,"private_credit_yoy",v,per): updated.append("private_credit_yoy")

    # IMAE
    m=re.search(r"IMAE original\s*\(variación % interanual\)\s*(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(20\d{2})\s*([0-9.]+)%.*?Ene[^0-9]*(?:[A-Za-záéíóúñ]+)?\s*(20\d{2})\s*([0-9.]+)%",text,re.I)
    if m:
        per=period(m.group(1),m.group(2))
        if set_series(payload,"imae_yoy",float(m.group(3)),per): updated.append("imae_yoy")
        if set_series(payload,"imae_ytd",float(m.group(5)),per): updated.append("imae_ytd")

    return sorted(set(updated))

def main():
    payload=json.loads(DATA.read_text(encoding="utf-8"))
    now=datetime.now(timezone.utc)
    payload["automation_check_utc"]=now.isoformat()
    try:
        text=fetch_bcrd()
        updated=update_from_home(payload,text)
        payload["source_health"]={"bcrd":{"ok":True,"updated_fields":updated}}
        payload["status"]="live-bcrd"
        payload["as_of"]=now.date().isoformat()
        if len(updated) < 6:
            payload["source_health"]["bcrd"]["warning"]="BCRD loaded, but fewer fields than expected parsed; prior validated values retained."
    except Exception as exc:
        payload["source_health"]={"bcrd":{"ok":False,"error":str(exc)[:220]}}
        payload["status"]="last-valid"
    DATA.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(payload["source_health"],ensure_ascii=False,indent=2))

if __name__=="__main__": main()
