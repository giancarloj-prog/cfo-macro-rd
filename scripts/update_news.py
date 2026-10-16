"""Daily pharma headlines: trusted publishers, dated RSS items, no daily archive."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urlencode
from concurrent.futures import ThreadPoolExecutor
from html import unescape
import json, re, unicodedata, requests
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'news.json'
TZ=ZoneInfo('America/Santo_Domingo')
REGIONS={
 'rd':{'label':'República Dominicana','domains':['listindiario.com','diariolibre.com','acento.com.do','eldia.com.do','elnuevodiario.com.do','hoy.com.do','elcaribe.com.do']},
 'centroamerica':{'label':'Centroamérica','domains':['prensalibre.com','lahora.gt','nacion.com','crhoy.com','laprensagrafica.com','elsalvador.com','elmundo.sv','laprensa.hn','elheraldo.hn','prensa.com','laestrella.com.pa','laprensani.com','confidencial.digital']},
 'mexico':{'label':'México','domains':['eluniversal.com.mx','eleconomista.com.mx','elfinanciero.com.mx','milenio.com','expansion.mx','forbes.com.mx']},
 'usa':{'label':'USA','domains':['reuters.com','apnews.com','cnn.com','wsj.com','cnbc.com','nytimes.com','statnews.com','fiercepharma.com','biopharmadive.com'],'focus':'(FDA OR US OR USA OR "United States" OR American)'},
 'europa':{'label':'Europa','domains':['reuters.com','bbc.com','bbc.co.uk','ft.com','theguardian.com','euronews.com','dw.com','elpais.com','elmundo.es','eldiario.es','pharmaphorum.com'],'focus':'(Europe OR Europa OR European OR EU OR EMA OR UK)'},
 'global':{'label':'Global','domains':['reuters.com','apnews.com','cnn.com','wsj.com','ft.com','bbc.com','theguardian.com','statnews.com','fiercepharma.com','biopharmadive.com']}
}
TOPIC='(medicamentos OR farmacéutica OR farmacéutico OR fármaco OR farmacia OR vacunas OR pharmaceutical OR pharma OR drugmaker OR medicines OR "drug approval" OR "drug discovery" OR biotech)'
TOPIC_RX=re.compile(r'medicament|farmac|fármac|pharma|\bdrug|\bmedicine|vacun|vaccine|biotech|biologic|biosimilar|cofepris|digemaps|\bfda\b|clinical trial|ensayo clínic|oncolog|cancer drug',re.I)
EXCLUDE_RX=re.compile(r'narcotráfic|narcotrafic|drug trafficking|drug charges|drug cartel|drug bust|drug smuggling',re.I)

def domain(url):return (urlparse(url).hostname or '').lower().removeprefix('www.')
def trusted(host,domains):return any(host==x or host.endswith('.'+x) for x in domains)
def normalized(title):return ''.join(c for c in unicodedata.normalize('NFKD',title.casefold()) if not unicodedata.combining(c) and c.isalnum())

def parse_feed(content, region, day):
    config=REGIONS[region];items=[]
    for item in ET.fromstring(content).findall('.//item'):
        title=unescape(item.findtext('title') or '').strip()
        source=item.find('source')
        if source is None:continue
        publisher=(source.text or '').strip();source_url=source.get('url','')
        if not publisher or not trusted(domain(source_url),config['domains']):continue
        suffix=' - '+publisher
        if title.endswith(suffix):title=title[:-len(suffix)]
        if not TOPIC_RX.search(title) or EXCLUDE_RX.search(title):continue
        try:
            published=parsedate_to_datetime(item.findtext('pubDate') or '')
            if published.tzinfo is None:continue
            if published.astimezone(TZ).date().isoformat()!=day:continue
        except (ValueError,TypeError,OverflowError):continue
        link=item.findtext('link') or ''
        host=domain(link)
        if urlparse(link).scheme!='https' or not (host=='news.google.com' or trusted(host,config['domains'])):continue
        items.append({'title':title,'publisher':publisher,'publisher_url':source_url,'url':link,'published_at':published.astimezone(timezone.utc).isoformat(timespec='seconds'),'regions':[region]})
    return items

def fetch_region(region, day):
    config=REGIONS[region];dt=datetime.fromisoformat(day)
    topic='(medicamentos OR farmacéutica OR farmacia OR vacunas)' if region in ('rd','centroamerica','mexico') else '(pharma OR drug OR biotech OR pharmaceutical OR medicine)'
    lang='en-US' if region in ('usa','europa','global') else 'es-419'
    gl='DO' if region=='rd' else 'US' if lang=='en-US' else 'MX'
    # Short publisher groups avoid search engines dropping long boolean queries.
    groups=[config['domains'][i:i+3] for i in range(0,len(config['domains']),3)]
    def group(domains):
        query=topic+' ('+' OR '.join('site:'+d for d in domains)+') '+config.get('focus','')
        query+=f' after:{(dt-timedelta(days=1)).date()} before:{(dt+timedelta(days=2)).date()}'
        url='https://news.google.com/rss/search?'+urlencode({'q':query,'hl':lang,'gl':gl,'ceid':gl+':'+('en' if lang=='en-US' else 'es-419')})
        try:
            r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (compatible; CFO-Macro-Dashboard/1.0)'},timeout=35);r.raise_for_status()
            return parse_feed(r.content,region,day),None
        except Exception as exc:return [],str(exc)
    items=[];errors=[]
    for found,error in ThreadPoolExecutor(max_workers=3).map(group,groups):
        items.extend(found)
        if error:errors.append(error)
    return items,'; '.join(errors) if errors else None

def build(day, results, previous=None):
    merged={};health={}
    for region,(items,error) in results.items():
        health[region]={'ok':error is None,'error':error,'count':len(items)}
        if error and previous and previous.get('date')==day:
            items=items+[dict(x,regions=[region]) for x in previous.get('items',[]) if region in x.get('regions',[])]
        for item in items:
            # Recheck carried observations too: no older headline survives rollover.
            try:
                if datetime.fromisoformat(item['published_at']).astimezone(TZ).date().isoformat()!=day:continue
            except (ValueError,KeyError):continue
            key=normalized(item['title'])
            if key in merged:
                merged[key]['regions']=sorted(set(merged[key]['regions']+item['regions']))
            else:merged[key]=dict(item,regions=list(item['regions']))
    return {'date':day,'timezone':str(TZ),'checked_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'regions':{k:v['label'] for k,v in REGIONS.items()},'source_health':health,'items':sorted(merged.values(),key=lambda x:x['published_at'],reverse=True),'discovery':'Google News RSS · medios seleccionados; enlaces al agregador redirigen a la publicación original'}

def main():
    day=datetime.now(TZ).date().isoformat()
    try:previous=json.loads(DATA.read_text())
    except (FileNotFoundError,ValueError):previous=None
    def run(region):
        try:return region,fetch_region(region,day)
        except Exception as exc:return region,([],str(exc))
    results=dict(ThreadPoolExecutor(max_workers=6).map(run,REGIONS))
    payload=build(day,results,previous)
    DATA.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print('News:',len(payload['items']),'headlines;',json.dumps({k:v['ok'] for k,v in payload['source_health'].items()}))

if __name__=='__main__':main()
