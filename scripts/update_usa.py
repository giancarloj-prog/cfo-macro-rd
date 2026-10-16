"""Read public primary sources; preserve dated observations when a source fails."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import json, re, requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'usa.json'
FED = 'https://www.federalreserve.gov/monetarypolicy/openmarket.htm'
FRED = 'https://fred.stlouisfed.org/series/DGS10'
ISM = 'https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/'
WCI = 'https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry'
MONTHS = {m.lower():i for i,m in enumerate(('January February March April May June July August September October November December').split(),1)}
UA = {'User-Agent':'Mozilla/5.0 (compatible; CFO-Macro-Dashboard/1.0)'}

def page(url):
    try:
        r = requests.get(url, headers=UA, timeout=35)
    except (requests.Timeout, requests.ConnectionError):
        r = requests.get(url, headers=UA, timeout=35)
    r.raise_for_status()
    if 'login.aspx' in r.url.lower() or 'captcha_form' in r.text:
        raise ValueError('La fuente exige acceso interactivo; se conserva el último dato verificado')
    return BeautifulSoup(r.text, 'html.parser')

def text(soup): return re.sub(r'\s+', ' ', soup.get_text(' ', strip=True)).replace('®','').replace('℠','')

def fed():
    soup = page(FED)
    observations = []
    for h in soup.find_all(['h3','h4']):
        if not re.fullmatch(r'20\d{2}', h.get_text(strip=True)): continue
        year = h.get_text(strip=True)
        table = h.find_next('table')
        if table is None: continue
        for row in table.find_all('tr'):
            cells = [c.get_text(' ',strip=True) for c in row.find_all('td')]
            if len(cells) != 4: continue
            dm = re.search(r'([A-Za-z]+)\s+(\d{1,2})', cells[0])
            rate = re.fullmatch(r'([\d.]+)\s*[-–]\s*([\d.]+)', cells[-1])
            if dm and rate and dm[1].lower() in MONTHS:
                period = f'{year}-{MONTHS[dm[1].lower()]:02d}-{int(dm[2]):02d}'
                if period <= datetime.now(timezone.utc).date().isoformat():
                    lo,hi=map(float,rate.groups())
                    if 0 <= lo <= hi <= 30: observations.append((period,lo,hi))
    if not observations: raise ValueError('No se encontró un rango objetivo fechado de la Fed')
    period,lo,hi=max(observations)
    return {'value':hi,'lower':lo,'upper':hi,'period':period,'source':'Federal Reserve','url':FED,'unit':'percent_range'}

def treasury_fred():
    soup=page(FRED)
    content=text(soup)
    # The date must be attached to an observation, not the page update timestamp.
    m=re.search(r'Observations\s+(\d{4}-\d{2}-\d{2}):\s*([\d.]+)',content)
    if not m: raise ValueError('No se encontró una observación DGS10 fechada')
    value=float(m[2])
    if not 0 <= value <= 30: raise ValueError('DGS10 fuera de rango')
    return {'value':value,'period':m[1],'source':'Federal Reserve · FRED (DGS10)','url':FRED,'unit':'percent'}

def treasury():
    url='https://www.federalreserve.gov/releases/h15/'
    try:
        soup=page(url)
        for table in soup.find_all('table'):
            rows=table.find_all('tr')
            if not rows: continue
            headers=[c.get_text(' ',strip=True).replace('*','') for c in rows[0].find_all(['th','td'])]
            dates={}
            for i,h in enumerate(headers):
                try:dates[i]=datetime.strptime(h,'%Y %b %d').date().isoformat()
                except ValueError:pass
            nominal=False
            for row in rows[1:]:
                cells=[c.get_text(' ',strip=True) for c in row.find_all(['th','td'])]
                if not cells: continue
                if re.match(r'^Nominal\b',cells[0]):nominal=True
                if re.match(r'^Inflation indexed\b',cells[0]):nominal=False
                if nominal and cells[0]=='10-year':
                    observations=[(dates[i],float(cells[i])) for i in dates if i<len(cells) and re.fullmatch(r'\d+(?:\.\d+)?',cells[i])]
                    if observations:
                        period,value=max(observations)
                        if 0 <= value <= 30:return {'value':value,'period':period,'source':'Federal Reserve · H.15','url':url,'unit':'percent'}
        raise ValueError('No se encontró el rendimiento nominal a 10 años con fecha')
    except (requests.RequestException,ValueError):
        return treasury_fred()

def pmi(kind, previous):
    sub='pmi' if kind=='manufacturing' else 'services'
    label='Manufacturing' if kind=='manufacturing' else 'Services'
    # The report for the prior calendar month is released in the current month.
    prior=datetime.now(timezone.utc).replace(day=1)-timedelta(days=1)
    month=list(MONTHS)[prior.month-1]
    candidates=[urljoin(ISM,f'{sub}/{month}/')]
    if previous.get('url') and previous['url'] not in candidates: candidates.append(previous['url'])
    errors=[]
    for url in candidates:
        try:
            soup=page(url)
            headings=' '.join(h.get_text(' ',strip=True) for h in soup.find_all('h1')).replace('®','')
            value=re.search(label+r'\s+PMI\s+at\s+([\d.]+)%',headings,re.I)
            period=re.search(r'('+'|'.join(MONTHS)+r')\s+(20\d{2})\s+ISM\s+'+label,headings,re.I)
            if not value or not period: raise ValueError('Faltan el PMI principal y su mes en el encabezado')
            v=float(value[1]); p=f'{period[2]}-{MONTHS[period[1].lower()]:02d}'
            if not 0 <= v <= 100: raise ValueError('PMI fuera de rango')
            return {'value':v,'period':p,'source':'ISM','url':url,'unit':'index'}
        except Exception as exc: errors.append(str(exc))
    # ISM also publishes its own releases on PR Newswire. Discover only from
    # the issuer's page, then verify the issuer and the report heading.
    wire='https://www.prnewswire.com/news/institute-for-supply-management/'
    try:
        listing=page(wire)
        links=[]
        for a in listing.find_all('a',href=True):
            href=a['href']
            if '/news-releases/'+label.lower()+'-pmi-at-' in href:
                url=urljoin(wire,href)
                if url not in links: links.append(url)
        for url in links[:2]:
            soup=page(url)
            if not re.search(r'News provided by\s+Institute for Supply Management',text(soup),re.I):
                continue
            heading=' '.join(h.get_text(' ',strip=True) for h in soup.find_all('h1')).replace('®','')
            value=re.search(label+r'\s+PMI\s+at\s+([\d.]+)%',heading,re.I)
            period=re.search(r'('+'|'.join(MONTHS)+r')\s+(20\d{2})\s+ISM\s+'+label,heading,re.I)
            if value and period and 0 <= float(value[1]) <= 100:
                return {'value':float(value[1]),'period':f'{period[2]}-{MONTHS[period[1].lower()]:02d}', 'source':'ISM · comunicado oficial', 'url':url,'report_url':urljoin(ISM,f'{sub}/{period[1].lower()}/'),'unit':'index'}
        raise ValueError('No se encontró un comunicado de ISM fechado')
    except Exception as exc: errors.append(str(exc))
    raise ValueError('; '.join(errors))

def containers():
    content=text(page(WCI))
    m=re.search(r'(?:assessment for\s+\w+,?\s+)(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2}).{0,600}?World Container Index\s*\(WCI\).{0,200}?\bto\s+\$([\d,]+(?:\.\d+)?)\s+per\s+40',content,re.I)
    if not m: raise ValueError('No se encontró el WCI compuesto con fecha y unidad')
    month=m[2].lower(); month=next((v for k,v in MONTHS.items() if k.startswith(month)),None)
    value=float(m[4].replace(',',''))
    if month is None or not 100 <= value <= 50000: raise ValueError('WCI inválido')
    return {'value':value,'period':f'{m[3]}-{month:02d}-{int(m[1]):02d}','source':'Drewry','url':WCI,'unit':'usd_40ft'}

def main():
    p=json.loads(DATA.read_text()) if DATA.exists() else {'series':{}}
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    jobs={'fed_rate':fed,'treasury_10y':treasury,'ism_manufacturing':lambda:pmi('manufacturing',p['series'].get('ism_manufacturing',{})),'ism_services':lambda:pmi('services',p['series'].get('ism_services',{})),'world_container_index':containers}
    def run(k):
        try:
            x=jobs[k]()
            old=p['series'].get(k,{})
            if x['period'] < old.get('period',''): raise ValueError('La fuente devolvió un período anterior; se conserva el dato vigente')
            x['verified_at']=now
            return k,x,None
        except Exception as exc: return k,None,str(exc)
    health={}
    for key,item,error in ThreadPoolExecutor(max_workers=5).map(run,jobs):
        if item: p.setdefault('series',{})[key]=item
        health[key]={'ok':error is None,'checked_at':now,'error':error}
    p['source_health']=health;p['checked_at']=now
    DATA.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
    print('USA:',json.dumps({k:v['ok'] for k,v in health.items()}))

if __name__=='__main__':main()
