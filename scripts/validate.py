import gzip
import json
import re
from pathlib import Path
from urllib.parse import unquote,urlsplit
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
pages=json.loads((ROOT/'source/reports/pages.json').read_text())
products=json.loads((OUT/'catalog.json').read_text())
source=json.loads((ROOT/'source/prepared.json').read_text() if (ROOT/'source/prepared.json').exists() else gzip.decompress((ROOT/'source/prepared.json.gz').read_bytes() if (ROOT/'source/prepared.json.gz').exists() else b''.join(p.read_bytes() for p in sorted((ROOT/'source').glob('prepared.json.gz.part*')))))
errors=[]
for path,record in pages.items():
    file=OUT/record['file']
    s=BeautifulSoup(file.read_text(),'html.parser')
    if not s.select_one('h1'):errors.append([path,'missing h1'])
    if not s.title or not s.title.get_text(strip=True):errors.append([path,'missing title'])
    if '{{' in str(s):errors.append([path,'unfilled template'])
    for e in s.select('[src],a[href],link[href]'):
        url=e.get('src') or e.get('href')
        if url.startswith('/'):
            target=OUT/unquote(urlsplit(url).path).lstrip('/')
            if not target.exists():errors.append([path,'missing asset/link',url])
    for e in s.select('script[type="application/ld+json"]'):
        try:json.loads(e.string)
        except (ValueError,TypeError):errors.append([path,'invalid structured data'])
for product in products:
    old=source[product['path']]
    for field in ['title','price','description','props','images']:
        if product[field]!=old[field]:errors.append([product['path'],'changed source field',field])
    if not product['images']:errors.append([product['path'],'no images'])
    file=OUT/product['path'].strip('/')/'index.html'
    text=BeautifulSoup(file.read_text(),'html.parser').get_text(' ',strip=True)
    for key,value in product['props']:
        if key and key not in text:errors.append([product['path'],'missing property',key])
        if value and value not in text:errors.append([product['path'],'missing property value',value])
    for tab in old['tabs']:
        original=BeautifulSoup(tab['html'],'html.parser').get_text(' ',strip=True)
        normalize=lambda value:re.sub(r'\s+',' ',value).strip()
        if normalize(original) not in normalize(text):errors.append([product['path'],'missing source tab',tab['id']])
report={'pages':len(pages),'products':len(products),'unique_products':len({p['id'] for p in products}),'original_images':len(json.loads((ROOT/'source/assets.json').read_text())),'errors':errors}
(ROOT/'source/reports/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({**report,'errors':errors[:15]},ensure_ascii=False,indent=2))
raise SystemExit(bool(errors))
