import gzip
import concurrent.futures
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'source/content.json').read_text() if (ROOT/'source/content.json').exists() else gzip.decompress((ROOT/'source/content.json.gz').read_bytes() if (ROOT/'source/content.json.gz').exists() else b''.join(p.read_bytes() for p in sorted((ROOT/'source').glob('content.json.gz.part*')))))
for path,record in data.items():
    if record['kind']!='product':continue
    raw=ROOT/'source/crawl'/f'{hashlib.sha256(path.encode()).hexdigest()[:20]}.html'
    s=BeautifulSoup(raw.read_text(),'html.parser')
    props=[]
    for el in s.select('.properties__item'):
        k=el.select_one('.properties__title');v=el.select_one('.properties__value')
        if k and v:
            pair=[k.get_text(' ',strip=True),v.get_text(' ',strip=True)]
            if pair not in props:props.append(pair)
    record['props']=props
    record['article']=(s.select_one('.article') or s.new_tag('span')).get_text(' ',strip=True)
    record['categoryPath']='/'+'/'.join(path.strip('/').split('/')[:-1])+'/'
    for el in s.select('.product-detail-gallery [data-src]'):
        src=el.get('data-src','')
        if '/upload/iblock/' in src:
            u='https://silver-colubrid.ru'+src
            if u not in record['images']:record['images'].append(u)

urls=set()
for p in data.values():
    urls.update(p.get('images',[]))
    for section in [p.get('html','')]+[t['html'] for t in p.get('tabs',[])]:
        s=BeautifulSoup(section,'html.parser')
        urls.update(i['src'] for i in s.select('img[src]') if i['src'].startswith('https://silver-colubrid.ru/upload/'))

assets={};errors=[]
def download(u):
    ext=Path(urlsplit(u).path).suffix.lower()
    if ext not in ['.jpg','.jpeg','.png','.webp','.gif','.svg']:ext='.jpg'
    local='/assets/original/'+hashlib.sha256(u.encode()).hexdigest()[:20]+ext
    file=ROOT/'dist'/local.lstrip('/')
    if file.exists() and file.stat().st_size>0:return u,local,None
    try:
        response=requests.get(u,timeout=30)
        if response.status_code!=200:return u,None,response.status_code
        file.write_bytes(response.content);return u,local,None
    except requests.RequestException as e:return u,None,str(e)

print('Preparing',len(urls),'original images',flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    for idx,(url,path,error) in enumerate(pool.map(download,sorted(urls))):
        if error:errors.append({'url':url,'error':error})
        else:assets[url]=path
        if (idx+1)%150==0:print('Images:',idx+1,flush=True)
for p in data.values():
    p['images']=[assets.get(u,u) for u in p.get('images',[])]
    for u,path in assets.items():
        p['html']=p.get('html','').replace(u,path)
        for t in p.get('tabs',[]):t['html']=t['html'].replace(u,path)
(ROOT/'source/prepared.json').write_text(json.dumps(data,ensure_ascii=False))
(ROOT/'source/assets.json').write_text(json.dumps(assets,ensure_ascii=False,indent=2))
(ROOT/'source/reports/assets.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2))
print('Ready:',len(assets),'images.',len(errors),'errors.',flush=True)
