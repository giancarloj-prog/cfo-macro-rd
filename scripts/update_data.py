"""CFO Macro RD — BCRD updater v3.
Updates validated BCRD homepage indicators and generates CFO Watch rules.
Keeps the last validated value whenever a field cannot be parsed.
"""
from pathlib import Path
from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile
import json, re, requests
from bs4 import BeautifulSoup
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "current.json"
BCRD = "https://www.bancentral.gov.do/"
DGII_PAGE = "https://www.dgii.gov.do/estadisticas/Operaciones-Recaudaciones-ITBIS/Paginas/default.aspx"
DGII_FILES = {
    "itbis_total_operations": "https://www.dgii.gov.do/estadisticas/Operaciones-Recaudaciones-ITBIS/Operaciones%20Totales/Totales-ITBIS-2015-2026.zip",
    "itbis_taxed_operations": "https://www.dgii.gov.do/estadisticas/Operaciones-Recaudaciones-ITBIS/Operaciones%20Gravadas/Gravadas-ITBIS-2015-2026.zip",
    "itbis_revenue": "https://www.dgii.gov.do/estadisticas/Operaciones-Recaudaciones-ITBIS/Recaudacion%20ITBIS/Recaudacion-ITBIS-2015-2026.zip",
}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"}
MONTHS = {"enero":"01","febrero":"02","marzo":"03","abril":"04","mayo":"05","junio":"06",
          "julio":"07","agosto":"08","septiembre":"09","octubre":"10","noviembre":"11","diciembre":"12"}

def norm(s): return re.sub(r"\s+", " ", s.replace("\xa0"," ")).strip()
def per(month, year): return f"{year}-{MONTHS[month.lower()]}"
def num(s): return float(s.replace(",", ""))

MONTH_NAMES = {v: k[:3] for k, v in MONTHS.items()}

def dgii_workbook(url):
    headers = dict(UA)
    headers["Referer"] = DGII_PAGE
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    with ZipFile(BytesIO(r.content)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".xlsx")]
        if not names:
            raise ValueError("El ZIP de DGII no contiene un archivo XLSX")
        return load_workbook(BytesIO(z.read(names[0])), read_only=True, data_only=True)

def dgii_monthly_total(ws, year):
    """Return monthly values from the row named Total, regardless of header row shifts."""
    header_row = None
    months = {}
    for row_number, row in enumerate(ws.iter_rows(), 1):
        vals = [c.value for c in row]
        for i, value in enumerate(vals):
            if isinstance(value, str) and value.strip().lower() in MONTHS:
                months[i] = MONTHS[value.strip().lower()]
        if months:
            header_row = row_number
            break
    if header_row is None:
        raise ValueError(f"No se encontraron meses en la hoja {year}")
    for row in ws.iter_rows(min_row=header_row + 1):
        vals = [c.value for c in row]
        label = next((v for v in vals[:3] if isinstance(v, str) and v.strip()), "")
        if label.strip().lower() == "total":
            out = {}
            for col, month in months.items():
                value = vals[col] if col < len(vals) else None
                if isinstance(value, (int, float)):
                    out[f"{year}-{month}"] = float(value) / 1_000_000
            if not out:
                raise ValueError(f"La fila Total de {year} no contiene valores mensuales")
            return out
    raise ValueError(f"No se encontró la fila Total en la hoja {year}")

def update_dgii(p, hist):
    updated, errors = [], {}
    dgii_hist = hist.setdefault("monthly", {})
    for key, url in DGII_FILES.items():
        try:
            wb = dgii_workbook(url)
            values = {}
            for year in ("2025", "2026"):
                if year in wb.sheetnames:
                    values.update(dgii_monthly_total(wb[year], year))
            if not values:
                raise ValueError("No se extrajeron observaciones")
            dgii_hist.setdefault(key, {}).update(values)
            latest_period = max(values)
            latest_value = values[latest_period]
            prior_period = f"{int(latest_period[:4])-1}{latest_period[4:]}"
            prior_value = dgii_hist[key].get(prior_period)
            yoy = ((latest_value / prior_value) - 1) * 100 if prior_value else None
            setv(p, key, latest_value, latest_period, "DGII")
            if yoy is not None:
                setv(p, key + "_yoy", yoy, latest_period, "DGII")
            updated.append(key)
        except Exception as exc:
            errors[key] = str(exc)

    total = p.get("series", {}).get("itbis_total_operations", {})
    taxed = p.get("series", {}).get("itbis_taxed_operations", {})
    if total.get("period") == taxed.get("period") and total.get("value"):
        setv(p, "itbis_taxed_share", taxed["value"] / total["value"] * 100, total["period"], "DGII")
    p.setdefault("source_health", {})["dgii"] = {
        "ok": not errors,
        "url": DGII_PAGE,
        "updated_fields": updated,
        "errors": errors,
    }
    return updated

def setv(p,k,v,period,source="BCRD"):
    if v is None or period is None: return False
    p.setdefault("series",{})[k]={"value":v,"period":period,"source":source}
    return True

def fx(text):
    m=re.search(r"Tipo de cambio\s+(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+(\d{4}).{0,140}?Compra\s+(\d{1,3}\.\d{4}).{0,100}?Venta\s+(\d{1,3}\.\d{4})",text,re.I|re.S)
    if not m:return None
    d,mo,y,b,s=m.groups(); b=float(b); s=float(s)
    if not (30<b<100 and 30<s<100 and s>=b): return None
    return b,s,f"{y}-{MONTHS[mo.lower()]}-{int(d):02d}"

def watch(p):
    s=p["series"]; items=[]
    inf=s.get("inflation_yoy",{}).get("value")
    if inf is not None:
        if inf>5:
            items.append({"level":"yellow","title":"Inflación: vigilancia","text":f"La inflación interanual se ubica en {inf:.2f}%, por encima del techo de 5.0% del rango meta del BCRD."})
        else:
            items.append({"level":"green","title":"Inflación: dentro de meta","text":f"La inflación interanual se ubica en {inf:.2f}%, dentro del rango meta de 3%-5%."})
    a=s.get("active_rate",{}).get("value"); pol=s.get("policy_rate",{}).get("value")
    if a is not None and pol is not None:
        items.append({"level":"yellow" if a-pol>=8 else "green","title":"Financiamiento: spread bancario","text":f"La tasa activa promedio es {a:.2f}% frente a una TPM de {pol:.2f}%, un diferencial de {a-pol:.2f} puntos porcentuales."})
    im=s.get("imae_yoy",{}).get("value")
    if im is not None:
        items.append({"level":"green" if im>=4 else "yellow","title":"Actividad económica","text":f"El IMAE registra crecimiento interanual de {im:.1f}% en el último dato publicado."})
    r=s.get("gross_reserves",{}).get("value")
    if r is not None:
        items.append({"level":"green","title":"Sector externo: reservas","text":f"Las reservas internacionales brutas se sitúan en US${r:,.1f} millones."})
    p["cfo_watch"]=items

def main():
    p=json.loads(DATA.read_text(encoding="utf-8"))
    r=requests.get(BCRD,headers=UA,timeout=30); r.raise_for_status()
    text=norm(BeautifulSoup(r.text,"html.parser").get_text(" ",strip=True))
    u=[]
    z=fx(text)
    if z:
        b,s,period=z
        for k,v in [("usd_dop_buy",b),("usd_dop_sell",s)]:
            if setv(p,k,v,period):u.append(k)

    patterns=[
      ("inflation_yoy",r"Inflación\s*\(variación %\)\s*(\w+)\s+(\d{4}).{0,180}?Interanual\s+(\d+(?:\.\d+)?)%"),
      ("core_inflation_yoy",r"Inflación subyacente\s*(\w+)\s+(\d{4}).{0,180}?Interanual\s+(\d+(?:\.\d+)?)%"),
      ("policy_rate",r"Tasa de política monetaria\s*(\w+)\s+(\d{4})\s+(\d+(?:\.\d+)?)%"),
      ("imae_yoy",r"IMAE original.*?(\w+)\s+(\d{4})\s+(\d+(?:\.\d+)?)%")
    ]
    for k,pat in patterns:
        m=re.search(pat,text,re.I|re.S)
        if m and m.group(1).lower() in MONTHS and setv(p,k,float(m.group(3)),per(m.group(1),m.group(2))):u.append(k)

    m=re.search(r"Tasas de interés\s*\(promedio ponderado\)\s*(\w+)\s+(\d{4}).{0,300}?Interbancaria\s+(\d+(?:\.\d+)?)%.{0,140}?Activa\s*B\.?M\.?\s+(\d+(?:\.\d+)?)%.{0,140}?Pasiva\s*B\.?M\.?\s+(\d+(?:\.\d+)?)%",text,re.I|re.S)
    if m and m.group(1).lower() in MONTHS:
        period=per(m.group(1),m.group(2))
        for k,v in [("interbank_rate",m.group(3)),("active_rate",m.group(4)),("passive_rate",m.group(5))]:
            if setv(p,k,float(v),period):u.append(k)

    m=re.search(r"Préstamos privados.*?(\w+)\s+(\d{4}).{0,200}?Mon\.?\s*nacional\s+(\d+(?:\.\d+)?)%.{0,120}?Total\s+(\d+(?:\.\d+)?)%",text,re.I|re.S)
    if m and m.group(1).lower() in MONTHS and setv(p,"private_credit_yoy",float(m.group(4)),per(m.group(1),m.group(2))):u.append("private_credit_yoy")

    m=re.search(r"Reservas internacionales\s*\(en US\$ MM\)\s*(\w+)\s+(\d{4}).{0,180}?Brutas\s+\$?([\d,]+(?:\.\d+)?).{0,100}?Netas\s+\$?([\d,]+(?:\.\d+)?)",text,re.I|re.S)
    if m and m.group(1).lower() in MONTHS:
        period=per(m.group(1),m.group(2))
        for k,v in [("gross_reserves",m.group(3)),("net_reserves",m.group(4))]:
            if setv(p,k,num(v),period):u.append(k)

    m=re.search(r"Producto Interno Bruto\s*\(variación % interanual\).*?Ene-Dic\s+(\d{4})\s+(\d+(?:\.\d+)?)%",text,re.I|re.S)
    if m and setv(p,"gdp_growth",float(m.group(2)),m.group(1)):u.append("gdp_growth")

    m=re.search(r"Cuenta corriente\s*\(como % del PIB\).*?2025\s+(-?\d+(?:\.\d+)?)%",text,re.I|re.S)
    if m and setv(p,"current_account_gdp",float(m.group(1)),"2025"):u.append("current_account_gdp")

    # Maintain a compact monthly history used by the dashboard charts.
    hist_path = ROOT / "data" / "history.json"
    try:
        hist = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else {}
    except Exception:
        hist = {}

    dgii_updated = update_dgii(p, hist)
    watch(p)
    p["as_of"]=datetime.now(timezone.utc).date().isoformat()
    p["status"]="live-bcrd-v3"
    p["automation_check_utc"]=datetime.now(timezone.utc).isoformat(timespec="seconds")
    p["updated_fields"]=u
    p.setdefault("source_health",{})["bcrd"]={"ok":True,"url":BCRD,"http_status":r.status_code,"updated_fields":u}
    hist.setdefault("monthly", {})
    for key in ["active_rate","passive_rate","interbank_rate","policy_rate","inflation_yoy",
                "core_inflation_yoy","imae_yoy","gross_reserves","net_reserves","private_credit_yoy"]:
        x = p.get("series", {}).get(key)
        if x and x.get("period") and x.get("value") is not None:
            hist["monthly"].setdefault(key, {})
            hist["monthly"][key][x["period"]] = x["value"]
    hist.setdefault("daily", {})
    for key in ["usd_dop_buy","usd_dop_sell"]:
        x = p.get("series", {}).get(key)
        if x and x.get("period") and x.get("value") is not None:
            hist["daily"].setdefault(key, {})
            hist["daily"][key][x["period"]] = x["value"]
    hist["updated_utc"] = p["automation_check_utc"]
    hist_path.write_text(json.dumps(hist, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    DATA.write_text(json.dumps(p,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Updated:", ", ".join(u + dgii_updated) if (u or dgii_updated) else "none")

if __name__=="__main__": main()
