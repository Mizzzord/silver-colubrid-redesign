import concurrent.futures
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs, urlencode

import requests
from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://silver-colubrid.ru'
CACHE = ROOT / 'source' / 'crawl'
CACHE.mkdir(exist_ok=True)
ASSETS = ROOT / 'dist' / 'assets' / 'original'
ASSETS.mkdir(parents=True, exist_ok=True)
session = requests.Session()
session.headers['User-Agent'] = 'SilverColubridRedesign/1.0 (public content migration)'

def normalize(url):
    p = urlsplit(urljoin(BASE, url))
    if p.netloc != 'silver-colubrid.ru': return None
    if re.search(r'^/(bitrix|ajax|personal|basket|order|auth|search|test|cabinet|include/ajax)', p.path): return None
    if p.path.endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.pdf', '.zip', '.doc', '.xlsx')): return None
    if 'compare.php' in p.path or 'indexStart' in p.path or '404.php' in p.path: return None
    q = {k: v for k, v in parse_qs(p.query).items() if k.startswith('PAGEN_')}
    return urlunsplit(('', '', p.path or '/', urlencode(q, doseq=True), ''))

def fetch(path):
    key = hashlib.sha256(path.encode()).hexdigest()[:20]
    fp = CACHE / (key + '.html')
    try:
        if fp.exists(): return path, 200, fp.read_text()
        response = session.get(BASE + path, timeout=35)
        if response.status_code == 200: fp.write_text(response.text)
        return path, response.status_code, response.text
    except requests.RequestException as error: return path, 0, str(error)

def clean(node):
    if not node: return ''
    s = BeautifulSoup(str(node), 'html.parser')
    for el in s.select('script,style,noscript,svg,form,input,button,select,iframe,.top-block-wrapper,.left_block,.order-block,.ask_a_question,.bottom_nav,.module-pagination,.pagination,.top_block,.soc-avt,.share,.detail-gallery-big-slider-thumbs'):
        el.decompose()
    for el in s.find_all(string=lambda t:isinstance(t, Comment)): el.extract()
    for el in list(s.find_all()):
        if el.name == 'img':
            src = el.get('data-src') or el.get('src')
            if not src or '/upload/' not in src: el.decompose();continue
            el.attrs={'src':urljoin(BASE,src),'alt':el.get('alt',''),'loading':'lazy'}
        elif el.name == 'a':
            href=el.get('href','')
            if href.startswith(('javascript:', '#')) or not href: el.unwrap();continue
            if href.startswith('/'): href=normalize(href) or urljoin(BASE,href)
            el.attrs={'href':href}
        elif el.name in ['h1','h2','h3','h4','h5','h6','p','ul','ol','li','strong','b','em','i','br','table','thead','tbody','tr','td','th','blockquote']:
            el.attrs={}
            if el.name=='h1':el.name='h2'
        elif el.name in ['meta','link','hr']: el.decompose()
        else: el.attrs={}
    return str(s)

def extract(path, html):
    s=BeautifulSoup(html,'html.parser')
    title=s.select_one('h1') or s.select_one('title')
    title=title.get_text(' ',strip=True) if title else path
    main=s.select_one('.right_block') or s.select_one('#content') or s.body or s
    result={'path':path,'title':title,'source':BASE+path,'html':clean(main)}
    prod=s.select_one('.catalog_detail [itemprop="sku"]')
    if prod:
        def meta(name):
            el=s.select_one('.catalog_detail [itemprop="'+name+'"]')
            return el.get('content') or el.get('href') or el.get_text(' ',strip=True) if el else ''
        images=list(dict.fromkeys([e.get('href') for e in s.select('.catalog_detail link[itemprop="image"]')]+[e.get('data-big') for e in s.select('.catalog_detail [data-big]')]))
        props=[]
        for prop in s.select('.product-info .properties .prop'):
            name=prop.select_one('.name'); value=prop.select_one('.value')
            if name and value:props.append([name.get_text(' ',strip=True),value.get_text(' ',strip=True)])
        if not props:
            props=[e.get_text(' ',strip=True) for e in s.select('.product-info .properties .property')]
        stock=s.select_one('.product-info .item-stock')
        result.update(kind='product',id=meta('sku'),category=meta('category'),price=meta('price'),description=meta('description'),images=[urljoin(BASE,x) for x in images if x],props=props,stock=stock.get_text(' ',strip=True) if stock else '',tabs=[{'id':e.get('id'),'html':clean(e)} for e in s.select('.tab-pane')])
        result['html']=''
    elif path.startswith('/catalog/'):
        result['kind']='category'
        text=s.select_one('.group_description_block') or s.select_one('.text_after_items') or s.select_one('.text_before_items')
        result['html']=clean(text)
    else: result['kind']='document'
    links={p for a in main.select('a[href]') if (p:=normalize(a['href']))}
    return result,links

def crawl():
    maps=json.loads((ROOT/'source/sitemaps.json').read_text())
    paths={normalize(u) for k,urls in maps.items() for u in urls if '#YEAR#' not in u}
    home=BeautifulSoup((ROOT/'source/pages/home.html').read_text(),'html.parser')
    paths.update(normalize(a['href']) for a in home.select('a[href]'))
    paths.update(['/help/warranty/','/include/licenses_detail','/include/politika-obrabotki-personalnykh-dannykh','/include/politika-ispolzovaniya-faylov-cookies'])
    paths.discard(None)
    done=set(); records={}; errors=[]
    for wave in range(5):
        batch=sorted(paths-done)
        if not batch:break
        print(f'Wave {wave+1}: {len(batch)} pages',flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for path,status,html in pool.map(fetch,batch):
                done.add(path)
                if status!=200:errors.append({'path':path,'status':status});continue
                record,links=extract(path,html)
                records[path]=record;paths.update(links)
                if len(done)%100==0:print(f'Collected {len(done)} pages',flush=True)
        (ROOT/'source/content.json').write_text(json.dumps(records,ensure_ascii=False))
        (ROOT/'source/reports/crawl.json').write_text(json.dumps({'visited':len(done),'errors':errors,'remaining':sorted(paths-done)},ensure_ascii=False,indent=2))
    print(f'Done: {len(records)} pages, {len(errors)} unavailable',flush=True)

if __name__=='__main__':crawl()
