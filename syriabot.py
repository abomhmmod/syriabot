#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بوت سوريا — المرحلة الأولى: الأرقام، واللوحة المثبّتة، ونشرة الصباح، وتنبيه التغيّر.

يعمل كلّ ساعة على GitHub Actions بمكتبة بايثون القياسيّة وحدها. يقرأ:
  السوق:     ليراسكوب (واجهته العامّة) ويقابله بصفحة «الليرة اليوم».
  الرسميّ:   موقع مصرف سورية المركزيّ.
  المحروقات والخبز والذهب: سيترا، وتُقابَل المحروقات بـ«الليرة اليوم».
  سلّة حماة: برنامج الأغذية العالميّ (HDX)، شهريّة.
  الطقس والمواقيت: Open-Meteo و AlAdhan بإحداثيّات المدينة.
ثمّ يحدّث لوحةً مثبّتة بصمت، ويرسل نشرةً واحدة في الصباح، وينبّه حين يتغيّر رقمٌ فعلًا.

  python syriabot.py                 فحص عاديّ (يحتاج TELEGRAM_TOKEN و TELEGRAM_CHAT_ID)
  python syriabot.py --dry DIR       بلا تيليغرام: يكتب الرسائل والحالة في DIR
  python syriabot.py --bulletin-now  يرسل نشرة الصباح الآن ولو أُرسلت اليوم
  python syriabot.py --basket-now    يرسل سلّة المدينة الآن
"""
import csv, html, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))                # ليُستورد news.py من مجلّد البوت أيًّا كانت طريقة التشغيل
TZ = timezone(timedelta(hours=3))            # سوريا على +3 طوال السنة منذ 2022
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/130.0 Safari/537.36', 'Accept-Language': 'ar'}
LS = 'https://lirascope.syria-cloud.sy/api/v1'
CURS = [('USD', '💵', 'الدولار'), ('EUR', '💶', 'اليورو'), ('TRY', '🇹🇷', 'الليرة التركيّة'),
        ('SAR', '🇸🇦', 'الريال'), ('AED', '🇦🇪', 'الدرهم')]
ITEMS = {  # المفتاح: (الاسم، الوحدة، مفتاحه في سيترا، هل له مصدرٌ ثانٍ في «الليرة اليوم»)
    'gasoline_95': ('بنزين 95', 'لليتر', 'gasoline_95', True),
    'gasoline_90': ('بنزين 90', 'لليتر', 'gasoline_90', True),
    'diesel': ('المازوت', 'لليتر', 'diesel_1', True),
    'diesel_heating': ('مازوت التدفئة', 'لليتر', 'diesel_heating', False),
    'gas_home': ('أسطوانة الغاز المنزليّ', 'للأسطوانة', 'gas_home', True),
    'bread': ('ربطة الخبز', 'للربطة', None, False),
}
DAYS = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
MONTHS = ['كانون الثاني', 'شباط', 'آذار', 'نيسان', 'أيّار', 'حزيران', 'تمّوز', 'آب', 'أيلول', 'تشرين الأوّل',
          'تشرين الثاني', 'كانون الأوّل']
WMO = {0: 'صافٍ', 1: 'صافٍ غالبًا', 2: 'غائم جزئيًّا', 3: 'غائم', 45: 'ضباب', 48: 'ضباب', 51: 'رذاذ خفيف', 53: 'رذاذ',
       55: 'رذاذ غزير', 56: 'رذاذ متجمّد', 57: 'رذاذ متجمّد', 61: 'مطر خفيف', 63: 'مطر', 65: 'مطر غزير', 66: 'مطر متجمّد',
       67: 'مطر متجمّد', 71: 'ثلج خفيف', 73: 'ثلج', 75: 'ثلج غزير', 77: 'حبيبات ثلج', 80: 'زخّات خفيفة', 81: 'زخّات مطر',
       82: 'زخّات غزيرة', 85: 'زخّات ثلج', 86: 'زخّات ثلج', 95: 'عواصف رعديّة', 96: 'عواصف رعديّة وبَرَد',
       99: 'عواصف رعديّة وبَرَد'}
FOOD = {'Bread (bakery)': 'خبز الفرن', 'Bread (shop)': 'خبز المحلّات', 'Bulgur': 'برغل', 'Pasta (spaghetti)': 'معكرونة',
        'Noodles (instant, indomie)': 'إندومي', 'Potatoes': 'بطاطا', 'Rice': 'رزّ', 'Wheat flour': 'طحين', 'Eggs': 'بيض',
        'Fish (tuna, canned)': 'تونة معلّبة', 'Livestock (sheep, two-year-old male)': 'خروف بعمر سنتين',
        'Meat (beef, minced)': 'لحم عجل مفروم', 'Meat (chicken, legs)': 'أفخاذ فروج', 'Meat (chicken, plucked)': 'فروج منظّف',
        'Cheese': 'جبنة', 'Yogurt': 'لبن', 'Salt (iodised)': 'ملح', 'Sugar': 'سكّر', 'Bleach (chlorine)': 'كلور',
        'Diapers': 'حفاضات', 'Dishwashing liquid': 'سائل جلي', 'Fuel (diesel)': 'مازوت السوق',
        'Fuel (diesel, transport, parallel market)': 'مازوت النقل، السوق الموازية', 'Fuel (gas)': 'غاز السوق',
        'Fuel (gas, parallel market)': 'غاز السوق الموازية', 'Internet bundle': 'باقة إنترنت',
        'Multipurpose soap': 'صابون', 'Sanitary pads': 'فوط صحّيّة', 'Toothpaste': 'معجون أسنان',
        'Wage (non-qualified labour)': 'أجرة يوم العامل', 'Lentils': 'عدس', 'Oil (vegetable)': 'زيت نباتيّ',
        'Tomatoes': 'بندورة', 'Onions': 'بصل', 'Cucumbers': 'خيار', 'Milk': 'حليب', 'Tea': 'شاي', 'Chickpeas': 'حمّص',
        'Beans (white)': 'فاصولياء بيضاء', 'Ghee (vegetable)': 'سمن نباتيّ', 'Tomato paste': 'دبس بندورة',
        'Dates': 'تمر', 'Apples': 'تفّاح', 'Bananas': 'موز', 'Exchange rate (unofficial)': 'سعر الصرف (السوق)'}
FOOD.update({'Carrots': 'جزر', 'Eggplants': 'باذنجان', 'Oil': 'زيت', 'Parsley': 'بقدونس', 'Water (drinking)': 'ماء شرب',
             'Garlic': 'ثوم', 'Lemons': 'ليمون', 'Oranges': 'برتقال', 'Zucchini': 'كوسا', 'Peppers': 'فليفلة',
             'Cabbage': 'ملفوف', 'Lettuce': 'خسّ', 'Olive oil': 'زيت زيتون', 'Butter': 'زبدة', 'Coffee': 'قهوة'})
UNITS = {'KG': 'كغ', 'L': 'ليتر', 'Packet': 'علبة', 'Head': 'رأس', 'Day': 'يوم', 'Bar': 'قطعة', '30 pcs': '30 بيضة',
         '1 GB': '1 غيغا'}
UNIT_WORD = {'KG': 'كغ', 'G': 'غ', 'L': 'ليتر', 'ML': 'مل', 'PCS': 'قطعة', 'GB': 'غيغا'}
GROUPS = [('cereals and tubers', 'حبوب ونشويّات'), ('pulses and nuts', 'بقول'), ('meat, fish and eggs', 'لحوم وبيض'),
          ('milk and dairy', 'ألبان'), ('oil and fats', 'زيوت'), ('vegetables and fruits', 'خضار وفواكه'),
          ('miscellaneous food', 'سكّر وملح ومتفرّقات'), ('non-food', 'منظّفات ونظافة'), ('services', 'وقود وخدمات')]
GROUP_ICON = {'cereals and tubers': '🌾', 'pulses and nuts': '🫘', 'meat, fish and eggs': '🍗', 'milk and dairy': '🥛',
              'oil and fats': '🫒', 'vegetables and fruits': '🥬', 'miscellaneous food': '🧂', 'non-food': '🧴',
              'services': '⛽'}


def unit_ar(unit, item=''):
    """الوحدة بالعربيّة، وفارغةٌ للكيلو (هو الأصل في السلّة)."""
    if unit == 'KG' or (unit == 'Day' and item.startswith('Wage')):
        return ''
    if item == 'Parsley':
        return 'ربطة'
    if unit in UNITS:
        return UNITS[unit]
    m = re.fullmatch(r'([\d.]+)\s*([A-Za-z]+)', unit or '')
    return f'{m.group(1)} {UNIT_WORD.get(m.group(2).upper(), m.group(2))}' if m else (unit or '')
SRC_NAMES = {'lirascope': 'ليراسكوب', 'sptoday': 'الليرة اليوم', 'cbs': 'مصرف سورية المركزيّ', 'sytra': 'سيترا',
             'weather': 'الطقس', 'prayer': 'مواقيت الصلاة', 'wfp': 'برنامج الأغذية العالميّ'}


def now():
    fixed = os.environ.get('SYRIABOT_NOW')
    return datetime.fromisoformat(fixed).astimezone(TZ) if fixed else datetime.now(TZ)


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def save(path, data):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(path)


# ------------------------------------------------------------------ الجلب
def fetch(url, timeout=45, tries=3, raw=False):
    err = None
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
            if raw:                                  # الملفّ الكبير يُقرأ سطرًا سطرًا، ويغلقه من طلبه
                return r
            with r:
                return r.read().decode('utf-8', 'replace')
        except (urllib.error.URLError, OSError, ValueError) as ex:
            err = ex
            time.sleep(2 + 3 * i)
    raise RuntimeError(f'{urllib.parse.urlparse(url).netloc}: {type(err).__name__}: {str(err)[:120]}')


def jget(url):
    return json.loads(fetch(url))


def page_text(h):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>', ' ', h, flags=re.S)))


def num(s):
    return float(str(s).replace(',', '').strip())


# ------------------------------------------------------------------ المصادر
def src_lirascope(cfg):
    r = jget(LS + '/rates/latest')
    market = {x['currency']: {'buy': float(x['buy']), 'sell': float(x['sell']), 'at': x.get('timestampUtc', '')}
              for x in r.get('marketRates', []) if x.get('buy') and x.get('sell')}
    usd = market['USD']
    if not 0 < usd['buy'] <= usd['sell']:
        raise RuntimeError('lirascope: سعر الدولار غير معقول')
    cbs = {x['currency']: float(x['mid']) for x in r.get('cbsRates', []) if x.get('mid')}
    out = {'market': market, 'cbs': cbs}
    try:
        out['gold_usd'] = {x['type']: float(x['priceUSD']) for x in jget(LS + '/gold/latest')['data']}
    except Exception:
        out['gold_usd'] = {}
    try:
        out['usdt_usd'] = next(float(x['priceUSD']) for x in jget(LS + '/crypto/latest')['data'] if x['symbol'] == 'USDT')
    except Exception:
        out['usdt_usd'] = None
    return out


SP_FUEL = {'gasoline_95': r'بنزين 95 لكل لتر ([\d.,]+)', 'gasoline_90': r'بنزين 90 لكل لتر ([\d.,]+)',
           'diesel': r'مازوت لكل لتر ([\d.,]+)', 'gas_home': r'غاز لكل أسطوانة \(10 كيلو\) ([\d.,]+)'}


def parse_sptoday(currencies_html, energy_html):
    t, market = page_text(currencies_html), {}
    for code, _, _ in CURS:
        m = re.search(rf'{code} {code} [^\d]{{2,40}}?([\d.,]+) [\d.,]+ قديمة ([\d.,]+) ', t)
        if m:
            market[code] = {'buy': num(m.group(1)), 'sell': num(m.group(2))}
    e, fuel = page_text(energy_html), {}
    for k, pat in SP_FUEL.items():
        m = re.search(pat, e)
        if m:
            fuel[k] = num(m.group(1))
    if 'USD' not in market:
        raise RuntimeError('sp-today: لم يُقرأ سعر الدولار (تغيّر شكل الصفحة؟)')
    return {'market': market, 'fuel': fuel}


def src_sptoday(cfg):
    return parse_sptoday(fetch('https://sp-today.com/currencies'), fetch('https://sp-today.com/energy'))


def parse_cbs(h):
    d = re.search(r't-asof">[^<]*?(\d{4}-\d\d-\d\d)', h)
    rates = {c: num(v) for c, v in re.findall(r't-cur">([A-Z]{3})</span>\s*<span class="t-val">([\d.,]+)', h)}
    if not d or 'USD' not in rates:
        raise RuntimeError('cb.gov.sy: لم تُقرأ النشرة (تغيّر شكل الصفحة؟)')
    return {'date': d.group(1), 'rates': rates}


def src_cbs(cfg):
    return parse_cbs(fetch('https://cb.gov.sy/'))


def src_sytra(cfg):
    d = jget('https://sytra.me/api/v1/prices')['data']
    if not (d.get('fuel') or {}).get('prices'):
        raise RuntimeError('sytra: لا أسعار محروقات في الجواب')
    return d


def src_weather(cfg):
    q = urllib.parse.urlencode({'latitude': cfg['lat'], 'longitude': cfg['lon'], 'timezone': 'Asia/Damascus',
                                'forecast_days': 2, 'current': 'temperature_2m',
                                'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum,'
                                         'precipitation_probability_max,weather_code'})
    r = jget('https://api.open-meteo.com/v1/forecast?' + q)
    d = r['daily']
    return {'now': (r.get('current') or {}).get('temperature_2m'),
            'days': [{'date': d['time'][i], 'max': d['temperature_2m_max'][i], 'min': d['temperature_2m_min'][i],
                      'rain': d['precipitation_sum'][i], 'prob': d['precipitation_probability_max'][i],
                      'code': d['weather_code'][i]} for i in range(len(d['time']))]}


MASJIDAK = 'https://tv.masjidak.mow.gov.sy/api/main'
PRAYERS = ('Fajr', 'Sunrise', 'Dhuhr', 'Asr', 'Maghrib', 'Isha')


def add_min(hhmm, minutes):
    h, m = map(int, hhmm.split(':'))
    t = (h * 60 + m + int(minutes or 0)) % 1440
    return f'{t // 60:02d}:{t % 60:02d}'


def src_prayer(cfg):
    """المواقيت كما يحسبها تطبيق وزارة الأوقاف «مسجدك» لمسجدٍ بعينه: خدمة AlAdhan بإحداثيّات المسجد وبطريقة الحساب
    التلقائيّة للبلد (ما لم يحدّد المسجد طريقة)، ثمّ فروق الدقائق التي يضبطها المسجد في التطبيق إن وُجدت."""
    p = cfg.get('prayer') or {}
    lat, lon = p.get('lat', cfg['lat']), p.get('lon', cfg['lon'])
    q = {'latitude': lat, 'longitude': lon, 'timezonestring': 'Asia/Damascus'}
    if p.get('method'):
        q['method'] = p['method']
    r = jget(f"https://api.aladhan.com/v1/timings/{now():%d-%m-%Y}?" + urllib.parse.urlencode(q))['data']
    if abs(float(r['meta']['latitude']) - lat) > 0.5:
        raise RuntimeError('aladhan: أجاب عن موقعٍ آخر')
    off, iqama = {}, None
    if p.get('mosque_id'):
        try:
            s = jget(f"{MASJIDAK}/v1/mosques/prayerSettings?mosqueId={p['mosque_id']}")['prayerSettings']
            off, iqama = s.get('timeOffsets') or {}, s.get('iqamaWaitDurations')
        except Exception as ex:
            print(f'masjidak settings not read: {ex}', file=sys.stderr)
    return {'date': f'{now():%Y-%m-%d}', 'method': (r['meta'].get('method') or {}).get('name', ''), 'iqama': iqama,
            **{k: add_min(r['timings'][k][:5], off.get(k, 0)) for k in PRAYERS}}


HDX = 'https://data.humdata.org/api/3/action/package_show?id=wfp-food-prices-for-syrian-arab-republic'


def parse_wfp(lines, market):
    """آخر شهرين لسوق المدينة من ملفّ برنامج الأغذية العالميّ: {التاريخ: {المادّة: [الوحدة، السعر، الفئة]}}."""
    by = {}
    for r in csv.DictReader(lines):
        if r.get('market') == market and r.get('currency') == 'SYP' and r.get('price'):
            try:
                by.setdefault(r['date'], {})[r['commodity']] = [r['unit'], float(r['price']), r.get('category', '')]
            except ValueError:
                pass
    dates = sorted(by)[-2:]
    return {d: by[d] for d in dates}


def src_wfp(cfg, known=''):
    """لا يُنزَّل الملفّ (عشرات الميغابايتات) إلّا حين يتغيّر ختم البيانات في HDX."""
    res = jget(HDX)['result']
    stamp = res.get('dataset_date', '') + '|' + max((r.get('last_modified') or '' for r in res['resources']), default='')
    if stamp == known:
        return None
    url = next(r['url'] for r in res['resources'] if r['url'].endswith('.csv') and 'qc' not in r['name'].lower())
    with fetch(url, timeout=180, raw=True) as r:
        months = parse_wfp(io.TextIOWrapper(r, encoding='utf-8', errors='replace'), cfg.get('wfp_market', 'Hama'))
    if not months:
        raise RuntimeError('wfp: لا صفوف لسوق المدينة')
    return {'stamp': stamp, 'months': months}


SOURCES = {'lirascope': src_lirascope, 'sptoday': src_sptoday, 'cbs': src_cbs, 'sytra': src_sytra,
           'weather': src_weather, 'prayer': src_prayer}


# ------------------------------------------------------------------ التنسيق
def n(v, dec=None):
    if v is None:
        return '—'
    if dec is None:
        dec = 0 if abs(v - round(v)) < 0.005 else 2
    return f'{v:,.{dec}f}'


def pct(new, old):
    return f'{(new - old) / old * 100:+.1f}%' if old else ''


def day_title(d):
    return f'{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}'


def short(datestr):
    try:
        y, m, d = datestr[:10].split('-')
        return f'{int(d)}-{int(m)}'
    except ValueError:
        return datestr or '؟'


# ------------------------------------------------------------------ القواعد
def collect(cfg, state, alerts):
    """يجلب كلّ مصدر. ما تعذّر جلبه يُستعمل آخر ما حُفظ منه، ويُنبَّه بعد ثلاث ساعاتٍ متتالية من التعطّل."""
    cache, fail, data = state.setdefault('cache', {}), state.setdefault('fail', {}), {}
    for name, fn in SOURCES.items():
        try:
            data[name] = fn(cfg)
            cache[name] = {'at': now().isoformat(timespec='minutes'), 'data': data[name]}
            if fail.get(name, 0) >= 3:
                alerts.append(f'✅ عاد المصدر «{SRC_NAMES[name]}» يعمل.')
            fail[name] = 0
        except Exception as ex:
            fail[name] = fail.get(name, 0) + 1
            print(f'source {name} failed ({fail[name]}): {ex}', file=sys.stderr)
            if fail[name] == 3:
                alerts.append(f'⚠️ المصدر «{SRC_NAMES[name]}» لا يردّ منذ ثلاث ساعات. أعرض آخر ما قرأته منه، وسأخبرك حين يعود.')
            if name in cache:
                data[name] = cache[name]['data']
    return data


def rule_fuel(data, state, alerts, first):
    """المحروقات والخبز: يُعتمد الرقم حين يتّفق عليه المصدران. وإن اختلفا بقي المعتمد وأُرسل «غير مؤكَّد» مرّةً واحدة."""
    adopted, pending = state.setdefault('adopted', {}), state.setdefault('pending', {})
    sy, sp = data.get('sytra') or {}, (data.get('sptoday') or {}).get('fuel') or {}
    fuel, bread = sy.get('fuel') or {}, sy.get('bread') or {}
    today = f'{now():%Y-%m-%d}'
    ex = state.get('extracted') or {}
    for key, (name, unit, sykey, two) in ITEMS.items():
        a = bread.get('price') if key == 'bread' else (fuel.get('prices') or {}).get(sykey)
        date = bread.get('since') if key == 'bread' else fuel.get('bulletin_date')
        b = sp.get(key) if two else None
        a, b = (float(a) if a is not None else None), (float(b) if b is not None else None)
        cur = adopted.get(key)
        # الخبر الرسميّ أعلى من الموقعين: نشرةٌ أحدث من المعتمد، مستخرجة من خبرٍ ومتحقَّقٌ من نصّها، تُعتمد فورًا.
        nw = ex.get(key)
        if nw and cur and not first and nw['day'] > cur['date'] and abs(nw['value'] - cur['value']) >= 0.005:
            alerts.append(f'🔔 <b>تغيّر سعر {name}</b>\n{n(cur["value"])} ← {n(nw["value"])} ل.س {unit} ({pct(nw["value"], cur["value"])})\n'
                          f'عن <a href="{html.escape(nw["url"])}">{html.escape(nw["name"])}</a>:\n'
                          f'<blockquote>{html.escape(nw["quote"])}</blockquote>')
            adopted[key] = cur = {'value': nw['value'], 'date': nw['day'], 'single': True, 'src': nw['name'], 'news': nw['id']}
            pending.pop(key, None)
        if a is None and b is None:
            continue
        agreed = a if (a is not None and (not two or b is None or abs(a - b) < 0.005)) else None
        single = not two or a is None or b is None
        if cur is None or first:
            v = agreed if agreed is not None else (a if a is not None else b)
            adopted[key] = {'value': v, 'date': date or today, 'single': single or agreed is None}
            continue
        behind = bool(cur.get('news')) and (date or '') < cur['date']      # الموقعان ما زالا على النشرة السابقة
        if agreed is not None and abs(agreed - cur['value']) < 0.005:
            if behind:
                cur['single'] = single
            else:
                adopted[key] = {'value': cur['value'], 'date': date or cur['date'], 'single': single}
            pending.pop(key, None)
            continue
        if behind:
            continue
        if agreed is not None and not (two and b is None) and not (cur.get('news') and (date or '') <= cur['date']):
            # اتّفق المصدران، أو المادّة بمصدرٍ واحد أصلًا؛ ولا يُنقض خبرٌ رسميّ بنشرةٍ من اليوم نفسه عند الموقعين
            alerts.append(f'🔔 <b>تغيّر سعر {name}</b>\n{n(cur["value"])} ← {n(agreed)} ل.س {unit} ({pct(agreed, cur["value"])})\n'
                          + (f'من مصدرٍ واحد: سيترا (نشرة {short(date or today)}).' if not two else
                             f'اتّفق عليه سيترا و«الليرة اليوم» (نشرة {short(date or today)}).'))
            adopted[key] = {'value': agreed, 'date': date or today, 'single': not two}
            pending.pop(key, None)
            continue
        claims = [(s, v) for s, v in (('سيترا', a), ('الليرة اليوم', b)) if v is not None and abs(v - cur['value']) >= 0.005]
        sig = '|'.join(f'{s}={v}' for s, v in claims)
        if claims and pending.get(key) != sig:
            said = '، و'.join(f'{s} يذكر {n(v)}' for s, v in claims)
            why = f'وهو عن {cur["src"]}، فأبقيته حتّى يُحسم.' if cur.get('news') else f'لم يتّفق المصدران بعد، فأبقيت {n(cur["value"])}.'
            alerts.append(f'⚠️ <b>غير مؤكَّد: {name}</b>\n{said}، والمعتمد عندي {n(cur["value"])} ل.س {unit}.\n{why}')
            pending[key] = sig


def rule_gold(data, state):
    """نشرة الذهب: من الخبر الرسميّ الذي نقلها (رقمٌ مستخرج ومتحقَّق من نصّه) أو من سيترا، أيّهما أحدث. في اليوم
    الواحد يُقدَّم الخبر، إلّا إن تغيّر رقم سيترا بعد نشره (نشرةٌ ثانية في اليوم نفسه)."""
    sy, ex = (data.get('sytra') or {}).get('gold') or {}, state.get('extracted') or {}
    seen = state.setdefault('sytra_gold', {})
    g = None
    if sy.get('g21_sell'):
        sig = f"{sy.get('date')}|{sy['g21_sell']}|{sy.get('g21_buy')}"
        if seen.get('sig') != sig:
            seen.update(sig=sig, at=now().timestamp() if seen.get('sig') else 0)
        g = {'g21_sell': sy['g21_sell'], 'g21_buy': sy.get('g21_buy'), 'g18_sell': sy.get('g18_sell'), 'g18_buy': None,
             'date': sy.get('date') or '', 'src': 'سيترا'}
    nw = ex.get('gold21_sell')
    if nw and (g is None or nw['day'] > g['date'] or (nw['day'] == g['date'] and nw['ts'] >= seen.get('at', 0))):
        same = lambda k: ex[k]['value'] if k in ex and ex[k]['id'] == nw['id'] else None
        g = {'g21_sell': nw['value'], 'g21_buy': same('gold21_buy'), 'g18_sell': same('gold18_sell'), 'g18_buy': same('gold18_buy'),
             'date': nw['day'], 'src': nw['name'], 'url': nw['url'], 'quote': nw['quote']}
    state['gold'] = g
    return g or {}


def rule_official(data, state, alerts, first):
    cb, ls = data.get('cbs'), (data.get('lirascope') or {}).get('cbs') or {}
    old = state.get('official')
    if cb:
        new = {'date': cb['date'], 'USD': cb['rates']['USD'], 'EUR': cb['rates'].get('EUR'), 'src': 'نشرة المصرف'}
    elif ls.get('USD'):
        new = {'date': (old or {}).get('date', ''), 'USD': ls['USD'], 'EUR': ls.get('EUR'), 'src': 'ليراسكوب عن المصرف'}
    else:
        return
    if old and not first and abs(new['USD'] - old['USD']) >= 0.005:
        alerts.append(f'🔔 <b>نشرة المصرف المركزيّ {short(new["date"])}</b>\nالدولار الرسميّ {n(old["USD"], 2)} ← {n(new["USD"], 2)} '
                      f'({pct(new["USD"], old["USD"])})')
    state['official'] = new


def market_now(data):
    """سعر السوق: ليراسكوب أوّلًا، و«الليرة اليوم» إن غاب. وإن اختلفا في الدولار أكثر من 1% عُرض الاثنان."""
    ls, sp = (data.get('lirascope') or {}).get('market') or {}, (data.get('sptoday') or {}).get('market') or {}
    main, src = (ls, 'ليراسكوب') if 'USD' in ls else (sp, 'الليرة اليوم')
    alt = None
    if 'USD' in ls and 'USD' in sp and abs(ls['USD']['sell'] - sp['USD']['sell']) / ls['USD']['sell'] > 0.01:
        alt = sp['USD']
    return main, src, alt


def rule_moves(facts, state, alerts, first, cfg):
    """قفزة 2% أو أكثر في دولار السوق أو ذهب الصاغة، قياسًا بآخر قيمةٍ نُبّه عليها (أو بأوّل قيمة)."""
    ref = state.setdefault('ref', {})
    for key, label, val in (('market_usd', 'الدولار في السوق', facts.get('usd_sell')),
                            ('gold21', 'ذهب 21 (نشرة الصاغة)', facts.get('gold_assoc_sell'))):
        if not val:
            continue
        if key not in ref or first:
            ref[key] = val
            continue
        ch = (val - ref[key]) / ref[key]
        if abs(ch) >= cfg.get('move_pct', 2) / 100:
            alerts.append(f'🔔 <b>{label} {"ارتفع" if ch > 0 else "انخفض"} {abs(ch) * 100:.1f}%</b>\n'
                          f'{n(ref[key], 2 if val < 1000 else 0)} ← {n(val, 2 if val < 1000 else 0)} ل.س (مبيع)')
            ref[key] = val


def build_facts(data, state):
    main, msrc, alt = market_now(data)
    ls, sy = data.get('lirascope') or {}, data.get('sytra') or {}
    usd = main.get('USD') or {}
    gold = rule_gold(data, state)
    f = {'market': main, 'market_src': msrc, 'market_alt': alt, 'usd_sell': usd.get('sell'),
         'official': state.get('official'), 'adopted': state.get('adopted', {}),
         'gold_assoc_sell': gold.get('g21_sell'), 'gold_assoc_buy': gold.get('g21_buy'), 'gold_date': gold.get('date'),
         'gold_src': gold.get('src') if gold.get('url') else None, 'gold_url': gold.get('url'),
         'gold_market': (ls.get('gold_usd') or {}).get('21K') and usd.get('sell') and ls['gold_usd']['21K'] * usd['sell'],
         'usdt': ls.get('usdt_usd') and usd.get('sell') and ls['usdt_usd'] * usd['sell'],
         'weather': data.get('weather'), 'prayer': data.get('prayer'),
         'fuel_date': (sy.get('fuel') or {}).get('bulletin_date')}
    return f


def snapshot(f):
    s = {'usd_sell': f.get('usd_sell'), 'official_usd': (f.get('official') or {}).get('USD'),
         'gold': f.get('gold_assoc_sell')}
    s.update({k: v['value'] for k, v in (f.get('adopted') or {}).items()})
    return s


# ------------------------------------------------------------------ الرسائل
def weather_line(w, i=0):
    if not w or len(w.get('days', [])) <= i:
        return None
    d = w['days'][i]
    line = f'{n(d["max"], 0)}° / {n(d["min"], 0)}° · {WMO.get(d["code"], "متقلّب")}'
    if (d.get('rain') or 0) >= 0.5:
        line += f' · مطر {n(d["rain"], 0 if d["rain"] >= 10 else 1)} مم'
    elif (d.get('prob') or 0) >= 40:
        line += f' · احتمال مطر {d["prob"]}%'
    return line


def prayer_line(p, sunrise=False):
    if not p:
        return None
    keys = [('Fajr', 'الفجر'), ('Sunrise', 'الشروق'), ('Dhuhr', 'الظهر'), ('Asr', 'العصر'), ('Maghrib', 'المغرب'),
            ('Isha', 'العشاء')]
    return ' · '.join(f'{ar} {p[k]}' for k, ar in keys if sunrise or k != 'Sunrise')


def board_text(f, cfg):
    t, L = now(), []
    L.append(f'🇸🇾 <b>سوريا الآن · {cfg["city"]}</b>\nآخر تحديث {t:%H:%M} · {day_title(t)}')
    m = f['market']
    if m:
        rows = [f'{icon} {name} {n(m[c]["buy"], 2)} / {n(m[c]["sell"], 2)}' for c, icon, name in CURS if c in m]
        if f.get('usdt'):
            rows.append(f'🪙 تيثر USDT {n(f["usdt"], 2)}')      # يبدأ بالعربيّة حتّى لا ينقلب السطر إلى اليسار
        if f.get('market_alt'):
            rows.append(f'↔️ «الليرة اليوم» تذكر الدولار {n(f["market_alt"]["buy"], 2)} / {n(f["market_alt"]["sell"], 2)}')
        L.append(f'<b>السوق</b> (شراء / مبيع · {f["market_src"]})\n' + '\n'.join(rows))
    o = f.get('official')
    if o:
        row = f'💵 {n(o["USD"], 2)}' + (f' · 💶 {n(o["EUR"], 2)}' if o.get('EUR') else '')
        if f.get('usd_sell'):
            row += f' · الفجوة {pct(f["usd_sell"], o["USD"])}'
        L.append(f'<b>الرسميّ</b> ({o["src"]} {short(o["date"])})\n{row}')
    g = []
    if f.get('gold_assoc_sell'):
        tag = ' · '.join(x for x in (short(f['gold_date']) if f.get('gold_date') else '', f'<a href="{html.escape(f["gold_url"])}">{html.escape(f["gold_src"])}</a>' if f.get('gold_src') else '') if x)
        g.append(f'الصاغة {n(f.get("gold_assoc_buy"))} / {n(f["gold_assoc_sell"])}' + (f' ({tag})' if tag else ''))
    if f.get('gold_market'):
        g.append(f'محسوبًا من السوق {n(f["gold_market"], 0)}')
    if g:
        L.append('<b>الذهب</b> (غرام عيار 21)\n🥇 ' + ' · '.join(g))
    a = f['adopted']
    if a:
        v = lambda k: (n(a[k]['value']) + ('*' if a[k].get('single') else '')) if k in a else '—'
        rows = [f'⛽ بنزين 95: {v("gasoline_95")} · بنزين 90: {v("gasoline_90")}', f'🛢 مازوت: {v("diesel")} · تدفئة: {v("diesel_heating")}',
                f'🔥 غاز منزليّ: {v("gas_home")}', f'🍞 ربطة الخبز: {v("bread")}']
        L.append(f'<b>المحروقات والخبز</b>' + (f' (نشرة {short(f["fuel_date"])})' if f.get('fuel_date') else '') + '\n' + '\n'.join(rows))
    tail = []
    w = weather_line(f.get('weather'))
    if w:
        tail.append(f'🌤 <b>طقس {cfg["city"]}</b> {w}')
    p = prayer_line(f.get('prayer'))
    if p:
        tail.append(f'🕌 {p}')
    if tail:
        L.append('\n'.join(tail))
    mosque = (cfg.get('prayer') or {}).get('mosque')
    L.append('<i>الأسعار بالليرة الجديدة. * من مصدرٍ واحد.'
             + (f' المواقيت بحساب تطبيق «مسجدك» ل{mosque}.' if mosque and p else '') + '</i>')
    return '\n\n'.join(L)


def delta(cur, old, dec=None):
    if cur is None:
        return '—'
    if old is None or abs(cur - old) < 0.005:
        return f'{n(cur, dec)} (كأمس)' if old is not None else n(cur, dec)
    return f'{n(cur, dec)} ({pct(cur, old)} عن أمس)'


def basket_text(basket, cfg):
    months = basket.get('months') or {}
    dates = sorted(months)
    if not dates:
        return None
    cur, prev = months[dates[-1]], (months[dates[-2]] if len(dates) > 1 else {})
    up, down, by = [], [], {}
    for item, row in sorted(cur.items(), key=lambda x: FOOD.get(x[0], x[0])):
        unit, price, cat = row[0], row[1], (row[2] if len(row) > 2 else '')
        name, u = FOOD.get(item, item), unit_ar(unit, item)
        label = f'{name} ({u})' if u else name
        if cat == 'non-food' and re.match(r'Fuel|Internet|Wage|Water', item):
            cat = 'services'
        by.setdefault(cat if cat in dict(GROUPS) else 'miscellaneous food', []).append(f'• {label}: <b>{n(price, 0)}</b>')
        old = (prev.get(item) or [None, None])[1]
        if old and abs(price - old) / old >= cfg.get('basket_pct', 5) / 100:
            (up if price > old else down).append((abs(price - old) / old, f'• {name}: {n(old, 0)} ← <b>{n(price, 0)}</b> ({pct(price, old)})'))
    y, m, d = dates[-1].split('-')
    def top(rows, cap=6):                    # أكبر التغيّرات أوّلًا، والباقي عددًا
        rows = [s for _, s in sorted(rows, reverse=True)]
        return '\n'.join(rows[:cap]) + (f'\n<i>و{len(rows) - cap} أخرى في القائمة.</i>' if len(rows) > cap else '')

    # الرسالة قصيرة: ما تغيّر ظاهر، والأسعار كلّها في اقتباسٍ مطويّ يُفتح بضغطة (blockquote expandable).
    L = [f'🧺 <b>سلّة {cfg["city"]} · {MONTHS[int(m) - 1]} {y}</b>']
    if up:
        L.append('⬆️ <b>ارتفع عن الشهر السابق</b>\n' + top(up))
    if down:
        L.append('⬇️ <b>انخفض</b>\n' + top(down))
    if not up and not down and prev:
        L.append('↔️ لا تغيّر يُذكر عن الشهر السابق.')
    groups = [f'{icon} <b>{ar}</b>\n' + '\n'.join(by[k]) for k, ar, icon in ((k, ar, GROUP_ICON.get(k, '▫️')) for k, ar in GROUPS) if k in by]
    L.append(f'<blockquote expandable>📋 <b>الأسعار كلّها · {len(cur)} مادّة</b>\n<i>بالليرة الجديدة، وللكيلو ما لم تُذكر وحدة.</i>\n\n'
             + '\n\n'.join(groups) + '</blockquote>')
    L.append('<i>متوسّط ثلاثة باعة في سوق المدينة. المصدر: برنامج الأغذية العالميّ.</i>')
    return '\n\n'.join(L)


def bulletin_text(f, state, cfg, new_basket, digest=None):
    t = now()
    y = (state.get('days') or {}).get(f'{t - timedelta(days=1):%Y-%m-%d}') or {}
    a, L = f['adopted'], [f'☀️ <b>نشرة {day_title(t)}</b>']
    rows = []
    if f.get('usd_sell'):
        rows.append(f'💵 الدولار في السوق: {delta(f["usd_sell"], y.get("usd_sell"), 2)}')
    if f.get('official'):
        rows.append(f'🏛 الدولار الرسميّ: {delta(f["official"]["USD"], y.get("official_usd"), 2)}')
    if f.get('gold_assoc_sell'):
        rows.append(f'🥇 ذهب 21: {delta(f["gold_assoc_sell"], y.get("gold"))}')
    changed = [f'{ITEMS[k][0]} {n(y[k])} ← {n(v["value"])}' for k, v in a.items() if k in y and abs(v['value'] - y[k]) >= 0.005]
    rows.append('⛽ ' + ('تغيّر: ' + '، '.join(changed) if changed else 'لا تغيّر في المحروقات ولا الخبز.'))
    L.append('<b>الأسعار</b>\n' + '\n'.join(rows))
    w0, w1 = weather_line(f.get('weather'), 0), weather_line(f.get('weather'), 1)
    if w0:
        L.append(f'<b>طقس {cfg["city"]}</b>\nاليوم: {w0}' + (f'\nغدًا: {w1}' if w1 else ''))
    p = prayer_line(f.get('prayer'), sunrise=True)
    if p:
        L.append(f'<b>مواقيت {cfg["city"]}</b>\n{p}')
    # الموجز في اقتباسين مطويّين: يظهر أوّل كلٍّ منهما، ويُفتح الباقي بضغطة، فلا تطول النشرة.
    if digest and digest.get('hama'):
        L.append(f'📍 <b>يخصّ {cfg["city"]}</b>\n<blockquote expandable>' + '\n\n'.join(digest['hama']) + '</blockquote>')
    if digest and digest.get('general'):
        L.append('📰 <b>أهمّ ما صدر في سوريا</b>\n<blockquote expandable>' + '\n\n'.join(digest['general']) + '</blockquote>')
    if new_basket:
        b = basket_text(state.get('basket') or {}, cfg)
        if b:
            L.append(b)
    if state.get('pending'):
        L.append('⚠️ <b>لم يُحسم بعد:</b> ' + '، '.join(ITEMS[k][0] for k in state['pending']))
    return '\n\n'.join(L)


# ------------------------------------------------------------------ تيليغرام
class Telegram:
    def __init__(self, dry=None):
        self.dry = Path(dry) if dry else None
        self.token, self.chat = os.environ.get('TELEGRAM_TOKEN', ''), os.environ.get('TELEGRAM_CHAT_ID', '')
        self.count = 0
        if self.dry:
            self.dry.mkdir(parents=True, exist_ok=True)
        elif not (self.token and self.chat):
            raise SystemExit('السرّان TELEGRAM_TOKEN و TELEGRAM_CHAT_ID غير موجودين.')

    def call(self, method, payload):
        if self.dry:
            self.count += 1
            (self.dry / f'{self.count:02d}-{method}.txt').write_text(payload.get('text', json.dumps(payload, ensure_ascii=False)), encoding='utf-8')
            return {'ok': True, 'result': {'message_id': 1000 + self.count}}
        body = json.dumps(dict(payload, chat_id=self.chat)).encode()
        for i in range(3):
            try:
                req = urllib.request.Request(f'https://api.telegram.org/bot{self.token}/{method}', body, {'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=40) as r:
                    return json.load(r)
            except urllib.error.HTTPError as ex:
                try:
                    j = json.load(ex)
                except ValueError:
                    j = {'ok': False, 'description': f'HTTP {ex.code}'}
                if ex.code == 429 and i < 2:
                    time.sleep(int((j.get('parameters') or {}).get('retry_after', 5)) + 1)
                    continue
                return j
            except (urllib.error.URLError, OSError):
                time.sleep(4 + 4 * i)
        return {'ok': False, 'description': 'لا جواب من تيليغرام'}

    def send(self, text, silent=False):
        r = self.call('sendMessage', {'text': text, 'parse_mode': 'HTML', 'disable_notification': silent,
                                      'link_preview_options': {'is_disabled': True}})
        if not r.get('ok'):
            print('send failed:', r.get('description'), file=sys.stderr)
        return r['result']['message_id'] if r.get('ok') else None

    def board(self, state, text):
        """اللوحة رسالةٌ واحدة تُعدَّل في مكانها بلا إشعار. إن حُذفت أُرسلت من جديد وثُبّتت."""
        b = state.setdefault('board', {})
        if b.get('id'):
            r = self.call('editMessageText', {'message_id': b['id'], 'text': text, 'parse_mode': 'HTML',
                                              'link_preview_options': {'is_disabled': True}})
            d = (r.get('description') or '').lower()
            if r.get('ok') or 'not modified' in d:
                return True
            if not any(x in d for x in ('not found', "can't be edited", 'message_id_invalid')):
                print('board edit failed:', r.get('description'), file=sys.stderr)
                return False
        mid = self.send(text, silent=True)
        if not mid:
            return False
        b['id'] = mid
        self.call('pinChatMessage', {'message_id': mid, 'disable_notification': True})
        return True


# ------------------------------------------------------------------ التشغيل
def run(dry=None, bulletin_now=False, basket_now=False):
    cfg = load(BASE / 'config.json', {})
    state_path = (Path(dry) / 'state.json') if dry else BASE / 'state.json'
    state = load(state_path, None) if state_path.exists() else load(BASE / 'state.json', {}) if dry else {}
    state = state or {}
    tg = Telegram(dry)
    root = Path(dry) if dry else BASE                   # في التجربة يُكتب الأرشيف في مجلّدها لا في المستودع
    first = not state.get('started')
    alerts, t = [], now()
    data = collect(cfg, state, alerts)

    # الجامع الصامت: يحفظ ما نشرته المصادر الرسميّة في news/، ولا يخرج منه إلى المحادثة إلّا تنبيه المراسيم.
    # يسبق القواعد لتأخذ اللوحة أرقام أخبار هذه الساعة. تعطّله لا يمسّ اللوحة ولا الأسعار. أوّل تشغيلٍ له يملأ الأرشيف بلا تنبيه.
    try:
        import news
        srcs = load(BASE / 'sources.json', {})
        seeding = 'tg' not in state.get('news', {})
        got, nfail = news.collect(srcs, state.setdefault('news', {}), t.timestamp())
        added = news.store(root, got, cfg.get('keep_days', 60), t)
        decrees = news.decree_alerts(added, state['news'], t.year)
        if not seeding:
            alerts += decrees
        total = len(srcs.get('telegram', [])) + len(srcs.get('rss', []))
        print(f'news: {len(added)} new post(s) kept, {nfail} of {total} source(s) not read, {len(decrees)} decree alert(s)'
              + (' (first run: none sent)' if seeding else ''))
        # الأرقام التي أعلنتها الأخبار نفسها (نشرة الذهب، المحروقات، الخبز): تُستخرج ويُتحقَّق من نصّها، ثمّ تحكم القواعد.
        import extract
        rule_gold(data, state)                           # ليقيس المستخرِج رقم الذهب الجديد على الحاليّ
        facts_new = extract.run(root, state, added, t.timestamp())
        if facts_new:
            print('extract: ' + '، '.join(f'{f["key"]}={f["value"]:g} ({f["name"]} {f["day"]})' for f in facts_new))
    except Exception as ex:
        print(f'news collector failed: {type(ex).__name__}: {ex}', file=sys.stderr)

    rule_fuel(data, state, alerts, first)
    rule_official(data, state, alerts, first)
    facts = build_facts(data, state)
    rule_moves(facts, state, alerts, first, cfg)

    new_basket = False
    basket = state.setdefault('basket', {})
    if t.hour >= cfg.get('bulletin_hour', 7) and basket.get('checked') != f'{t:%Y-%m-%d}':
        try:
            got = src_wfp(cfg, basket.get('stamp', ''))
            if got:
                new_basket = bool(basket.get('months')) and max(got['months']) != max(basket['months'])
                basket.update(got)
            basket['checked'] = f'{t:%Y-%m-%d}'
            state['fail']['wfp'] = 0
        except Exception as ex:
            state['fail']['wfp'] = state['fail'].get('wfp', 0) + 1
            print(f'source wfp failed: {ex}', file=sys.stderr)

    ok = tg.board(state, board_text(facts, cfg))

    # الأدلّة (هواتف، جهات، سير، تطبيقات…): تُجلب مرّةً في اليوم إلى directory/ ليقرأها مستقبِل السؤال والجواب.
    if t.hour >= cfg.get('bulletin_hour', 7) and state.get('directory_day') != f'{t:%Y-%m-%d}':
        try:
            import directory
            print('directory:', directory.build(root))
            state['directory_day'] = f'{t:%Y-%m-%d}'
        except Exception as ex:
            print(f'directory failed: {type(ex).__name__}: {ex}', file=sys.stderr)

    if basket_now and not first:
        b = basket_text(basket, cfg)
        if b:
            tg.send(b, silent=True)
    if first and ok:
        tg.send('✅ <b>بدأ بوت سوريا.</b>\nاللوحة المثبّتة أعلى المحادثة تتحدّث كلّ ساعة بلا إشعار. تصلك نشرةٌ واحدة كلّ صباح، '
                'وتنبيهٌ حين يتغيّر سعرٌ فعلًا.')
        b = basket_text(basket, cfg)
        if b:
            tg.send(b, silent=True)
    if state.pop('run_failing', None):                  # يكتبها ملفّ التشغيل حين يفشل تشغيلٌ وينبّه
        tg.send('✅ عاد بوت سوريا يعمل.')
    for a in alerts:
        tg.send(a)
    today = f'{t:%Y-%m-%d}'
    if bulletin_now or (t.hour >= cfg.get('bulletin_hour', 7) and state.get('bulletin') != today and not first):
        dg = None
        try:
            import news
            dg = news.digest(root, cfg, t.timestamp())           # None بلا مفتاح Gemini أو عند تعذّره
        except Exception as ex:
            print(f'digest failed: {type(ex).__name__}: {ex}', file=sys.stderr)
        if tg.send(bulletin_text(facts, state, cfg, new_basket, dg)):
            state['bulletin'] = today
    elif first:
        state['bulletin'] = today                       # يوم البدء: اللوحة تكفي، والنشرة من الغد
    days = state.setdefault('days', {})
    days[today] = snapshot(facts)
    for d in sorted(days)[:-45]:
        del days[d]
    state['started'] = True
    state['last_run'] = t.isoformat(timespec='seconds')
    save(state_path, state)
    print(f'done: board {"ok" if ok else "FAILED"}, {len(alerts)} alert(s), sources failing: '
          f'{[k for k, v in state["fail"].items() if v] or "none"}')
    return 0 if ok else 1


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
    a = sys.argv[1:]
    sys.exit(run(dry=a[a.index('--dry') + 1] if '--dry' in a else None, bulletin_now='--bulletin-now' in a,
                 basket_now='--basket-now' in a))
