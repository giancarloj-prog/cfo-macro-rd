"""Read public primary sources; preserve dated observations when a source fails."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
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

CPI='https://www.bls.gov/news.release/cpi.nr0.htm'
SP500='https://fred.stlouisfed.org/series/SP500'

def inflation_us():
    try:
        content=text(page(CPI))
        period=re.search(r'CONSUMER PRICE INDEX\s*[-–]\s*('+'|'.join(MONTHS)+r')\s+(20\d{2})',content,re.I)
        rate=re.search(r'Over the last 12 months, the all items index (increased|decreased|declined|rose|fell)\s+([\d.]+)\s+percent',content,re.I)
        if not period or not rate:raise ValueError('Faltan el mes y la inflación general CPI-U interanual')
        value=float(rate[2])*(-1 if rate[1].lower() in ('decreased','declined','fell') else 1)
        if not -30 <= value <= 100:raise ValueError('CPI-U interanual fuera de rango')
        return {'value':value,'period':f'{period[2]}-{MONTHS[period[1].lower()]:02d}','source':'BLS · CPI-U','url':CPI,'unit':'percent','description':'Inflación general interanual · sin ajuste estacional'}
    except (requests.RequestException,ValueError):
        # FRED mirrors the BLS non-seasonally-adjusted all-items CPI (CPIAUCNS).
        # This avoids relying solely on the frequently timing-out BLS API.
        try:
            import csv, io
            url='https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS'
            response=requests.get(url,headers=UA,timeout=20)
            response.raise_for_status()
            values={}
            for row in csv.DictReader(io.StringIO(response.text)):
                date=row.get('observation_date') or row.get('DATE')
                raw=row.get('CPIAUCNS','')
                if date and re.fullmatch(r'\d{4}-\d{2}-01',date) and re.fullmatch(r'\d+(?:\.\d+)?',raw):
                    values[date[:7]]=float(raw)
            if not values:raise ValueError('FRED CPIAUCNS sin observaciones')
            latest=max(values)
            prior=f'{int(latest[:4])-1}{latest[4:]}'
            if prior not in values or values[prior]<=0:raise ValueError('Falta comparación anual en FRED')
            value=round((values[latest]/values[prior]-1)*100,1)
            if not -30<=value<=100:raise ValueError('Inflación calculada fuera de rango')
            return {'value':value,'period':latest,'source':'BLS · CPI-U (vía FRED)','url':'https://fred.stlouisfed.org/series/CPIAUCNS','unit':'percent','series_id':'CPIAUCNS','description':'Inflación general interanual · sin ajuste estacional'}
        except (requests.RequestException,ValueError,KeyError,TypeError):
            pass
        url='https://api.bls.gov/publicAPI/v1/timeseries/data/CUUR0000SA0'
        r=requests.get(url,headers=UA,timeout=35);r.raise_for_status();payload=r.json()
        if payload.get('status')!='REQUEST_SUCCEEDED':raise ValueError('BLS API no disponible')
        series=payload['Results']['series']
        if not series or series[0]['seriesID']!='CUUR0000SA0':raise ValueError('Serie CPI-U incorrecta')
        values={f"{x['year']}-{int(x['period'][1:]):02d}":float(x['value']) for x in series[0]['data'] if re.fullmatch(r'M(?:0[1-9]|1[0-2])',x['period']) and re.fullmatch(r'-?\d+(?:\.\d+)?',str(x['value']))}
        latest=max(values);prior=f'{int(latest[:4])-1}{latest[4:]}'
        if prior not in values or values[prior]<=0:raise ValueError('Falta el mes comparable del CPI-U')
        value=round((values[latest]/values[prior]-1)*100,1)
        return {'value':value,'period':latest,'source':'BLS · CPI-U','url':CPI,'unit':'percent','series_id':'CUUR0000SA0','description':'Inflación general interanual · sin ajuste estacional'}

def sp500_fred():
    content=text(page(SP500))
    m=re.search(r'Observations\s+(\d{4}-\d{2}-\d{2}):\s*([\d,]+(?:\.\d+)?)',content)
    if not m:raise ValueError('No se encontró un cierre fechado del S&P 500')
    value=float(m[2].replace(',',''))
    if not 100 <= value <= 100000:raise ValueError('S&P 500 fuera de rango')
    return {'value':value,'period':m[1],'source':'S&P Dow Jones Indices · FRED','url':SP500,'unit':'index_points','description':'Último cierre publicado · puntos del índice'}

def sp500_yahoo(now=None):
    url='https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=5d&interval=1d'
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=25);r.raise_for_status()
    results=r.json().get('chart',{}).get('result')
    if not results:raise ValueError('No se recibieron cierres del S&P 500')
    x=results[0];meta=x['meta']
    if meta.get('symbol')!='^GSPC':raise ValueError('Símbolo incorrecto: se requiere el índice S&P 500')
    tz=ZoneInfo('America/New_York');now=now or datetime.now(timezone.utc)
    regular_end=datetime.fromtimestamp(meta['currentTradingPeriod']['regular']['end'],timezone.utc)
    session_day=regular_end.astimezone(tz).date()
    closes=x['indicators']['quote'][0]['close'];observations=[]
    for ts,value in zip(x['timestamp'],closes):
        day=datetime.fromtimestamp(ts,timezone.utc).astimezone(tz).date()
        if value is None or day>now.astimezone(tz).date():continue
        # A daily candle for the current session is still an intraday quote.
        if day>=session_day and now<regular_end+timedelta(minutes=15):continue
        value=float(value)
        if 100 <= value <= 100000:observations.append((day.isoformat(),round(value,2)))
    if not observations:raise ValueError('No hay una sesión completada del S&P 500')
    period,value=max(observations)
    return {'value':value,'period':period,'source':'Yahoo Finance · S&P 500','url':'https://finance.yahoo.com/quote/%5EGSPC/','unit':'index_points','description':'Último cierre publicado · puntos del índice'}

def sp500():
    try:return sp500_fred()
    except (requests.RequestException,ValueError):return sp500_yahoo()

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

COMMODITIES = {
    'wti': ('DCOILWTICO', 'usd_barrel', 'WTI spot · Cushing, Oklahoma · US$/barril'),
}

def commodity(key):
    series, unit, description = COMMODITIES[key]
    url = 'https://fred.stlouisfed.org/series/' + series
    content = text(page(url))
    m = re.search(r'Observations\s+(\d{4}-\d{2}-\d{2}):\s*(-?[\d,]+(?:\.\d+)?)', content)
    if not m: raise ValueError('No hay observación fechada de ' + series)
    value = float(m[2].replace(',', ''))
    if not -100 <= value <= 10000: raise ValueError('Precio fuera de rango')
    if m[1] > datetime.now(timezone.utc).date().isoformat(): raise ValueError('Observación futura')
    return dict(value=value, period=m[1], unit=unit, source='EIA · FRED', url=url, description=description, series_id=series)

EIA_WTI = 'https://www.eia.gov/dnav/pet/hist/RWTCD.htm'

def parse_wti_eia(soup, today=None):
    heading=text(soup)
    if not re.search(r'Cushing.*?WTI.*?Spot Price',heading,re.I) or 'Dollars per Barrel' not in heading:
        raise ValueError('La página no identifica WTI spot en US$/barril')
    today=today or datetime.now(timezone.utc).date()
    observations=[]
    for row in soup.find_all('tr'):
        cells=row.find_all('td',recursive=False)
        if len(cells)!=6:continue
        label=cells[0].get_text(' ',strip=True)
        m=re.fullmatch(r'(20\d{2})\s+([A-Za-z]{3})-\s*(\d{1,2})\s+to\s+([A-Za-z]{3})-\s*(\d{1,2})',label)
        if not m:continue
        start=datetime.strptime(f'{m[1]}-{m[2]}-{m[3]}','%Y-%b-%d').date()
        if start.weekday()!=0:raise ValueError('Inicio semanal inesperado en EIA')
        for offset,cell in enumerate(cells[1:]):
            raw=cell.get_text(strip=True).replace(',','')
            if not re.fullmatch(r'-?\d+(?:\.\d+)?',raw):continue
            value=float(raw);day=start+timedelta(days=offset)
            if day<=today and -100<=value<=10000:observations.append((day.isoformat(),value))
    if not observations:raise ValueError('EIA sin precios WTI fechados')
    period,value=max(observations)
    return dict(value=value,period=period,unit='usd_barrel',source='EIA · fuente directa',url=EIA_WTI,description='WTI spot · Cushing, Oklahoma · US$/barril · último dato publicado',series_id='RWTC')

def wti(previous=None):
    errors=[]
    for source,fetcher in [('EIA directa',lambda:parse_wti_eia(page(EIA_WTI))),('FRED',lambda:commodity('wti'))]:
        try:
            x=fetcher()
            if x['period']<(previous or {}).get('period',''):raise ValueError('Período anterior al dato guardado')
            if errors:x['fallback_note']='Se utilizó FRED porque la consulta directa a EIA no estuvo disponible.'
            return x
        except (requests.RequestException,ValueError) as exc:errors.append(source+': '+str(exc))
    raise ValueError('; '.join(errors))

def gold(now=None):
    # GC=F is a futures reference, explicitly identified rather than labeled spot.
    url='https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF?range=5d&interval=1d'
    r=requests.get(url,headers=UA,timeout=35);r.raise_for_status()
    x=r.json()['chart']['result'][0]
    if x['meta'].get('symbol')!='GC=F': raise ValueError('Contrato de oro incorrecto')
    now=now or datetime.now(timezone.utc)
    end=datetime.fromtimestamp(x['meta']['currentTradingPeriod']['regular']['end'],timezone.utc)
    tz=ZoneInfo(x['meta'].get('exchangeTimezoneName','America/New_York'))
    observations=[]
    for ts,value in zip(x['timestamp'],x['indicators']['quote'][0]['close']):
        day=datetime.fromtimestamp(ts,timezone.utc).astimezone(tz).date()
        if value is None or day>now.astimezone(tz).date():continue
        if day>=end.astimezone(tz).date() and now<end+timedelta(minutes=30):continue
        if 0<float(value)<100000:observations.append((day.isoformat(),round(float(value),2)))
    if not observations:raise ValueError('Sin sesión completada de oro')
    period,value=max(observations)
    return dict(value=value,period=period,unit='usd_oz',source='Yahoo Finance · COMEX',url='https://finance.yahoo.com/quote/GC=F/',description='Futuros de oro · GC=F · último cierre diario · US$/onza troy')

def parse_remittances(content, url):
    pattern=(r'entre enero y ('+'|'.join({'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12})+
             r') de (20\d{2}),? las remesas recibidas alcanzaron.{0,50}?US\$\s*([\d,]+\.\d+) millones.{0,180}?(aumento|disminución).{0,100}?un\s+([\d.]+)\s*%.{0,100}?mismo per[ií]odo.{0,30}?(20\d{2})')
    months={'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12}
    found=[]
    for m in re.finditer(pattern,content,re.I):
        if int(m[6])!=int(m[2])-1:continue
        period=f'{m[2]}-{months[m[1].lower()]:02d}'
        if period>datetime.now(timezone.utc).strftime('%Y-%m'):continue
        value=float(m[3].replace(',',''));yoy=float(m[5])*(-1 if m[4].lower()=='disminución' else 1)
        if value<=0 or not -100<yoy<100:continue
        found.append(dict(value=value,period=period,yoy=yoy,unit='usd_million',source='Banco Central · BCRD',url=url,description=f'Enero–{m[1].lower()} {m[2]} · YoY frente al mismo período de {m[6]}'))
    if not found:raise ValueError('Falta acumulado de remesas con comparación del mismo período')
    return max(found,key=lambda x:x['period'])

def remittances():
    base='https://www.bancentral.gov.do'
    def post(path, data):
        r=requests.post(base+path,data=data,headers=UA,timeout=35);r.raise_for_status()
        p=r.json()
        return json.loads(p) if isinstance(p,str) else p
    listing=post('/Home/GetArticles',dict(requestIsFromPortal='true',filter='Remesas',languageName='es',categoryCode='CAT-037',skipCount=0,maxResultCount=10))
    items=listing['result']['items']
    candidates=[x for x in items if 'remesas' in x.get('title','').lower() and x.get('isActive')]
    if not candidates:raise ValueError('Sin comunicado de remesas')
    latest=max(candidates,key=lambda x:x['creationTime'])
    content=post('/Home/GetContentForRender',dict(id=latest['id'],languageName='es'))['result']['article']['content']
    return parse_remittances(text(BeautifulSoup(content,'html.parser')),base+'/a/d/'+latest['stringId'])

def main():
    p=json.loads(DATA.read_text()) if DATA.exists() else {'series':{}}
    for removed in ('diesel','gasoline'):
        p.get('series',{}).pop(removed,None)
        p.get('source_health',{}).pop(removed,None)
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    jobs={'wti':lambda:wti(p['series'].get('wti',{})),'gold':gold,'remittances_ytd':remittances,'inflation_us_yoy':inflation_us,'sp500':sp500,'fed_rate':fed,'treasury_10y':treasury,'ism_manufacturing':lambda:pmi('manufacturing',p['series'].get('ism_manufacturing',{})),'ism_services':lambda:pmi('services',p['series'].get('ism_services',{})),'world_container_index':containers}
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
