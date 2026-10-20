"""Read only explicitly dated US LEI/CEI/LAG observations from the public release."""
import json,re,requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'economic_cycle.json'
URL='https://www.conference-board.org/topics/us-leading-indicators/'
MONTHS={m:i for i,m in enumerate('January February March April May June July August September October November December'.split(),1)}
KEYS={'leading':'Leading','coincident':'Coincident','lagging':'Lagging'}
def parse_release(html):
    soup=BeautifulSoup(html,'html.parser')
    body=' '.join(soup.get_text(' ',strip=True).split())
    # Only parse the Latest Press Release block, never footer, archived releases or navigation.
    start=body.find('Latest Press Release')
    if start<0:raise ValueError('No latest press release section')
    body=body[start:start+13000]
    dates=re.search(r'Updated:\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(20\d{2})',body)
    if not dates or dates[1] not in MONTHS:raise ValueError('Missing dated publication')
    published=f'{dates[3]}-{MONTHS[dates[1]]:02d}-{int(dates[2]):02d}'
    results={}
    for key,word in KEYS.items():
        # Must be a US-specific index statement with an explicit reference month, year and index value.
        pattern=(r'The Conference Board '+word+r' Economic Index.{0,65}?\('+('LEI' if key=='leading' else 'CEI' if key=='coincident' else 'LAG')+r'\) for the US '
                 r'(decreased|increased|rose|fell|declined|dropped|advanced|edged up|edged down|remained unchanged|was unchanged|held steady) '
                 r'(?:by\s+)?(\d+(?:\.\d+)?)%?\s+in\s+([A-Za-z]+)\s+(20\d{2})\s+to\s+(\d+(?:\.\d+)?)')
        match=re.search(pattern,body,re.I)
        if not match:
            # No safe extraction for this index. Preserve previous observation.
            continue
        direction=match[1].lower()
        month=match[3]
        if month not in MONTHS:continue
        period=f'{match[4]}-{MONTHS[month]:02d}'
        value=float(match[5]);change=float(match[2])
        if direction in ('decreased','fell','declined','dropped','edged down'):change=-change
        if direction in ('remained unchanged','was unchanged','held steady'):change=0
        if not 20<value<300 or not -10<=change<=10:continue
        if period>published[:7]:continue
        results[key]={'value':value,'mom':change,'period':period,'published_at':published,'source':'The Conference Board','url':URL}
    return results,published
def main():
    previous=json.loads(OUT.read_text()) if OUT.exists() else {}
    now=datetime.now(timezone.utc).isoformat()
    result={'checked_at':now,'series':dict(previous.get('series',{})),'source_health':{}}
    try:
        response=requests.get(URL,headers={'User-Agent':'Mozilla/5.0 (compatible; CFO-Macro-Dashboard/1.0)'},timeout=35)
        response.raise_for_status()
        observations,published=parse_release(response.text)
        if not observations:raise ValueError('No complete US index observations found')
        for key,record in observations.items():
            old=result['series'].get(key,{})
            if record['period']>=old.get('period',''):
                history=dict(old.get('history',{}))
                history[record['period']]=record['value']
                record['history']=dict(sorted(history.items())[-60:])
                result['series'][key]={**old,**record}
        for key in KEYS:
            result['source_health'][key]={'ok':key in observations,'error':None if key in observations else 'No se pudo extraer del último informe'}
        result['latest_report_date']=published
    except Exception as exc:
        for key in KEYS:result['source_health'][key]={'ok':False,'error':str(exc)[:200]}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
