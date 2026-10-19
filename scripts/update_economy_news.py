"""Daily Dominican economy headlines and economist-name searches; public RSS only."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode,urlparse
from concurrent.futures import ThreadPoolExecutor
from html import unescape
import json,re,unicodedata,requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'economy_news.json'
TZ=ZoneInfo('America/Santo_Domingo')
DOMAINS=['diariolibre.com','listindiario.com','eldinero.com.do','acento.com.do','hoy.com.do','eldia.com.do','elcaribe.com.do','elnuevodiario.com.do','bancentral.gov.do','hacienda.gob.do','dgii.gov.do','sb.gob.do','simv.gob.do','sipen.gob.do','bvrd.com.do']
DOMAINS=list(dict.fromkeys(x for x in DOMAINS if ' ' not in x))
TOPICS={'bcrd':'Banco Central','fiscal':'Hacienda y finanzas públicas','dgii':'DGII e impuestos','finance':'Sector financiero','securities':'Mercado de valores','economy':'Economía dominicana','opinion':'Opinión y economistas'}
ECONOMISTS={
 'andy':{'name':'Andy Dauhajre','aliases':['Andy Dauhajre','Andy Dahajre','Andy Dajuhare','Andrés Dauhajre']},
 'jaime':{'name':'Jaime Aristy Escuder','aliases':['Jaime Aristy','Jaime Aristy Escuder']},
 'juan_ariel':{'name':'Juan Ariel Jiménez','aliases':['Juan Ariel Jiménez','Juan Ariel Jimenez']},
 'raul':{'name':'Raúl Ovalle','aliases':['Raúl Ovalle','Raul Ovalle']},
 'jose_luis':{'name':'José Luis de Ramón','aliases':['José Luis de Ramón','Jose Luis de Ramon']},
 'nassim':{'name':'Nassim Alemany','aliases':['Nassim Alemany']},
}
QUERIES={
 'bcrd':'("Banco Central" OR BCRD OR "política monetaria")',
 'fiscal':'(Hacienda OR DIGEPRES OR "deuda pública" OR "presupuesto nacional")',
 'dgii':'(DGII OR ITBIS OR "reforma fiscal" OR "impuestos internos")',
 'finance':'(banca OR "sector financiero" OR "superintendencia de bancos" OR "tasas de interés")',
 'securities':'("mercado de valores" OR SIMV OR "puestos de bolsa" OR "bolsa de valores" OR "fondos de inversión")',
 'economy':'(economía OR inflación OR PIB OR empleo OR remesas OR exportaciones)',
}
def fold(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.casefold()) if not unicodedata.combining(c))
def host(u):return (urlparse(u).hostname or '').lower().removeprefix('www.')
def trusted(h):return any(h==d or h.endswith('.'+d) for d in DOMAINS)
def clean(s):return BeautifulSoup(unescape(s or ''),'html.parser').get_text(' ',strip=True)
ECON_RX=re.compile(r'econom|financ|banc|fiscal|tribut|impuest|itbis|dgii|hacienda|presupuest|deuda|inflacion|monetari|\bpib\b|\bbonos?\b|bolsa|inversion|remesa|exporta|empleo|salario|pensiones|mercado de valores',re.I)
PATTERNS={
 'bcrd':r'banco central|\bbcrd\b|politica monetaria|tasa de politica',
 'fiscal':r'hacienda|digepres|presupuesto|deuda publica|gasto publico|deficit fiscal|finanzas publicas',
 'dgii':r'\bdgii\b|\bitbis\b|impuest|tribut|reforma fiscal',
 'finance':r'\bbanc\w*|sector financiero|superintendencia de bancos|tasas? de interes|credito|pensiones|sipen',
 'securities':r'mercado de valores|\bsimv\b|puestos? de bolsa|bolsa de valores|fondos? de inversion|bonos|fideicomis',
}

def parse_feed(content,day,topic=None,economist=None):
    found=[]
    for item in ET.fromstring(content).findall('.//item'):
        source=item.find('source')
        if source is None:continue
        publisher=(source.text or '').strip();publisher_url=source.get('url','')
        if not publisher or not trusted(host(publisher_url)):continue
        title=clean(item.findtext('title'))
        suffix=' - '+publisher
        if title.endswith(suffix):title=title[:-len(suffix)]
        context=fold(title+' '+clean(item.findtext('description')))
        if not ECON_RX.search(context):continue
        try:
            published=parsedate_to_datetime(item.findtext('pubDate') or '')
            if published.tzinfo is None or published.astimezone(TZ).date().isoformat()!=day:continue
        except (ValueError,TypeError,OverflowError):continue
        link=item.findtext('link') or ''
        if urlparse(link).scheme!='https' or not(host(link)=='news.google.com' or trusted(host(link))):continue
        topics=[k for k,pattern in PATTERNS.items() if re.search(pattern,context)]
        if topic in TOPICS:topics.append(topic)
        economists=[k for k,c in ECONOMISTS.items() if any(fold(a) in context for a in c['aliases'])]
        match='headline' if economists else None
        if economist in ECONOMISTS:
            economists.append(economist)
            if match is None:match='search'
        if economists or re.search(r'opinion|columna|analisis|economistas?',context):topics.append('opinion')
        if not topics:topics=['economy']
        found.append(dict(title=title,publisher=publisher,publisher_url=publisher_url,url=link,published_at=published.astimezone(timezone.utc).isoformat(timespec='seconds'),topics=sorted(set(topics)),economists=sorted(set(economists)),economist_match=match))
    return found

def fetch_job(job,day):
    key,topic,economist,query=job
    dt=datetime.fromisoformat(day)
    if economist is None:query+=' ("República Dominicana" OR dominicano OR dominicana OR BCRD OR DGII OR SIMV)'
    query+=f' after:{(dt-timedelta(days=1)).date()} before:{(dt+timedelta(days=1)).date()}'
    url='https://news.google.com/rss/search?'+urlencode(dict(q=query,hl='es-419',gl='DO',ceid='DO:es-419'))
    try:
        r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (CFO-Macro-RD)'},timeout=25);r.raise_for_status()
        return key,(parse_feed(r.content,day,topic,economist),None)
    except Exception as exc:return key,([],type(exc).__name__+': '+str(exc)[:160])

def build(day,results,previous=None):
    merged={};health={}
    for key,(items,error) in results.items():
        health[key]=dict(ok=error is None,error=error,count=len(items))
        for item in items:
            x=dict(item,topics=list(item['topics']),economists=list(item['economists']),searches=[key])
            add_item(merged,x,day)
    # Keep discoveries for the whole day, even when search ranking changes later.
    if previous and previous.get('date')==day:
        for x in previous.get('items',[]):add_item(merged,x,day)
    return dict(date=day,timezone=str(TZ),checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),topics=TOPICS,economists={k:v['name'] for k,v in ECONOMISTS.items()},source_health=health,items=sorted(merged.values(),key=lambda x:x['published_at'],reverse=True),discovery='Google News RSS · medios dominicanos seleccionados y fuentes oficiales; cobertura no exhaustiva.')

def add_item(merged,item,day):
    try:
        published=datetime.fromisoformat(item['published_at'])
        if published.tzinfo is None or published.astimezone(TZ).date().isoformat()!=day:return
    except (ValueError,KeyError):return
    key=host(item['publisher_url'])+':'+re.sub(r'\W+','',fold(item['title']))
    if key in merged:
        old=merged[key]
        for field in ('topics','economists','searches'):old[field]=sorted(set(old.get(field,[])+item.get(field,[])))
        if item.get('economist_match')=='headline':old['economist_match']='headline'
    else:merged[key]=dict(item)

def main():
    day=datetime.now(TZ).date().isoformat()
    try:previous=json.loads(DATA.read_text())
    except (ValueError,FileNotFoundError):previous=None
    jobs=[(k,k,None,q) for k,q in QUERIES.items()]
    jobs += [('economist_'+k,'opinion',k,'('+' OR '.join('"'+a+'"' for a in c['aliases'])+')') for k,c in ECONOMISTS.items()]
    with ThreadPoolExecutor(max_workers=4) as pool:results=dict(pool.map(lambda job:fetch_job(job,day),jobs))
    payload=build(day,results,previous)
    DATA.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print('RD economy news:',len(payload['items']),'items;',sum(not x['ok'] for x in payload['source_health'].values()),'failed searches')
if __name__=='__main__':main()
