"""Free-source economic cycle updater. Never fabricate observations."""
import csv, io, json, re, requests
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'economic_cycle.json'
SERIES={}  # No verified free machine-readable Conference Board LEI/CEI/LAG feeds yet.
def fetch(series):
    url=f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}'
    response=requests.get(url,timeout=25,headers={'User-Agent':'CFO-Macro-Dashboard/1.0'})
    response.raise_for_status()
    observations={}
    for row in csv.DictReader(io.StringIO(response.text)):
        date=row.get('observation_date') or row.get('DATE','')
        value=row.get(series,'')
        if re.fullmatch(r'20\d{2}-\d{2}-01',date) and re.fullmatch(r'-?\d+(?:\.\d+)?',value):
            observations[date[:7]]=float(value)
    return dict(sorted(observations.items())[-60:]),url
def main():
    previous=json.loads(OUT.read_text()) if OUT.exists() else {}
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'series':{},'source_health':{}}
    for name in ('leading','coincident','lagging'):
        result['source_health'][name]={'ok':False,'error':'No se ha validado una serie pública gratuita de The Conference Board; no se publican cifras sustitutas.'}
    for name,identifier in SERIES.items():
        try:
            history,url=fetch(identifier)
            if not history:raise ValueError('No observations returned by public source')
            latest=max(history)
            # Explicitly reject discontinued FRED series, rather than label stale data current.
            now=datetime.now(timezone.utc)
            months=(now.year-int(latest[:4]))*12+now.month-int(latest[5:])
            if months>4:raise ValueError(f'Public FRED series discontinued/stale (last: {latest})')
            result['series'][name]={'history':history,'period':latest,'value':history[latest],'source':f'FRED · {identifier}','url':url}
            result['source_health'][name]={'ok':True,'error':None}
        except Exception as exc:
            old=previous.get('series',{}).get(name)
            if old:result['series'][name]=old
            result['source_health'][name]={'ok':False,'error':str(exc)[:220]}
    for name in ('leading','coincident','lagging'):
        if name not in result['series'] and name in previous.get('series',{}):
            result['series'][name]=previous['series'][name]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
