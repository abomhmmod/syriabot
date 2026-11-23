# -*- coding: utf-8 -*-
"""أدلّة بوت سوريا (المرحلة الثالثة): ما يحرّره الموقعان بأيديهما ولا مصدر آليًّا له. تُجلب مرّةً في اليوم وتُحفظ في
directory/<النوع>.jsonl، كلّ مدخلٍ سطر: {id, kind, source, title, text, url}. لا يُرسل منها شيء؛ يقرؤها مستقبِل السؤال
والجواب ليجيب عن «ما رقم…؟»، «من هو…؟»، «ما موقع…؟».

  المساحة السوريّة (syrian.zone): دليل الهاتف، التطبيقات الحكوميّة، الحسابات الرسميّة، السير الذاتيّة للمسؤولين، دليل
  المواقع، عدّاد الوعود. بياناتها مضمّنة في صفحاتها (data-page).
  سيترا (sytra.me، CC BY 4.0): دليل الجهات بمواقعها وهواتفها وحساباتها.

  python directory.py [DIR]     يبني الأدلّة في DIR (الأصل: مجلّد البوت) ويطبع عدد كلّ نوع
"""
import html, json, re, sys, urllib.parse, urllib.request
from pathlib import Path

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/130.0 Safari/537.36', 'Accept-Language': 'ar'}
SZ, TEXT_MAX = 'https://syrian.zone', 1400
SKIP_KEYS = re.compile(r'(^|_)(id|uuid|slug|image|images|icon|photo|logo|avatar|color|created|updated|deleted|order|sort|'
                       r'en|tr|lat|lng|latitude|longitude|wikidata|keywords|related|added|status_code)($|_)|_at$|_en$|_tr$')


def fetch(url, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def sz_props(path):
    m = re.search(r'data-page="([^"]+)"', fetch(SZ + path))
    if not m:
        raise RuntimeError(f'syrian.zone{path}: لا بيانات مضمّنة في الصفحة')
    return json.loads(html.unescape(m.group(1)))['props']


def clean(s):
    s = re.sub(r'<[^>]+>', ' ', html.unescape(str(s)))
    return re.sub(r'\s+', ' ', s).strip()


def flat(v, key='', out=None, links=None):
    """كلّ النصوص العربيّة والأرقام النافعة في مدخلٍ متشعّب، مع روابطه، بلا المعرّفات والصور والترجمات."""
    out = [] if out is None else out
    links = [] if links is None else links
    if isinstance(v, dict):
        for k, x in v.items():
            if not SKIP_KEYS.search(k):
                flat(x, k, out, links)
    elif isinstance(v, list):
        for x in v:
            flat(x, key, out, links)
    elif isinstance(v, str):
        s = clean(v)
        if s.startswith('http'):
            if not re.search(r'\.(webp|png|jpe?g|svg|gif)(\?|$)', s, re.I) and s not in links:
                links.append(s)
        elif s and s not in out and len(s) > 1 and re.search('[؀-ۿ0-9]', s) and not re.fullmatch(r'[a-z0-9_\-]+', s):
            out.append(s)                          # النصّ العربيّ والأرقام؛ الترجمات والرموز الداخليّة (in_office…) تُترك
    elif isinstance(v, (int, float)) and not isinstance(v, bool) and key and re.search(r'number|phone|year|count|total|percent', key):
        out.append(str(v))
    return out, links


def entry(kind, source, uid, title, text, url):
    return {'id': f'{kind}:{uid}', 'kind': kind, 'source': source, 'title': clean(title)[:160], 'text': clean(text)[:TEXT_MAX], 'url': url}


def generic(kind, source, rows, title_keys, page):
    out = []
    for i, r in enumerate(rows):
        title = next((r[k] for k in title_keys if r.get(k)), '') or ''
        parts, links = flat(r)
        text = ' · '.join(p for p in parts if p != clean(title))
        if links:
            text += ' · الروابط: ' + ' ، '.join(links[:6])
        if title:
            out.append(entry(kind, source, r.get('id', i), title, text, page))
    return out


def build_phonebook():
    d = sz_props('/phonebook')['initialData']
    return [entry('phone', 'دليل الهاتف · المساحة السوريّة', r['id'], f"{r['name_ar']} ({r['category_ar']})",
                  f"{r['category_ar']} · {r['name_ar']} · الرقم: {r['number']}" + (' · عليه واتساب' if r.get('is_whatsapp') else ''),
                  r.get('source_url') or SZ + '/phonebook') for r in d if r.get('number')]


def build_apps():
    return generic('app', 'دليل التطبيقات · المساحة السوريّة', sz_props('/govapps')['initialData'], ['name'], SZ + '/govapps')


def build_official():
    return generic('account', 'الحسابات الرسميّة · المساحة السوريّة', sz_props('/syofficial')['initialData'], ['name_ar', 'name'], SZ + '/syofficial')


def build_cvs():
    p = sz_props('/govtcvs')
    return generic('cv', 'السير الذاتيّة للمسؤولين · المساحة السوريّة', p['officials'], ['name_ar', 'name', 'full_name_ar', 'full_name'], SZ + '/govtcvs')


def build_sites():
    return generic('site', 'دليل المواقع · المساحة السوريّة', sz_props('/sites')['initialWebsites'], ['name_ar', 'name', 'title'], SZ + '/sites')


def build_promises():
    return generic('promise', 'عدّاد الوعود · المساحة السوريّة', sz_props('/promises')['promises'], ['title_ar', 'title', 'text_ar', 'text'], SZ + '/promises')


TYPES = {'ministry': 'وزارة', 'authority': 'هيئة أو مؤسّسة', 'governorate': 'محافظة', 'university': 'جامعة', 'embassy': 'بعثة في الخارج',
         'channel': 'وسيلة إعلام', 'site': 'موقع', 'app': 'تطبيق', 'minister': 'وزير', 'governor': 'محافظ', 'personality': 'شخصيّة', 'guide': 'دليل خدمة'}
SOCIAL = {'telegram': 'تيليغرام', 'facebook': 'فيسبوك', 'twitter': 'X', 'instagram': 'إنستغرام', 'youtube': 'يوتيوب'}


def build_entities():
    d = json.loads(fetch('https://sytra.me/downloads/entities.json'))
    rows = d if isinstance(d, list) else next(v for v in d.values() if isinstance(v, list))
    out = []
    for r in rows:
        parts = [TYPES.get(r.get('type'), r.get('type') or '')]
        if r.get('description_ar'):
            parts.append(r['description_ar'])
        if r.get('website'):
            parts.append('الموقع: ' + r['website'])
        if r.get('phones'):
            parts.append('الهاتف: ' + ' ، '.join(map(str, r['phones'])))
        if r.get('email'):
            parts.append('البريد: ' + r['email'])
        if r.get('address'):
            parts.append('العنوان: ' + r['address'])
        if r.get('city'):
            parts.append('المدينة: ' + str(r['city']))
        soc = [f'{ar}: {r["social"][k]}' for k, ar in SOCIAL.items() if (r.get('social') or {}).get(k)]
        if soc:
            parts.append(' ، '.join(soc))
        subs = [f"{s.get('name')}: {s.get('url')}" for s in (r.get('sub_sites') or [])[:6] if s.get('url') and 'اكتُشف آليًا' not in (s.get('note') or '')]
        if subs:
            parts.append('بوّابات تابعة: ' + ' ، '.join(subs))
        out.append(entry('entity', 'دليل الجهات · سيترا', r['slug'], r['name_ar'], ' · '.join(p for p in parts if p),
                         r.get('website') or 'https://sytra.me/search?q=' + urllib.request.quote(r['name_ar'])))
    return out


OSM_BOX = '35.075,36.680,35.205,36.840'              # مدينة حماة وأطرافها
OSM_KIND = {'hospital': 'مشفى', 'clinic': 'عيادة أو مركز صحّيّ', 'doctors': 'عيادة طبيب', 'dentist': 'عيادة أسنان', 'pharmacy': 'صيدليّة', 'laboratory': 'مخبر',
            'police': 'شرطة', 'fire_station': 'إطفاء ودفاع مدنيّ', 'ambulance_station': 'مركز إسعاف', 'post_office': 'بريد', 'bank': 'مصرف', 'courthouse': 'قصر عدليّ',
            'townhall': 'بلديّة', 'government': 'دائرة حكوميّة', 'public_building': 'مبنى حكوميّ', 'university': 'جامعة أو معهد', 'fuel': 'محطّة وقود', 'bus_station': 'كراج أو موقف'}
OSM_OLD = re.compile(r'الامن السياسي|الأمن السياسي|الامن العسكري|الأمن العسكري|امن الدول[ةه]|أمن الدول[ةه]|المخابرات|شعب[ةه] التجنيد|حزب البعث|شعب[ةه] الحزب|فرع الحزب|العسكري[ةه]$|قياد[ةه] موقع')


def km(a, b, c, d):
    """المسافة بالكيلومتر بين نقطتين (تقريب يكفي داخل مدينة)."""
    import math
    x = math.radians(d - b) * math.cos(math.radians((a + c) / 2))
    return 6371 * math.hypot(x, math.radians(c - a))


def build_hama():
    """مرافق مدينة حماة من الخريطة المفتوحة OpenStreetMap (ODbL): مشافٍ، عيادات، صيدليّات، شرطة، إطفاء، دوائر، مصارف…
    لكلّ مرفق نوعه وموقعه على الخريطة وبُعده عن مسجد الحيّ، وهاتفه إن كان مسجَّلًا. ثمّ ما في data/hama_services.json
    من أرقامٍ جُمعت من مصادر عامّة وتُحقّق من كلّ رقمٍ في صفحته."""
    base = Path(__file__).resolve().parent
    cfg = json.loads((base / 'config.json').read_text(encoding='utf-8'))
    home = cfg.get('prayer') or {}
    hlat, hlon, near = home.get('lat', cfg.get('lat')), home.get('lon', cfg.get('lon')), home.get('mosque') or 'وسط المدينة'
    q = (f'[out:json][timeout:60];(nwr["amenity"~"^(hospital|clinic|doctors|dentist|pharmacy|police|fire_station|post_office|bank|courthouse|townhall|public_building|university|fuel|bus_station)$"]({OSM_BOX});'
         f'nwr["office"="government"]({OSM_BOX});nwr["healthcare"="laboratory"]({OSM_BOX});nwr["emergency"="ambulance_station"]({OSM_BOX}););out center tags;')
    els, err = [], None
    for host in ('https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'):
        try:
            req = urllib.request.Request(host, urllib.parse.urlencode({'data': q}).encode(), UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                els = json.load(r)['elements']
            break
        except Exception as ex:
            err = ex
    snap = base / 'data' / 'osm_hama.json'                  # آخر نسخةٍ قُرئت: يُرجع إليها إن لم تُجب الخريطة
    if els:
        snap.parent.mkdir(exist_ok=True)
        snap.write_text(json.dumps(els, ensure_ascii=False), encoding='utf-8')
    elif snap.exists():
        els = json.loads(snap.read_text(encoding='utf-8'))
    else:
        raise RuntimeError(f'overpass: {type(err).__name__ if err else "لا عناصر"}')
    out = []
    for e in els:
        t = e.get('tags') or {}
        name = clean(t.get('name:ar') or t.get('name') or '')
        kind = OSM_KIND.get(t.get('amenity') or t.get('office') or t.get('healthcare') or t.get('emergency'))
        lat, lon = (e.get('lat') or (e.get('center') or {}).get('lat')), (e.get('lon') or (e.get('center') or {}).get('lon'))
        if not name or not kind or lat is None or OSM_OLD.search(name):
            continue
        parts = [kind + ' في مدينة حماة']
        addr = ' '.join(x for x in (t.get('addr:full'), t.get('addr:street'), t.get('addr:housenumber'), t.get('addr:suburb')) if x)
        if addr:
            parts.append('العنوان: ' + clean(addr))
        phone = t.get('phone') or t.get('contact:phone') or t.get('contact:mobile')
        if phone:
            parts.append('الهاتف: ' + clean(phone))
        if t.get('opening_hours'):
            parts.append('الدوام: ' + clean(t['opening_hours']))
        if t.get('healthcare:speciality') or t.get('description'):
            parts.append(clean(t.get('healthcare:speciality') or t.get('description'))[:120])
        if hlat is not None:
            d = km(hlat, hlon, lat, lon)
            parts.append(f'يبعد {d:.1f} كم عن {near}')
        parts.append(f'الموقع على الخريطة: https://www.google.com/maps?q={lat:.6f},{lon:.6f}')
        out.append(entry('hama', 'خريطة حماة · OpenStreetMap (قد لا تكون محدَّثة)', f"osm-{e['type'][0]}{e['id']}", f'{name} ({kind})', ' · '.join(parts),
                         f'https://www.openstreetmap.org/{e["type"]}/{e["id"]}'))
    extra = base / 'data' / 'hama_services.json'
    if extra.exists():                                    # أرقامٌ من مصادر عامّة، كلٌّ برابط صفحته
        for i, x in enumerate(json.loads(extra.read_text(encoding='utf-8'))):
            parts = [x.get('kind') or 'خدمة عامّة', *( ['الاختصاص: ' + x['specialty']] if x.get('specialty') else []),
                     'الهاتف: ' + ' ، '.join(x.get('phones') or []), *(['العنوان: ' + x['address']] if x.get('address') else []),
                     *([x['note']] if x.get('note') else []), *(['بتاريخ ' + x['page_date']] if x.get('page_date') else [])]
            out.append(entry('hama', 'دليل خدمات حماة · ' + (x.get('source_name') or 'مصدر عامّ'), f'web-{i}', x['name'], ' · '.join(parts), x['url']))
    return out


def build_sources():
    """المصادر التي يتابعها البوت نفسه (sources.json): لتُعرف الجهة وقناتها حين يُسأل عنها، لا عن أخبارها فقط."""
    s = json.loads((Path(__file__).resolve().parent / 'sources.json').read_text(encoding='utf-8'))
    out = []
    for x in s.get('telegram', []):
        text = (f"{x.get('kind') or 'جهة'} · قناتها على تيليغرام: https://t.me/{x['id']} (@{x['id']})" + (' · في محافظة حماة' if x.get('hama') else '')
                + (' · رسميّتها مرجَّحة من اسمها ووصفها، ولم تتأكّد من مصدرٍ ثانٍ' if x.get('unverified') else ' · قناة رسميّة')
                + ' · البوت يتابع ما تنشره')
        out.append(entry('source', 'مصادر البوت', 'tg-' + x['id'], x['name'], text, f"https://t.me/{x['id']}"))
    for x in s.get('rss', []):
        site = re.match(r'https?://[^/]+', x['url'])
        out.append(entry('source', 'مصادر البوت', 'rss-' + x['id'], x['name'], f"{x.get('kind') or 'إعلام'} · موقعه: {site.group(0) if site else x['url']} · البوت يتابع ما ينشره",
                         site.group(0) if site else x['url']))
    return out


BUILDERS = {'phone': build_phonebook, 'app': build_apps, 'account': build_official, 'cv': build_cvs, 'site': build_sites,
            'promise': build_promises, 'entity': build_entities, 'source': build_sources, 'hama': build_hama}


def build(base):
    """يبني كلّ دليل. دليلٌ تعذّر جلبه أو جاء فارغًا يبقى ملفّه السابق كما هو. يعيد {النوع: العدد أو نصّ الخطأ}."""
    d = Path(base) / 'directory'
    d.mkdir(parents=True, exist_ok=True)
    res = {}
    for kind, fn in BUILDERS.items():
        try:
            rows = fn()
            if not rows:
                raise RuntimeError('لا مداخل')
            (d / f'{kind}.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8', newline='\n')
            res[kind] = len(rows)
        except Exception as ex:
            res[kind] = f'{type(ex).__name__}: {str(ex)[:80]}'
    return res


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print(build(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent))
