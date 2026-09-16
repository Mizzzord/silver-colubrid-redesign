import gzip
import html
import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from collect import clean

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
DATA=json.loads((ROOT/'source/prepared.json').read_text() if (ROOT/'source/prepared.json').exists() else gzip.decompress((ROOT/'source/prepared.json.gz').read_bytes() if (ROOT/'source/prepared.json.gz').exists() else b''.join(p.read_bytes() for p in sorted((ROOT/'source').glob('prepared.json.gz.part*')))))
LAYOUT=(ROOT/'src/layout.html').read_text()
ESC=lambda x:html.escape(str(x),quote=True)
SERVICES=[
 {'slug':'lite-suvenirnykh-izdeliy','title':'Литьё сувениров','subtitle':'Любая сложность. Настоящее мастерство.','summary':'Объёмные талисманы, сувениры и амулеты из цветных металлов — от небольших партий до оптовых поставок.','image':'/assets/banner-1.png','source':'/company/','lead':'Обладая современными технологиями, при помощи литья мы создаем талисманы любого уровня сложности в любых количествах с оптимальным соотношением цены и качества.','points':['Латунь, бронза и экологически чистые материалы','Талисманы, сувениры и амулеты любой сложности','Современные производственные технологии','Собственное производство в Костроме']},
 {'slug':'izgotovlenie-po-eskizam','title':'Изготовление по вашим эскизам','subtitle':'Ваша идея обретает форму.','summary':'Индивидуальная разработка дизайна и создание памятных сувениров по вашему заказу.','image':'/assets/banner-2.png','source':'/company/','lead':'Кроме стандартного ассортимента, с которым Вы можете ознакомиться в каталоге изделий, мы также активно работаем с индивидуальными заказами. В случае необходимости наши ювелиры могут воссоздать целую серию самобытных вещей — памятных сувениров.','points':['Работа по вашим эскизам','Индивидуальная разработка дизайна сувениров','Авторские серии памятных изделий','Подарки близким, коллегам и партнёрам']},
 {'slug':'optovye-postavki','title':'Оптовые поставки','subtitle':'Маленькие вещи. Большие возможности.','summary':'Сувениры для магазинов и торговых лавок. Заказы от 10 000 ₽, индивидуальные условия и доставка по России.','image':'/assets/banner-3.png','source':'/optovym-pokupatelyam','lead':'«Серебряный полоз» создает качественные, стильные и оригинальные сувениры как по собственным эскизам, так и по заказам оптовых покупателей. Мы непрестанно совершенствуем технологии производственного процесса, обеспечивая продукции высокое качество и уникальность.','points':['Минимальный заказ — от 10 000 рублей','Пересчёт розничных цен при оптовой покупке','Презенты и скидки оптовым клиентам','Доставка в любой регион Российской Федерации']}
]

def canonical(path):
    path=urlsplit(path).path
    return path if path=='/' else path.rstrip('/')+'/'

for slug in ['licenses_detail','politika-obrabotki-personalnykh-dannykh','politika-ispolzovaniya-faylov-cookies']:
    raw=BeautifulSoup((ROOT/'source/pages'/f'{slug}.html').read_text(),'html.parser')
    main=raw.select_one('.right_block') or raw.select_one('#content') or raw
    title=raw.select_one('h1') or raw.title
    DATA[f'/include/{slug}/']={'path':f'/include/{slug}/','kind':'document','title':title.get_text(' ',strip=True),'html':clean(main),'source':f'https://silver-colubrid.ru/include/{slug}.php'}

PRODUCTS=[v for v in DATA.values() if v['kind']=='product']
CAT_PATHS=['bulavochki','brelki','imennye_brelki','imennye_monety','izdeliya_iz_fanery','kolokolchiki','koshelkovye_oberegi','runy','krasnaya_nit','suvenirnye_monety_lite','suvenirnye_monety_shtampovanny','monetnye_zagotovki','obereg','oborudovanie_dlya_torgovli']
CATS=[DATA['/catalog/'+k+'/'] for k in CAT_PATHS]
for cat in CATS:
    cat['products']=[p for p in PRODUCTS if p['categoryPath']==cat['path']]
    cat['count']=len(cat['products'])
    cat['image']=next((p['images'][0] for p in cat['products'] if p['images']),'')
PAGES={}

def money(value):
    try:return f'{float(value):,.0f}'.replace(',',' ')+' ₽'
    except (ValueError,TypeError):return 'Цена по запросу'

def title_block(title,kicker='СЕРЕБРЯНЫЙ ПОЛОЗ',intro='',crumb=''):
    return f'<div class="page-intro"><nav class="breadcrumbs" aria-label="Хлебные крошки"><a href="/">Главная</a><span>/</span>{crumb}<span>{ESC(title)}</span></nav><span class="eyebrow">{kicker}</span><h1>{ESC(title)}</h1>{f"<p>{intro}</p>" if intro else ""}</div>'

def write_page(path,title,body,description=''):
    path=canonical(path)
    file=OUT/path.strip('/')/'index.html' if path!='/' else OUT/'index.html'
    file.parent.mkdir(parents=True,exist_ok=True)
    doc=LAYOUT.replace('{{title}}',ESC(title)).replace('{{description}}',ESC(description or title+' — Серебряный полоз. Производство сувенирной продукции в Костроме.')).replace('{{body}}',body)
    file.write_text(doc)
    PAGES[path]={'title':title,'file':str(file.relative_to(OUT))}

def collection_card(cat,index):
    return f'<a class="collection-card" href="{cat["path"]}"><span class="index">{index:02d} / {cat["count"]} ИЗДЕЛИЙ</span><img src="{cat["image"]}" alt="{ESC(cat["title"])}" loading="lazy" width="300" height="240"><h3>{ESC(cat["title"])}</h3><span class="circle-arrow" aria-hidden="true">↗</span></a>'

def service_rows():
    return ''.join(f'<a class="service-row" href="/services/{s["slug"]}/"><span class="index">0{i+1}</span><h3>{s["title"]}</h3><p>{s["summary"]}</p><span class="arrow" aria-hidden="true">↗</span></a>' for i,s in enumerate(SERVICES))

def article_card(article):
    s=BeautifulSoup(article['html'],'html.parser');img=s.select_one('img[src]')
    image=f'<img src="{img["src"]}" alt="{ESC(article["title"])}" loading="lazy">' if img else ''
    return f'<a class="article-card" href="{article["path"]}">{image}<span class="eyebrow">ИСТОРИИ ИЗДЕЛИЙ</span><h3>{ESC(article["title"])}</h3><span class="circle-arrow" aria-hidden="true">↗</span></a>'

def product_card(p):
    return f'<article class="product-card" data-product="{p["id"]}"><div class="product-picture"><a href="{p["path"]}"><img src="{p["images"][0] if p["images"] else "/assets/logo.png"}" alt="{ESC(p["title"])}" loading="lazy" width="350" height="350"></a><button class="favorite-button" data-favorite="{p["id"]}" aria-label="В избранное: {ESC(p["title"])}" aria-pressed="false">♡</button></div><div class="product-card-info"><span class="product-category">{ESC(p["category"])}</span><a href="{p["path"]}"><h3>{ESC(p["title"])}</h3></a><div class="product-card-bottom"><span>{money(p["price"])}</span><button class="add-small" data-add="{p["id"]}" aria-label="Добавить в корзину: {ESC(p["title"])}">+</button></div></div></article>'

def catalog(path,title,products):
    active=path if path!='/catalog/' else ''
    nav=f'<a href="/catalog/" class="{"active" if not active else ""}">Все изделия <span>{len(PRODUCTS)}</span></a>'
    nav+=''.join(f'<a href="{c["path"]}" class="{"active" if c["path"]==active else ""}">{ESC(c["title"])} <span>{c["count"]}</span></a>' for c in CATS)
    content=title_block(title,'КОЛЛЕКЦИЯ МАЛЕНЬКИХ СМЫСЛОВ',intro='Изделия из цветных металлов. Созданы в Костроме, чтобы дарить, хранить и передавать истории.')
    content+=f'<section class="catalog-layout" data-catalog="{active}"><aside class="catalog-sidebar"><h2>Коллекции</h2><nav aria-label="Категории каталога">{nav}</nav><a class="catalog-wholesale" href="/optovym-pokupatelyam/">Покупаете оптом?<br><strong>Начнём сотрудничество ↗</strong><span>Заказы от 10 000 ₽</span></a></aside><div class="catalog-main"><form class="catalog-controls" id="catalog-filters"><label class="catalog-search"><svg viewBox="0 0 24 24"><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></svg><input type="search" name="q" placeholder="Название, имя, символ…" aria-label="Поиск изделий"></label><label class="sort-control"><span>Сортировка</span><select name="sort" aria-label="Сортировать товары"><option value="default">По умолчанию</option><option value="price-asc">Сначала дешевле</option><option value="price-desc">Сначала дороже</option><option value="name">По названию</option></select></label></form><div class="catalog-result-info"><span id="result-count">{len(products)} изделий</span><span>Маленькие символы. Большие пожелания.</span></div><div class="product-grid" id="product-grid">'+''.join(product_card(p) for p in products[:24])+'</div><div id="catalog-pagination" class="catalog-pagination"></div><noscript><p>Все изделия категории:</p><ul>'+''.join(f'<li><a href="{p["path"]}">{ESC(p["title"])}</a> — {money(p["price"])}</li>' for p in products)+'</ul></noscript></div></section>'
    if path in DATA and DATA[path]['html']:content+='<section class="section prose category-copy">'+DATA[path]['html']+'</section>'
    write_page(path,title,content)

def document_body(p,extra=''):
    sidebar='<aside class="document-nav"><span class="eyebrow">ПОЛЕЗНО ЗНАТЬ</span>'+''.join(f'<a href="{u}">{t} ↗</a>' for u,t in [('/company/','О компании'),('/services/','Наши услуги'),('/help/','Как купить'),('/help/payment/','Оплата'),('/help/delivery/','Доставка'),('/help/warranty/','Гарантия'),('/info/faq/','Вопрос — ответ'),('/contacts/','Контакты')])+'</aside>'
    return title_block(p['title'])+f'<section class="document-layout">{sidebar}<article class="prose source-document">{p["html"]}{extra}</article></section>'

def accordion_document(path,filename,intro):
    source=BeautifulSoup((ROOT/'source/pages'/filename).read_text(),'html.parser')
    parts=[]
    for block in source.select('.right_block .item-accordion-wrapper'):
        heading=block.select_one('.accordion-head')
        body=block.select_one('.accordion-body')
        if heading and body:
            title=heading.get_text(' ',strip=True)
            parts.append(f'<details class="product-accordion"><summary>{ESC(title)}<span>+</span></summary><div class="prose">{clean(body)}</div></details>')
    body=title_block(DATA[path]['title'],intro)
    desc=source.select_one('.vacancy_desc')
    if desc:body+='<section class="section vacancy-intro prose">'+clean(desc)+'</section>'
    body+='<section class="section accordion-document">'+''.join(parts)+'</section>'
    if 'vacancy' in path:body+='<section class="section vacancy-apply"><h2>Нашли своё дело?</h2><p>Отправьте резюме или позвоните, чтобы узнать подробности.</p><a class="button green" href="mailto:silver_colubrid@mail.ru?subject=Резюме">Отправить резюме по email ↗</a><a class="text-link" href="tel:+79038039999">+7 (903) 803-99-99</a></section>'
    body+='<details class="section original-home"><summary>Дополнительная информация исходного раздела <span>+</span></summary><div class="prose">'+DATA[path]['html']+'</div></details>'
    write_page(path,DATA[path]['title'],body)

ARTICLES=[v for k,v in DATA.items() if k.startswith('/blog/stati/') and '?' not in k]
home=(ROOT/'src/home.html').read_text()
selected=[CATS[6],CATS[9],CATS[5],CATS[2]]
selected[0]['image']=DATA['/catalog/koshelkovye_oberegi/1204/']['images'][0]
home=home.replace('{{collections}}',''.join(collection_card(c,i+1) for i,c in enumerate(selected))).replace('{{services}}',service_rows()).replace('{{articles}}',''.join(article_card(p) for p in ARTICLES[:3]))
original=BeautifulSoup(DATA['/']['html'],'html.parser')
for im in original.select('img'):im.decompose()
home=home.replace('{{home_original}}',str(original))
write_page('/','Сувениры с характером',home,'Сувениры из латуни и бронзы. Собственное производство в Костроме с 2000 года. Каталог, литьё, изготовление по вашим эскизам и оптовые поставки.')

catalog('/catalog/','Вещи с характером',PRODUCTS)
for cat in CATS:catalog(cat['path'],cat['title'],cat['products'])

for p in PRODUCTS:
    props=''.join(f'<div><dt>{ESC(k)}</dt><dd>{ESC(v)}</dd></div>' for k,v in p['props'] if k or v)
    images=p['images'] or ['/assets/logo.png']
    thumbnails=''.join(f'<button data-gallery="{u}" class="gallery-thumb {"selected" if i==0 else ""}" aria-label="Фото {i+1}: {ESC(p["title"])}" aria-pressed="{"true" if i==0 else "false"}"><img src="{u}" alt="Ракурс {i+1}" loading="lazy"></button>' for i,u in enumerate(images))
    product=f'<nav class="breadcrumbs product-breadcrumbs" aria-label="Хлебные крошки"><a href="/">Главная</a><span>/</span><a href="/catalog/">Каталог</a><span>/</span><a href="{p["categoryPath"]}">{ESC(p["category"])}</a><span>/</span><span>{ESC(p["title"])}</span></nav><section class="product-detail" data-detail="{p["id"]}"><div class="product-gallery"><div class="main-product-image"><img id="main-product-photo" src="{images[0]}" alt="{ESC(p["title"])}" fetchpriority="high"></div><div class="gallery-thumbnails">{thumbnails}</div></div><div class="product-detail-info"><span class="eyebrow">{ESC(p["category"])}</span><h1>{ESC(p["title"])}</h1><div class="product-reference">Код товара: {p["id"]} <span>{ESC(p.get("article",""))}</span></div><div class="price-line"><strong>{money(p["price"])}</strong><span>/ шт.</span><span class="product-stock">{ESC(p["stock"])}</span></div><p class="product-description">{ESC(p["description"])}</p><div class="purchase-controls"><div class="quantity"><button type="button" data-quantity="-1" aria-label="Уменьшить количество">−</button><input id="product-quantity" aria-label="Количество" type="number" min="1" max="9999" value="1"><button type="button" data-quantity="1" aria-label="Увеличить количество">+</button></div><button class="button green" data-add="{p["id"]}" data-detail-add>В корзину <span>+</span></button><button class="favorite-button large" data-favorite="{p["id"]}" aria-label="В избранное: {ESC(p["title"])}" aria-pressed="false">♡</button></div><div class="product-extra-actions"><button data-compare="{p["id"]}">Добавить к сравнению</button><a href="/optovym-pokupatelyam/">Оптовые условия ↗</a></div><dl class="product-properties">{props}</dl><p class="price-notice">Цена действительна только для интернет-магазина и может отличаться от цен в розничных магазинах. Оптовые цены пересчитываются при заказе от 10 000 ₽.</p><a class="original-product-link" href="https://silver-colubrid.ru{p["path"]}" target="_blank" rel="noopener">Купить в действующем интернет-магазине ↗</a></div></section>'
    tabs=''.join(f'<details class="product-accordion" {"open" if i==0 else ""}><summary>{dict(desc="Описание",buy="Как купить",payment="Оплата",delivery="Доставка",custom_tab="Вакансии").get(t["id"],"Дополнительная информация")}<span>+</span></summary><div class="prose">{t["html"]}</div></details>' for i,t in enumerate(p['tabs']))
    if len(p['description'])>240:
        short=p['description'][:220].rsplit(' ',1)[0]+'…'
        product=product.replace('<p class="product-description">'+ESC(p['description'])+'</p>','<p class="product-description">'+ESC(short)+'</p><a href="#product-description" class="description-jump">Полное описание ↓</a>')
    product=product.replace('<dd></dd>','')
    product+='<section class="product-information">'+tabs+'</section>'
    product=product.replace('<section class="product-information">','<section class="product-information" id="product-description">')
    related=[r for r in PRODUCTS if r['categoryPath']==p['categoryPath'] and r['id']!=p['id']][:4]
    product+='<section class="section related"><div class="section-heading"><div><span class="eyebrow">В ТОЙ ЖЕ КОЛЛЕКЦИИ</span><h2>Ещё немного <em>смысла.</em></h2></div><a class="text-link" href="'+p['categoryPath']+'">Вся коллекция ↗</a></div><div class="product-grid">'+''.join(product_card(r) for r in related)+'</div></section>'
    schema={'@context':'https://schema.org','@type':'Product','name':p['title'],'description':p['description'],'sku':p['id'],'brand':{'@type':'Brand','name':'Серебряный полоз'}}
    if p['price']:schema['offers']={'@type':'Offer','priceCurrency':'RUB','price':p['price']}
    product+='<script type="application/ld+json">'+json.dumps(schema,ensure_ascii=False).replace('</','<\\/')+'</script>'
    write_page(p['path'],p['title'],product,p['description'])

for path,p in DATA.items():
    if p['kind']!='document' or '?' in path or path.startswith(('/upload/','/cart/')) or path=='/':continue
    if canonical(path) in PAGES:continue
    write_page(path,p['title'],document_body(p))

services=title_block('Сделаем вашу идею настоящей.','НАШИ УСЛУГИ','От авторского эскиза до серии готовых изделий. Производим сувениры из цветных металлов с 2000 года.')+'<section class="section services-index"><div class="service-rows">'+service_rows()+'</div></section>'
services+='<section class="service-wide-image"><img src="/assets/banner-1.png" alt="Литьё цветных металлов" loading="lazy"><div><span class="eyebrow">СОБСТВЕННОЕ ПРОИЗВОДСТВО</span><h2>Мастерство,<br>которое <em>чувствуется.</em></h2><p>Наши ювелиры создают сувениры по собственным эскизам и индивидуальным заказам. Работаем с латунью и бронзой.</p><a class="button light" href="/contacts/">Обсудить вашу задачу <span>↗</span></a></div></section>'
write_page('/services/','Наши услуги',services)
for i,s in enumerate(SERVICES):
    body=title_block(s['title'],f'УСЛУГА 0{i+1} / СЕРЕБРЯНЫЙ ПОЛОЗ',s['subtitle'],crumb='<a href="/services/">Услуги</a><span>/</span>')
    body+=f'<section class="service-detail"><div class="service-detail-image"><img src="{s["image"]}" alt="{ESC(s["title"])}" fetchpriority="high"></div><div class="service-detail-copy"><h2>{s["subtitle"]}</h2><p>{s["lead"]}</p><ul>'+''.join(f'<li>{p}</li>' for p in s['points'])+f'</ul><a class="button green" href="mailto:silver_colubrid@mail.ru?subject={s["title"]}">Обсудить заказ по email <span>↗</span></a><a class="service-phone" href="tel:+79607422636">+7 (960) 742-26-36</a></div></section>'
    body+='<section class="service-source section"><div class="section-heading"><div><span class="eyebrow">ПОДРОБНОСТИ СОТРУДНИЧЕСТВА</span><h2>От первого вопроса<br><em>до готового изделия.</em></h2></div></div><div class="prose">'+DATA[s['source']]['html']+'</div></section>'
    body+='<section class="section"><div class="section-heading"><h2>Другие возможности</h2></div><div class="service-rows">'+service_rows()+'</div></section>'
    write_page('/services/'+s['slug']+'/',s['title'],body,s['summary'])

company=title_block('Металл. Мастерство. Характер.','О КОМПАНИИ','Серебряный полоз — сувениры, в которых есть авторское начало.')+'<div class="company-band"><strong>2000</strong><span>С этого года создаём<br>маленькие вещи с большим смыслом.</span><img src="/assets/banner-1.png" alt="Производство сувениров" loading="lazy"></div>'
company+='<section class="document-layout"><aside class="document-nav"><span class="eyebrow">СЕРЕБРЯНЫЙ ПОЛОЗ</span><a href="/services/">Услуги ↗</a><a href="/company/reviews/">Отзывы ↗</a><a href="/company/vacancy/">Вакансии ↗</a><a href="/contacts/">Контакты ↗</a></aside><article class="prose">'+DATA['/company/']['html']+'</article></section>'
write_page('/company/','О компании',company)

contacts=title_block('Хорошие вещи начинаются с разговора.','КОНТАКТЫ')+'<section class="contact-grid"><div class="contact-primary"><a href="tel:+79607422636">+7 (960) 742-26-36</a><a href="mailto:silver_colubrid@mail.ru">silver_colubrid@mail.ru</a><p>Пн — Пт, с 9:00 до 18:00</p><a class="button green" href="mailto:silver_colubrid@mail.ru?subject=Вопрос%20о%20сотрудничестве">Написать нам <span>↗</span></a></div><div class="contact-address"><span class="eyebrow">ПРИЕЗЖАЙТЕ ЗНАКОМИТЬСЯ</span><h2>Кострома,<br>ул. Коммунаров, 40</h2><a class="text-link" href="https://yandex.ru/maps/?text=Кострома%20улица%20Коммунаров%2040" target="_blank" rel="noopener">Построить маршрут <span>↗</span></a></div></section><section class="section contact-details" id="details"><span class="eyebrow">КОНТАКТНАЯ ИНФОРМАЦИЯ И РЕКВИЗИТЫ</span><div class="prose">'+DATA['/contacts/']['html'].replace('загрузка карты...','')+'</div></section>'
write_page('/contacts/','Контакты',contacts)
write_page('/optovym-pokupatelyam/','Оптовым покупателям',document_body(DATA['/optovym-pokupatelyam']))
write_page('/blog/','Истории маленьких вещей',title_block('Истории маленьких вещей.','ЖУРНАЛ','Материалы, традиции и символы. Узнайте больше о вещах, которые выбираете.')+'<section class="section blog-list"><div class="journal-grid">'+''.join(article_card(a) for a in ARTICLES)+'</div></section>')
accordion_document('/company/vacancy/','company__vacancy.html','КОМАНДА, КОТОРАЯ СОЗДАЁТ')
accordion_document('/info/faq/','info__faq.html','ОТВЕТЫ НА ВАШИ ВОПРОСЫ')
write_page('/archive/services/','Дополнительные услуги — материалы исходного сайта',document_body(DATA['/services/']))

for slug,title,copy in [('basket','Ваша коллекция','Вещи, которые вы выбрали.'),('favorites','Близко к сердцу','Сохраните изделия, к которым хочется вернуться.'),('compare','Сравнение изделий','Детали, которые помогают выбрать.')]:
    body=title_block(title,'ЛИЧНЫЙ ВЫБОР',copy)+f'<section class="section selection-page" data-selection="{slug}"><div id="selection-content"><p>Загружаем ваш выбор…</p></div><noscript>Для работы с выбранными изделиями включите JavaScript. <a href="https://silver-colubrid.ru/basket/">Открыть корзину действующего магазина</a>.</noscript></section>'
    write_page('/'+slug+'/',title,body)

write_page('/404/','Страница не найдена',title_block('Кажется, этот символ ещё не найден.','404','Вернитесь в каталог — там много хороших вещей.')+'<div class="section"><a class="button green" href="/catalog/">Открыть каталог ↗</a></div>')
(OUT/'404.html').write_text((OUT/'404/index.html').read_text())

site_map=title_block('Карта сайта.','ВСЕ РАЗДЕЛЫ')+'<section class="section sitemap-list"><h2>Каталог изделий</h2><ul>'+''.join(f'<li><a href="{c["path"]}">{ESC(c["title"])} — {c["count"]} изделий</a></li>' for c in CATS)+'</ul><h2>Услуги</h2><ul>'+''.join(f'<li><a href="/services/{s["slug"]}/">{s["title"]}</a></li>' for s in SERVICES)+'</ul><h2>Информация</h2><ul>'+''.join(f'<li><a href="{path}">{ESC(p["title"])}</a></li>' for path,p in PAGES.items() if not path.startswith(('/catalog/','/services/')) and path not in ['/404/','/basket/','/favorites/','/compare/'])+'</ul></section>'
write_page('/sitemap/','Карта сайта',site_map)

summaries=[{k:p[k] for k in ['id','path','title','category','categoryPath','price','description','images','props','stock']} for p in PRODUCTS]
(OUT/'catalog.json').write_text(json.dumps(summaries,ensure_ascii=False,separators=(',',':')))
(ROOT/'source/reports/pages.json').write_text(json.dumps(PAGES,ensure_ascii=False,indent=2))
(ROOT/'source/reports/services.json').write_text(json.dumps(SERVICES,ensure_ascii=False,indent=2))
print(f'Built {len(PAGES)} pages, {len(PRODUCTS)} products, {len(CATS)} categories, {len(ARTICLES)} articles, {len(SERVICES)} services.')
