"""Public economic-cycle component observations (not Conference Board contributions)."""
import csv,io,json,re,requests
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'cycle_components.json'
# FRED IDs are public series; unavailable/proprietary components intentionally have no proxy.
COMPONENTS={
'leading':[
('Manufacturing weekly hours','AWHMAN'),('Initial unemployment claims','ICSA'),
('Consumer goods and materials new orders',None),('Nondefense capital goods orders ex aircraft',None),
('ISM new orders','NAPMNOI'),('Residential building permits','PERMIT'),
('S&P 500','SP500'),('Leading Credit Index',None),
('10Y Treasury minus federal funds rate','T10YFF'),('Consumer expectations',None)],
'coincident':[
('Nonfarm payroll employment','PAYEMS'),('Personal income less transfers','W875RX1'),
('Industrial production','INDPRO'),('Manufacturing and trade sales','CMRMTSPL')],
'lagging':[
('Average duration of unemployment','UEMPMEAN'),('Inventories-to-sales ratio','ISRATIO'),
('Manufacturing unit labor costs',None),('Bank prime loan rate','MPRIME'),
('Commercial and industrial loans','BUSLOANS'),('Consumer credit to income ratio',None),
('CPI services inflation','CUSR0000SAS')]}
def read_series(series):
    url='https://fred.stlouisfed.org/graph/fredgraph.csv?id='+series
    r=requests.get(url,timeout=25,headers={'User-Agent':'CFO-Macro-Dashboard/1.0'})
    r.raise_for_status()
    vals=[]
    for row in csv.DictReader(io.StringIO(r.text)):
        d=row.get('observation_date') or row.get('DATE','')
        v=row.get(series,'')
        if re.fullmatch(r'20\d{2}-\d{2}-\d{2}',d) and re.fullmatch(r'-?\d+(?:\.\d+)?',v):
            vals.append((d,float(v)))
    if not vals:raise ValueError('No dated observations')
    vals.sort()
    return vals[-13:],url
def main():
    prior=json.loads(OUT.read_text()) if OUT.exists() else {}
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'groups':{}}
    for group,items in COMPONENTS.items():
        result['groups'][group]=[]
        old={x['name']:x for x in prior.get('groups',{}).get(group,[])}
        for name,series in items:
            item={'name':name,'series_id':series,'status':'unavailable','history':[]}
            if series:
                try:
                    observations,url=read_series(series)
                    latest=observations[-1][0]
                    now=datetime.now(timezone.utc)
                    months=(now.year-int(latest[:4]))*12+now.month-int(latest[5:7])
                    if months>4:raise ValueError('Source observation is stale')
                    item.update(status='ok',period=latest,value=observations[-1][1],history=observations,url=url)
                except Exception as e:
                    item.update(status='error',error=str(e)[:140])
                    if old.get(name,{}).get('status')=='ok':
                        item.update({k:v for k,v in old[name].items() if k in ('period','value','history','url')})
            result['groups'][group].append(item)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
