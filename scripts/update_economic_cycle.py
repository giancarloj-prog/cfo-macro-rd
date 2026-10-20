"""Latest-only US Business Cycle Indicators, sourced exclusively from The Conference Board.
Conservative parsing: never infer per-component contributions or use proxy data.
"""
import json,re,requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin
ROOT=Path(__file__).resolve().parents[1]
URL='https://www.conference-board.org/topics/us-leading-indicators/'
MONTHS={m.lower():i for i,m in enumerate('January February March April May June July August September October November December'.split(),1)}
NAMES={'leading':('Leading','LEI'),'coincident':('Coincident','CEI'),'lagging':('Lagging','LAG')}
OUT=ROOT/'data'/'economic_cycle.json'

HEADERS={'User-Agent':'Mozilla/5.0 (compatible; CFO-Macro-Dashboard/1.0)'}
def clean(s):return re.sub(r'\s+',' ',s).strip()
def monthperiod(m,y):
    i=MONTHS.get(m.lower())
    return f'{y}-{i:02d}' if i else None
def parse(html):
    soup=BeautifulSoup(html,'html.parser')
    text=clean(soup.get_text(' ',strip=True))
    start=text.find('Latest Press Release')
    if start<0:raise ValueError('Latest Press Release section not found')
    text=text[start:start+12500]
    dm=re.search(r'Updated:\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(20\d{2})',text,re.I)
    if not dm or dm[1].lower() not in MONTHS:raise ValueError('Official release date not found')
    published=f'{dm[3]}-{MONTHS[dm[1].lower()]:02d}-{int(dm[2]):02d}'
    found={}
    for key,(word,abbr) in NAMES.items():
        # Match the exact official index, month, level and signed monthly change.
        p=(r'The Conference Board\s+'+word+r' Economic Index.{0,30}?\('+abbr+r'\)\s+for the US\s+'
           r'(decreased|increased|rose|fell|declined|dropped|advanced|edged up|edged down)\s+'
           r'(?:slightly\s+)?(?:by\s+)?(\d+(?:\.\d+)?)\s*%\s+in\s+([A-Za-z]+)\s+(20\d{2})\s+to\s+(\d+(?:\.\d+)?)')
        m=re.search(p,text,re.I)
        if not m:continue
        period=monthperiod(m[3],m[4])
        if not period or period>published[:7]:continue
        value=float(m[5]);change=float(m[2])
        if m[1].lower() in ('decreased','fell','declined','dropped','edged down'):change=-change
        if not 20<value<300 or abs(change)>10:continue
        found[key]={'period':period,'value':value,'mom':change,'source':'The Conference Board','url':URL,'published_at':published}
    return found,published,soup,text
def note_link(soup):
    # Technical Notes are normally a publicly linked PDF, but the link is optional.
    for a in soup.find_all('a',href=True):
        title=clean(a.get_text(' ',strip=True)).lower()
        href=a['href']
        if ('technical notes' in title or ('technical' in href.lower() and '.pdf' in href.lower())):
            u=urljoin(URL,href)
            if u.startswith('https://www.conference-board.org/') and '.pdf' in u.lower():return u
    return None
def main():
    prev=json.loads(OUT.read_text()) if OUT.exists() else {}
    stamp=datetime.now(timezone.utc).isoformat()
    indexes={'checked_at':stamp,'series':dict(prev.get('series',{})),'source_health':{},'latest_report_date':prev.get('latest_report_date')}
    try:
        response=requests.get(URL,headers=HEADERS,timeout=35);response.raise_for_status()
        found,published,soup,body=parse(response.text)
        if not found:raise ValueError('No complete index observations in latest official release')
        for key in NAMES:
            x=found.get(key)
            old=indexes['series'].get(key,{})
            if x and x['period']>=old.get('period',''):
                indexes['series'][key]=x
            indexes['source_health'][key]={'ok':bool(x),'error':None if x else 'Index not parsed from official release'}
        indexes['latest_report_date']=published
    except Exception as exc:
        for key in NAMES:indexes['source_health'][key]={'ok':False,'error':str(exc)[:180]}
    OUT.write_text(json.dumps(indexes,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
