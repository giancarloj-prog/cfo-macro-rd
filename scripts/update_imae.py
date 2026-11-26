"""Extract explicitly monthly sector rates from official BCRD releases."""
import json, re, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'imae_sectors.json'
BASE='https://www.bancentral.gov.do'
MONTHS='enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
MO='|'.join(MONTHS)
ALIASES={'Construcción':'construccion','Manufactura local':'manufactura local','Manufactura zonas francas':'manufactura (?:de )?zonas francas','Agropecuaria':'agropecuari[oa]','Servicios financieros':'servicios financieros','Enseñanza':'ensenanza','Otras actividades de servicios de mercado':'otras actividades de servicios de mercado','Hoteles, bares y restaurantes':'hoteles,? bares y restaurantes','Servicios profesionales':'servicios profesionales','Transporte y almacenamiento':'transporte y almacenamiento','Energía y agua':'energia y agua','Comercio':'comercio','Administración pública':'administracion publica(?: y defensa)?','Salud':'salud','Comunicaciones':'comunicaciones','Minería':'mineria|explotacion de minas y canteras','Servicios':'actividades de servicios en su conjunto','Actividades inmobiliarias y de alquiler':'actividades inmobiliarias y de alquiler'}
NUM=r'(-?\d{1,3}(?:[.,]\d+)?)'
def norm(s):
    return re.sub(r'\s+',' ',''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))).strip()
def number(s):
    v=float(s.replace(',','.'))
    if not -100<=v<=100:raise ValueError('Tasa fuera de rango')
    return v
def parse(content):
    t=norm(content)
    m=re.search(r'\(imae\)\s+correspondiente a ('+MO+r') de (20\d{2}) registr[oó] una variacion interanual de '+NUM+r'\s*%',t)
    if not m:raise ValueError('IMAE mensual no identificado')
    month,year=m[1],m[2]
    period=f'{year}-{MONTHS.index(month)+1:02d}'
    overall=number(m[3])
    # Restrict extraction to the paragraph explicitly describing the month.
    block=re.search(r'(?:comportamiento exhibido por la economia(?: dominicana)? durante el mes de '+month+r' de '+year+r')(.+?)(?=la actividad construccion|por su parte, la manufactura|$)',t)
    if not block:raise ValueError('Desglose mensual no identificado')
    b=block[1]
    # Stop before any cumulative-period discussion.
    b=re.split(r'\b(?:periodo |durante )?enero\s*[-–]',b,maxsplit=1)[0]
    sectors={}
    for name,alias in ALIASES.items():
        hit=re.search(r'\b(?:'+alias+r')\s*\(\s*'+NUM+r'\s*%\s*\)',b)
        if hit:sectors[name]=number(hit[1])
    neg=re.search(r'\bmineria mostro una variacion negativa de '+NUM+r'\s*%',b)
    if neg:sectors['Minería']=-abs(number(neg[1]))
    if len(sectors)<3:raise ValueError('Desglose insuficiente')
    return period,overall,sectors
def fetch(url):
    r=requests.get(url,timeout=35,headers={'User-Agent':'Mozilla/5.0'});r.raise_for_status()
    return BeautifulSoup(r.content,'html.parser')
def candidates():
    soup=fetch(BASE)
    for a in soup.find_all('a',href=True):
        url=urljoin(BASE,a['href'])
        if urlparse(url).hostname in ('www.bancentral.gov.do','bancentral.gov.do') and re.match(r'/a/d/\d+',urlparse(url).path):
            yield url
def main():
    d=json.loads(DATA.read_text())
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    found=[]
    errors=[]
    try:
        for url in dict.fromkeys(candidates()):
            try:
                p,v,s=parse(fetch(url).get_text(' ',strip=True))
                if p<=now[:7]:found.append((p,v,s,url))
            except Exception as exc:errors.append(str(exc))
        if not found:raise ValueError('No se encontró comunicado mensual compatible')
        p,v,s,url=max(found,key=lambda x:x[0])
        if p<max(d['overall']):raise ValueError('Comunicado anterior al dato vigente')
        d['overall'][p]=v
        for k,v in s.items():d['sectors'].setdefault(k,{})[p]=v
        d['months']=sorted(set(d['months']+[p]))
        if url not in d['sources']:d['sources'].append(url)
        d['updated']=now[:10]
        d['source_health']={'ok':True,'period':p,'url':url}
    except Exception as exc:
        d['source_health']={'ok':False,'error':str(exc)}
    d['checked_at']=now
    DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    print('IMAE:',d['source_health'])
if __name__=='__main__':main()
