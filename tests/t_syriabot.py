"""اختبارات بوت سوريا بلا شبكة ولا تيليغرام: القارئات على صفحاتٍ محفوظة، والقواعد على بياناتٍ مصنوعة.
  python tests/t_syriabot.py            (من مجلّد البوت)
  python tests/t_syriabot.py --save     يحفظ نسخًا حيّة من صفحات المصادر في tests/fixtures (يحتاج الشبكة)"""
import copy, json, os, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import syriabot as sb

FX = HERE / 'fixtures'
fails = []


def check(name, cond, extra=''):
    print(('ok   ' if cond else 'FAIL ') + name, extra if not cond else '')
    if not cond:
        fails.append(name)


if '--save' in sys.argv:
    FX.mkdir(exist_ok=True)
    (FX / 'sp_currencies.html').write_text(sb.fetch('https://sp-today.com/currencies'), encoding='utf-8')
    (FX / 'sp_energy.html').write_text(sb.fetch('https://sp-today.com/energy'), encoding='utf-8')
    (FX / 'cbs.html').write_text(sb.fetch('https://cb.gov.sy/'), encoding='utf-8')
    print('saved'); sys.exit(0)

# ---------- القارئات على الصفحات المحفوظة
sp = sb.parse_sptoday((FX / 'sp_currencies.html').read_text(encoding='utf-8'), (FX / 'sp_energy.html').read_text(encoding='utf-8'))
check('sp-today: five currencies with buy <= sell', set(sp['market']) == {'USD', 'EUR', 'TRY', 'SAR', 'AED'} and all(v['buy'] <= v['sell'] for v in sp['market'].values()), sp['market'])
check('sp-today: USD in a sane range', 50 < sp['market']['USD']['sell'] < 1000)
check('sp-today: four fuel prices', set(sp['fuel']) == {'gasoline_95', 'gasoline_90', 'diesel', 'gas_home'} and sp['fuel']['gas_home'] > 500, sp['fuel'])
cb = sb.parse_cbs((FX / 'cbs.html').read_text(encoding='utf-8'))
check('central bank: date and USD, EUR', len(cb['date']) == 10 and cb['rates']['USD'] > 50 and 'EUR' in cb['rates'], cb)
try:
    sb.parse_cbs('<html>تغيّر الشكل</html>'); check('central bank: a changed page raises', False)
except RuntimeError:
    check('central bank: a changed page raises', True)
csv_lines = ['date,admin1,admin2,market,market_id,latitude,longitude,category,commodity,commodity_id,unit,priceflag,pricetype,currency,price,usdprice',
             '2026-10-15,Hama,Hama,Hama,1,0,0,cereals and tubers,Rice,1,KG,actual,Retail,SYP,120,0.8',
             '2026-11-15,Hama,Hama,Hama,1,0,0,cereals and tubers,Rice,1,KG,actual,Retail,SYP,132,0.9',
             '2026-11-15,Hama,Hama,Hama,1,0,0,miscellaneous food,Sugar,1,KG,actual,Retail,SYP,100,0.7',
             '2026-10-15,Hama,Hama,Hama,1,0,0,miscellaneous food,Sugar,1,KG,actual,Retail,SYP,110,0.7',
             '2026-11-15,Hama,Hama,Hama,1,0,0,"meat, fish and eggs",Eggs,1,30 pcs,actual,Retail,SYP,377,2',
             '2026-11-15,Hama,Hama,Hama,1,0,0,non-food,Dishwashing liquid,1,900 ML,actual,Retail,SYP,237,2',
             '2026-11-15,Hama,Hama,Masyaf,1,0,0,cereals and tubers,Rice,1,KG,actual,Retail,SYP,999,0.9',
             '2026-09-15,Hama,Hama,Hama,1,0,0,cereals and tubers,Rice,1,KG,actual,Retail,SYP,90,0.9']
months = sb.parse_wfp(csv_lines, 'Hama')
check('wfp: last two months of the city market only', sorted(months) == ['2026-10-15', '2026-11-15'] and months['2026-11-15']['Rice'][1] == 132)
cfg = {'city': 'حماة', 'lat': 35.13, 'lon': 36.75, 'bulletin_hour': 7, 'move_pct': 2}
bt = sb.basket_text({'months': months}, cfg)
check('basket: one item a line, grouped, units, rises and falls first',
      all(x in bt for x in ('🌾 <b>حبوب ونشويّات</b>\n• رزّ: <b>132</b>', '• بيض (30 بيضة): <b>377</b>', '• سائل جلي (900 مل): <b>237</b>',
                            '⬆️ <b>ارتفع عن الشهر السابق</b>\n• رزّ: 120 ← <b>132</b> (+10.0%)', '⬇️ <b>انخفض</b>\n• سكّر: 110 ← <b>100</b> (-9.1%)',
                            'تشرين الثاني 2026', 'الأسعار كلّها · 4 مادّة')) and bt.index('ارتفع') < bt.index('<blockquote expandable>') < bt.index('حبوب') < bt.index('</blockquote>')
      and bt.count('<blockquote') == bt.count('</blockquote>') == 1, bt)
many = {'2026-10-15': {f'Item{i}': ['KG', 100.0, 'non-food'] for i in range(9)}, '2026-11-15': {f'Item{i}': ['KG', 100.0 + 10 * (i + 1), 'non-food'] for i in range(9)}}
bm = sb.basket_text({'months': many}, cfg)
check('basket: at most six changes shown, the rest counted, biggest first', bm.count('←') == 6 and 'و3 أخرى في القائمة' in bm and bm.index('Item8: 100 ←') < bm.index('Item3: 100 ←'), bm[:600])

# ---------- القواعد
os.environ['SYRIABOT_NOW'] = '2026-12-01T10:00:00+03:00'


def data(**kw):
    d = {'lirascope': {'market': {'USD': {'buy': 150.0, 'sell': 151.0}, 'EUR': {'buy': 164.0, 'sell': 166.0}}, 'cbs': {'USD': 122.0, 'EUR': 134.0},
                       'gold_usd': {'21K': 100.0}, 'usdt_usd': 1.0},
         'sptoday': {'market': {'USD': {'buy': 150.0, 'sell': 151.0}}, 'fuel': {'gasoline_95': 195, 'gasoline_90': 185, 'diesel': 150, 'gas_home': 1600}},
         'cbs': {'date': '2026-11-30', 'rates': {'USD': 122.0, 'EUR': 134.0}},
         'sytra': {'fuel': {'bulletin_date': '2026-11-15', 'prices': {'gasoline_95': 195, 'gasoline_90': 185, 'diesel_1': 150, 'diesel_heating': 115, 'gas_home': 1600}},
                   'bread': {'price': 40, 'since': '2026-06-20'}, 'gold': {'g21_sell': 15700, 'g21_buy': 15400, 'date': '2026-11-30'}},
         'weather': {'now': 20, 'days': [{'date': '2026-12-01', 'max': 18, 'min': 7, 'rain': 3.2, 'prob': 80, 'code': 61}, {'date': '2026-12-02', 'max': 16, 'min': 6, 'rain': 0, 'prob': 10, 'code': 2}]},
         'prayer': {'date': '2026-12-01', 'Fajr': '05:52', 'Sunrise': '07:20', 'Dhuhr': '12:22', 'Asr': '15:03', 'Maghrib': '17:20', 'Isha': '18:45'}}
    d = copy.deepcopy(d)
    for k, v in kw.items():
        d[k] = v
    return d


def step(state, d, first=False):
    alerts = []
    sb.rule_fuel(d, state, alerts, first)
    sb.rule_official(d, state, alerts, first)
    f = sb.build_facts(d, state)
    sb.rule_moves(f, state, alerts, first, cfg)
    return alerts, f


st = {}
a, f = step(st, data(), first=True)
check('first run: seeds everything, no alerts', a == [] and st['adopted']['gasoline_95']['value'] == 195 and st['official']['USD'] == 122.0 and st['ref']['market_usd'] == 151.0)
check('first run: single-source items are marked', st['adopted']['diesel_heating']['single'] and st['adopted']['bread']['single'] and not st['adopted']['diesel']['single'])
a, f = step(st, data())
check('no change: no alerts', a == [])
d = data(); d['sytra']['fuel']['prices']['diesel_1'] = 165
a, f = step(st, d)
check('one source changes: unconfirmed, value kept', len(a) == 1 and a[0].startswith('⚠️') and 'سيترا يذكر 165' in a[0] and st['adopted']['diesel']['value'] == 150, a)
a, f = step(st, d)
check('same disagreement again: not repeated', a == [])
d['sptoday']['fuel']['diesel'] = 165; d['sytra']['fuel']['bulletin_date'] = '2026-12-01'
a, f = step(st, d)
check('both sources agree: confirmed change', len(a) == 1 and a[0].startswith('🔔') and '150 ← 165' in a[0] and '+10.0%' in a[0] and st['adopted']['diesel']['value'] == 165 and 'diesel' not in st['pending'], a)
d2 = copy.deepcopy(d); d2['sptoday']['fuel']['gas_home'] = 1750; d2['sytra']['fuel']['prices']['gas_home'] = 1800
a, f = step(st, d2)
check('sources differ from each other and from the adopted: one unconfirmed with both', len(a) == 1 and 'سيترا يذكر 1,800' in a[0] and 'الليرة اليوم يذكر 1,750' in a[0] and st['adopted']['gas_home']['value'] == 1600, a)
a, f = step(st, d)
check('sources return to the adopted value: pending cleared silently', a == [] and 'gas_home' not in st['pending'])
d3 = copy.deepcopy(d); d3['sytra']['bread']['price'] = 50
a, f = step(st, d3)
check('single-source item changes: alert says one source', len(a) == 1 and 'ربطة الخبز' in a[0] and 'من مصدرٍ واحد' in a[0] and st['adopted']['bread']['value'] == 50, a)
d4 = copy.deepcopy(d3); del d4['sptoday']
a, f = step(st, d4)
check('second source missing and first unchanged: no alert', a == [])
d4['sytra']['fuel']['prices']['gasoline_95'] = 210
a, f = step(st, d4)
check('second source missing and first changes: unconfirmed, not adopted', len(a) == 1 and a[0].startswith('⚠️') and st['adopted']['gasoline_95']['value'] == 195, a)

d5 = copy.deepcopy(d3); d5['cbs'] = {'date': '2026-12-01', 'rates': {'USD': 123.5, 'EUR': 135.0}}
a, f = step(st, d5)
check('new official bulletin with a new rate: alert', len(a) == 1 and '122.00 ← 123.50' in a[0] and st['official']['date'] == '2026-12-01', a)
d5['cbs']['date'] = '2026-12-02'
a, f = step(st, d5)
check('new bulletin, same rate: no alert, date updated', a == [] and st['official']['date'] == '2026-12-02')
d6 = copy.deepcopy(d5); del d6['cbs']
a, f = step(st, d6)
check('bank site down: falls back to LiraScope copy of it, alert on its different rate', len(a) == 1 and st['official']['src'].startswith('ليراسكوب'), a)
st['official'] = {'date': '2026-12-02', 'USD': 123.5, 'EUR': 135.0, 'src': 'نشرة المصرف'}

d7 = copy.deepcopy(d5); d7['lirascope']['market']['USD'] = {'buy': 152.5, 'sell': 153.0}
a, f = step(st, d7)
check('market +1.3%: no alert', a == [])
d7['lirascope']['market']['USD'] = {'buy': 154.0, 'sell': 154.5}
a, f = step(st, d7)
check('market +2.3% from the reference: alert, reference moves', len(a) == 1 and 'ارتفع 2.3%' in a[0] and st['ref']['market_usd'] == 154.5, a)
a, f = step(st, d7)
check('same value: no second alert', a == [])
d7['lirascope']['market']['USD'] = {'buy': 150.0, 'sell': 150.5}
a, f = step(st, d7)
check('market falls 2.6%: alert says fell', len(a) == 1 and 'انخفض 2.6%' in a[0], a)
check('market differs from sp-today by >1%: both shown', f['market_alt'] is None)
d8 = copy.deepcopy(d7); d8['sptoday']['market']['USD'] = {'buy': 147.0, 'sell': 147.5}
a, f = step(st, d8)
bt = sb.board_text(f, cfg)
check('board shows the second source when they differ', f['market_alt'] and '«الليرة اليوم» تذكر الدولار 147.00 / 147.50' in bt)
d9 = copy.deepcopy(d7); del d9['lirascope']
a, f = step(st, d9)
check('LiraScope down: market comes from sp-today, labelled', f['market_src'] == 'الليرة اليوم' and f['usd_sell'] == 151.0)

a, f = step(st, d7)
bt = sb.board_text(f, cfg)
check('board has every section', all(x in bt for x in ('سوريا الآن · حماة', 'آخر تحديث 10:00 · الثلاثاء 1 كانون الأوّل', 'السوق', 'الرسميّ', 'الفجوة', 'الصاغة 15,400 / 15,700', 'بنزين 95: 195', 'تدفئة: 115*', 'طقس حماة', 'مطر 3.2 مم', 'الفجر 05:52')), bt)
check('board fits one Telegram message', len(bt) < 3500, len(bt))

# ---------- التشغيل كلّه بتيليغرام وهميّ ومصادر وهميّة
tmp = Path(tempfile.mkdtemp())
shutil.copy(HERE.parent / 'config.json', tmp / 'config.json')
sb.BASE = tmp
cur = {'d': data(), 'down': set()}


def fake(name):
    def fn(c):
        if name in cur['down']:
            raise RuntimeError('down')
        return copy.deepcopy(cur['d'][name])
    return fn


sb.SOURCES = {k: fake(k) for k in sb.SOURCES}
sb.src_wfp = lambda c, known='': None if known else {'stamp': 's1', 'months': months}
sent = []


class FakeTG:
    def __init__(self, dry=None):
        self.next = 100

    def send(self, text, silent=False):
        self.next += 1; sent.append(('send', text, silent)); return self.next

    def board(self, state, text):
        b = state.setdefault('board', {})
        sent.append(('edit' if b.get('id') else 'new', text, True)); b.setdefault('id', 55); return True


sb.Telegram = FakeTG
os.environ['SYRIABOT_NOW'] = '2026-12-01T10:00:00+03:00'
sb.run()
check('first run: board, hello, basket; no bulletin, no alerts', [k for k, _, _ in sent] == ['new', 'send', 'send'] and 'بدأ بوت سوريا' in sent[1][1] and 'سلّة حماة' in sent[2][1], [k for k, _, _ in sent])
state = json.loads((tmp / 'state.json').read_text(encoding='utf-8'))
check('state saved: started, board id, today snapshot', state['started'] and state['board']['id'] == 55 and state['days']['2026-12-01']['usd_sell'] == 151.0 and state['bulletin'] == '2026-12-01')
sent.clear(); os.environ['SYRIABOT_NOW'] = '2026-12-01T11:00:00+03:00'; sb.run()
check('next hour: only a silent board edit', [k for k, _, _ in sent] == ['edit'])
sent.clear(); os.environ['SYRIABOT_NOW'] = '2026-12-02T06:10:00+03:00'; sb.run()
check('next day before 7: no bulletin yet', [k for k, _, _ in sent] == ['edit'])
cur['d']['lirascope']['market']['USD'] = {'buy': 151.5, 'sell': 152.0}
sent.clear(); os.environ['SYRIABOT_NOW'] = '2026-12-02T07:05:00+03:00'; sb.run()
bul = sent[-1][1] if sent else ''
check('07:05: bulletin once, with change since yesterday', [k for k, _, _ in sent] == ['edit', 'send'] and 'نشرة الأربعاء 2 كانون الأوّل' in bul and '152.00 (+0.7% عن أمس)' in bul and 'لا تغيّر في المحروقات' in bul and 'الشروق 07:20' in bul and 'غدًا' in bul, bul)
sent.clear(); os.environ['SYRIABOT_NOW'] = '2026-12-02T08:05:00+03:00'; sb.run()
check('08:05: no second bulletin', [k for k, _, _ in sent] == ['edit'])
cur['down'] = {'lirascope'}
for h in (9, 10):
    sent.clear(); os.environ['SYRIABOT_NOW'] = f'2026-12-02T{h:02d}:05:00+03:00'; sb.run()
check('source down twice: still silent, board uses the kept copy', [k for k, _, _ in sent] == ['edit'] and '151.50 / 152.00' in sent[0][1])
sent.clear(); os.environ['SYRIABOT_NOW'] = '2026-12-02T11:05:00+03:00'; sb.run()
check('third failure: one warning', [k for k, _, _ in sent] == ['edit', 'send'] and 'ليراسكوب' in sent[1][1] and sent[1][1].startswith('⚠️'))
sent.clear(); os.environ['SYRIABOT_NOW'] = '2026-12-02T12:05:00+03:00'; sb.run()
check('fourth failure: no repeat', [k for k, _, _ in sent] == ['edit'])
cur['down'] = set()
sent.clear(); os.environ['SYRIABOT_NOW'] = '2026-12-02T13:05:00+03:00'; sb.run()
check('source back: one recovery note', [k for k, _, _ in sent] == ['edit', 'send'] and sent[1][1].startswith('✅'))
months2 = dict(months, **{'2026-12-15': {'Rice': ['KG', 140.0, 'cereals and tubers']}})
sb.src_wfp = lambda c, known='': {'stamp': 's2', 'months': {k: months2[k] for k in sorted(months2)[-2:]}}
cur['d']['sytra']['fuel']['prices']['diesel_1'] = 170; cur['d']['sptoday']['fuel']['diesel'] = 170
sent.clear(); os.environ['SYRIABOT_NOW'] = '2026-12-03T07:30:00+03:00'; sb.run()
kinds = [k for k, _, _ in sent]
check('new month of the basket and a fuel change: alert + bulletin with basket and the change', kinds == ['edit', 'send', 'send'] and sent[1][1].startswith('🔔') and 'سلّة حماة' in sent[2][1] and 'المازوت 150 ← 170' in sent[2][1], kinds)
shutil.rmtree(tmp, ignore_errors=True)

print('\nFAILED: ' + ', '.join(fails) if fails else f'\nALL PASSED')
sys.exit(1 if fails else 0)
