"""اختبارات مستخرِج الأرقام من الأخبار بلا شبكة ولا نموذج: التحقّق الحرفيّ، والاتّساق، والطابور، ثمّ أثره في القواعد.
  python tests/t_extract.py           (من مجلّد البوت)"""
import copy, os, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ['SYRIABOT_NOW'] = '2026-12-01T12:00:00+03:00'
import extract, news
import syriabot as sb

fails = []


def check(name, cond, extra=''):
    print(('ok   ' if cond else 'FAIL ') + name, extra if not cond else '')
    if not cond:
        fails.append(name)


TS = 1796104800 + 2 * 3600                       # 2026-12-01 11:00 بتوقيت سوريا
GOLD_TEXT = ('دمشق-سانا\n‏ ‏\nارتفع سعر غرام الذهب عيار 21 قيراطاً في السوق السورية، بمقدار ‏200 ليرة ‏سورية، مقارنةً بسعره الذي سجّله أمس الأحد.‏\n'
             'ووفق النشرة الصادرة عن الهيئة العامة لإدارة ‏المعادن الثمينة ، اليوم الإثنين، ‏بلغ ‏سعر ‏غرام الذهب ‏عيار 21 قيراطاً 15900 ليرة سورية ‏للمبيع، ‏و15600 ليرة ‏للشراء. ‏ ‏\n'
             'وسجل غرام الذهب عيار 18 قيراطاً سعر 13650 ‏ليرة ‏سورية للمبيع، و13350 ‏ليرة للشراء. ‏ ‏')
FUEL_TEXT = ('دمشق-سانا\nأصدرت وزارة الطاقة نشرة أسعار المشتقات النفطية الجديدة.\n'
             'وحددت النشرة سعر ليتر البنزين أوكتان 95 بـ 205 ليرات، وليتر البنزين أوكتان 90 بـ 190 ليرة.\n'
             'وبلغ سعر ليتر المازوت 160 ليرة، وليتر مازوت التدفئة 120 ليرة، وأسطوانة الغاز المنزلي ١٬٧٠٠ ليرة.\n'
             'وكان سعر ليتر البنزين 95 قبل عام 120 ليرة، ويباع في لبنان بما يعادل 1.10 دولار.')


def item(i, title, text, tier=2, name='سانا', ts=TS):
    return {'id': f'rss:sana:{i}', 'src': 'sana', 'name': name, 'kind': 'إعلام', 'tier': tier, 'hama': False, 'ts': ts,
            'title': title, 'text': text, 'url': f'https://sana.sy/{i}'}


G = item(1, 'الذهب يرتفع 200 ليرة في السوق السورية', GOLD_TEXT)
F = item(2, 'الطاقة تصدر نشرة أسعار المحروقات الجديدة', FUEL_TEXT)
CUR = {'gold21_sell': 15700, 'gold21_buy': 15400, 'gold18_sell': 13500, 'gold18_buy': 13200, 'gasoline_95': 195, 'gasoline_90': 185,
       'diesel': 150, 'diesel_heating': 115, 'gas_home': 1600, 'bread': 40}
fact = lambda post, key, value, quote: {'post': post, 'key': key, 'value': value, 'quote': quote}
v = lambda f, items=(G, F), cur=CUR: extract.verify(f, list(items), cur)

# ---------- أدوات النصّ
check('flat: hidden direction marks and vowel marks go, digits unified', extract.flat('قيراطاً ‏١٥٩٠٠ ليرة') == 'قيراطا 15900 ليرة')
check('numbers: every reading of the separators', extract.numbers('15,900 و 15.900 و ١٥٬٩٠٠ و 1.10 و 200') >= {15900.0, 15.9, 1.1, 200.0})
check('candidate: official source, a commodity in the title, digits in the text', extract.is_candidate(G) and extract.is_candidate(F))
check('candidate: private paper, golden-seconds title, gas of another word are not', not extract.is_candidate(item(3, G['title'], GOLD_TEXT, tier=3))
      and not extract.is_candidate(item(4, 'خطة الثواني الذهبية لسلامتك على الطرق 100 متر', 'نصّ طويل فيه 100 متر وأرقام أخرى كثيرة 2026'))
      and not extract.is_candidate(item(5, 'وفد من غازي عنتاب يزور حلب', 'بحث الوفد 3 مشاريع مشتركة في المدينة الصناعية بحلب')))

# ---------- التحقّق الحرفيّ
ok, why = v(fact(1, 'gold21_sell', 15900, 'بلغ سعر غرام الذهب عيار 21 قيراطاً 15900 ليرة سورية للمبيع'))
check('gold 21 sell: accepted, quote kept, day and source carried', ok and ok['value'] == 15900 and ok['day'] == '2026-12-01' and ok['name'] == 'سانا' and '15900' in ok['quote'], why)
ok, why = v(fact(1, 'gold21_buy', 15600, 'و15600 ليرة للشراء.'))
check('gold 21 buy: a short clause is accepted because its sentence names carat 21', bool(ok), why)
ok, why = v(fact(1, 'gold18_buy', 13350, 'و13350 ليرة للشراء.'))
check('gold 18 buy: the sentence of carat 18 does not pass for carat 21', bool(ok) and not v(fact(1, 'gold21_buy', 13350, 'و13350 ليرة للشراء.'))[0], why)
ok, why = v(fact(1, 'gold21_sell', 15900, 'بلغ سعر غرام الذهب من عيار 21 قيراطاً 15900 ليرة للمبيع'))
check('a reworded quote is refused', ok is None and 'حرفيًّا' in why, why)
ok, why = v(fact(1, 'gold21_sell', 15950, 'بلغ سعر غرام الذهب عيار 21 قيراطاً 15900 ليرة سورية للمبيع'))
check('a number that is not in the quote is refused', ok is None and 'الرقم ليس' in why, why)
ok, why = v(fact(1, 'gold21_sell', 200, 'ارتفع سعر غرام الذهب عيار 21 قيراطاً في السوق السورية، بمقدار 200 ليرة سورية'))
check('the amount of the rise is refused (no sell word, far from the current price)', ok is None, why)
ok, why = v(fact(2, 'gasoline_95', 1.10, 'وكان سعر ليتر البنزين 95 قبل عام 120 ليرة، ويباع في لبنان بما يعادل 1.10 دولار.'))
check('a dollar price of another country is refused', ok is None, why)
ok, why = v(fact(2, 'gasoline_95', 2050, 'وحددت النشرة سعر ليتر البنزين أوكتان 95 بـ 2050 ليرات'), items=[G, dict(F, text=FUEL_TEXT.replace('205', '2050'))])
check('a price far from the current one (old lira, a typo) is refused by the range', ok is None and 'الهامش' in why, why)
ok, why = v(fact(2, 'gasoline_95', 120, 'وكان سعر ليتر البنزين 95 قبل عام 120 ليرة'))
check('the price of a year ago is refused though it is within the range', ok is None and 'سابق' in why, why)
T = item(6, 'الطاقة تعدّل سعر البنزين', 'دمشق-سانا\nحددت الوزارة سعر ليتر البنزين أوكتان 95 بـ 205 ليرات بعد أن كان 195 ليرة، وليتر البنزين 90 بـ 190 ليرة بدلاً من 185.\n'
         'وارتفع سعر ليتر المازوت من 150 إلى 160 ليرة.')
q1 = 'حددت الوزارة سعر ليتر البنزين أوكتان 95 بـ 205 ليرات بعد أن كان 195 ليرة، وليتر البنزين 90 بـ 190 ليرة بدلاً من 185.'
check('new price accepted, the old one in the same sentence refused («بعد أن كان», «بدلًا من», «من … إلى»)',
      v(fact(1, 'gasoline_95', 205, q1), items=[T])[0] and v(fact(1, 'gasoline_90', 190, q1), items=[T])[0]
      and v(fact(1, 'gasoline_95', 195, q1), items=[T])[0] is None and v(fact(1, 'gasoline_90', 185, q1), items=[T])[0] is None
      and v(fact(1, 'diesel', 160, 'وارتفع سعر ليتر المازوت من 150 إلى 160 ليرة.'), items=[T])[0]
      and v(fact(1, 'diesel', 150, 'وارتفع سعر ليتر المازوت من 150 إلى 160 ليرة.'), items=[T], cur=dict(CUR, diesel=155))[0] is None)
ok, why = v(fact(2, 'gas_home', 1700, 'وأسطوانة الغاز المنزلي ١٬٧٠٠ ليرة.'))
check('Arabic digits with a thousands mark are read', bool(ok) and ok['value'] == 1700, why)
ok, why = v(fact(2, 'diesel_heating', 120, 'وليتر مازوت التدفئة 120 ليرة'))
check('heating diesel accepted from its clause', bool(ok), why)
check('a post number out of range and an unknown key are refused', v(fact(9, 'diesel', 160, 'وبلغ سعر ليتر المازوت 160 ليرة'))[0] is None
      and v(fact(2, 'kerosene', 160, 'وبلغ سعر ليتر المازوت 160 ليرة'))[0] is None)
check('no current value to measure against: refused', v(fact(2, 'diesel', 160, 'وبلغ سعر ليتر المازوت 160 ليرة'), cur={})[0] is None)

# ---------- اتّساق أرقام الخبر الواحد
mk = lambda key, value, pid='p': {'key': key, 'value': value, 'id': pid, 'ts': TS, 'day': '2026-12-01', 'name': 'سانا', 'url': 'u', 'quote': 'q'}
good, bad = extract.consistent([mk('gold21_sell', 15900), mk('gold21_buy', 15600), mk('gold18_sell', 13650), mk('gold18_buy', 13350)], CUR)
check('consistent bulletin kept whole', len(good) == 4 and not bad)
good, bad = extract.consistent([mk('gold21_sell', 15600), mk('gold21_buy', 15900)], CUR)
check('buy above sell: both dropped', not good and len(bad) == 2)
good, bad = extract.consistent([mk('gold21_sell', 15900), mk('gold18_sell', 15600)], CUR)
check('carat 18 not near 18/21 of carat 21: gold dropped', not good and len(bad) == 2)
good, bad = extract.consistent([mk('gasoline_95', 185), mk('gasoline_90', 195), mk('gas_home', 1700)], CUR)
check('95 below 90: fuel dropped, gas kept', [f['key'] for f in good] == ['gas_home'] and len(bad) == 2)

# ---------- السؤال والطابور
ANS = {'facts': [fact(1, 'gold21_sell', 15900, 'بلغ سعر غرام الذهب عيار 21 قيراطاً 15900 ليرة سورية للمبيع'), fact(1, 'gold21_buy', 15600, 'و15600 ليرة للشراء.'),
                 fact(1, 'gold18_sell', 13650, 'وسجل غرام الذهب عيار 18 قيراطاً سعر 13650 ليرة سورية للمبيع'), fact(1, 'gold18_buy', 13350, 'و13350 ليرة للشراء.')]}
asked = []


def asker(*answers):
    it = iter(answers)

    def ask(prompt, model):
        asked.append(model)
        return next(it, None)
    return ask


facts = extract.extract([G], CUR, asker(ANS))
check('clean answer: four facts, one model asked', len(facts) == 4 and asked == [extract.MODELS[0]], asked)
asked.clear()
dirty = {'facts': ANS['facts'][:1] + [fact(1, 'gold21_buy', 15600, 'و 15600 ليرة سورية للشراء')]}
facts = extract.extract([G], CUR, asker(dirty, ANS))
check('a refused fact sends the question to the next model, verified ones are kept', len(facts) == 4 and asked == extract.MODELS[:2], asked)
asked.clear()
check('no model answers: None, to be asked again', extract.extract([G], CUR, asker()) is None and asked == extract.MODELS)
check('prompt carries the post text without hidden marks', True)

tmp = Path(tempfile.mkdtemp())
old = item(7, 'انخفاض سعر الذهب في السوق السورية', GOLD_TEXT.replace('15900', '15800').replace('15600', '15500'), ts=TS - 30 * 3600)
news.store(tmp, [old, G, item(8, 'افتتاح مركز صحي في حمص', 'افتتحت وزارة الصحة 3 مراكز صحية جديدة في محافظة حمص')], today=sb.now())
state = {'adopted': {k: {'value': CUR[k], 'date': '2026-11-15', 'single': False} for k in sb.ITEMS}, 'gold': {'g21_sell': 15700, 'g21_buy': 15400, 'g18_sell': 13500}}
asked.clear()
got = extract.run(tmp, state, [], TS + 600, ask=asker(None, None))
check('first run seeds the queue from the archive; model down keeps the queue', got == [] and state['extract']['queue'] == ['rss:sana:7', 'rss:sana:1'], state['extract'])
got = extract.run(tmp, state, [], TS + 4200, ask=asker(ANS if False else {'facts': [fact(2, 'gold21_sell', 15900, 'بلغ سعر غرام الذهب عيار 21 قيراطاً 15900 ليرة سورية للمبيع'),
                                                                               fact(2, 'gold21_buy', 15600, 'و15600 ليرة للشراء.'),
                                                                               fact(1, 'gold21_sell', 15800, 'بلغ سعر غرام الذهب عيار 21 قيراطاً 15800 ليرة سورية للمبيع')]}))
ex = state.get('extracted', {})
check('next run: queue answered and emptied, the newest post wins each key', len(got) == 3 and state['extract']['queue'] == [] and ex['gold21_sell']['value'] == 15900
      and ex['gold21_sell']['id'] == 'rss:sana:1' and ex['gold21_buy']['value'] == 15600, ex)
os.environ.pop('GEMINI_API_KEY', None)
check('nothing new and no key: no call', extract.run(tmp, state, [], TS + 7800) == [])
shutil.rmtree(tmp, ignore_errors=True)

# ---------- أثره في القواعد: الذهب
cfg = {'city': 'حماة', 'move_pct': 2}
D = {'lirascope': {'market': {'USD': {'buy': 150.0, 'sell': 151.0}}, 'cbs': {'USD': 122.0}, 'gold_usd': {}, 'usdt_usd': None},
     'sptoday': {'market': {'USD': {'buy': 150.0, 'sell': 151.0}}, 'fuel': {'gasoline_95': 195, 'gasoline_90': 185, 'diesel': 150, 'gas_home': 1600}},
     'sytra': {'fuel': {'bulletin_date': '2026-11-15', 'prices': {'gasoline_95': 195, 'gasoline_90': 185, 'diesel_1': 150, 'diesel_heating': 115, 'gas_home': 1600}},
               'bread': {'price': 40, 'since': '2026-06-20'}, 'gold': {'g21_sell': 15700, 'g21_buy': 15400, 'g18_sell': 13500, 'date': '2026-11-30'}}}


def step(st, d, first=False):
    alerts = []
    sb.rule_fuel(d, st, alerts, first)
    sb.rule_official(d, st, alerts, first)
    f = sb.build_facts(d, st)
    sb.rule_moves(f, st, alerts, first, cfg)
    return alerts, f


st = {}
a, f = step(st, D, first=True)
check('no news: gold from sytra, no source link', f['gold_assoc_sell'] == 15700 and f['gold_date'] == '2026-11-30' and f['gold_src'] is None)
nf = lambda key, value, day='2026-12-01', ts=TS, pid='rss:sana:1': {'value': value, 'quote': 'بلغ سعر غرام الذهب عيار 21 قيراطا 15900 ليرة سورية للمبيع', 'id': pid, 'ts': ts, 'day': day, 'name': 'سانا', 'url': 'https://sana.sy/1'}
st['extracted'] = {'gold21_sell': nf('gold21_sell', 15900), 'gold21_buy': nf('gold21_buy', 15600), 'gold18_sell': nf('gold18_sell', 13650, pid='other')}
a, f = step(st, D)
bt = sb.board_text(dict(f, weather=None, prayer=None), cfg)
check('news of a newer day: gold from the news with date and linked source, no alert under 2%', a == [] and f['gold_assoc_sell'] == 15900 and f['gold_assoc_buy'] == 15600
      and 'الصاغة 15,600 / 15,900 (1-12 · <a href="https://sana.sy/1">سانا</a>)' in bt and st['gold']['g18_sell'] is None, bt)
d2 = copy.deepcopy(D); d2['sytra']['gold'] = {'g21_sell': 15900, 'g21_buy': 15600, 'date': '2026-12-01'}
os.environ['SYRIABOT_NOW'] = '2026-12-01T13:00:00+03:00'
a, f = step(st, d2)
check('sytra catches up later the same day: sytra again, same price', f['gold_assoc_sell'] == 15900 and f['gold_src'] is None and a == [])
d3 = copy.deepcopy(D); d3['sytra']['gold'] = {'g21_sell': 16300, 'g21_buy': 16000, 'date': '2026-12-01'}
os.environ['SYRIABOT_NOW'] = '2026-12-01T15:00:00+03:00'
a, f = step(st, d3)
check('second bulletin of the day at sytra after the news: sytra wins, +2% alert', f['gold_assoc_sell'] == 16300 and len(a) == 1 and 'ذهب 21' in a[0], a)
st['extracted']['gold21_sell'] = nf('gold21_sell', 16500, ts=TS + 6 * 3600)
a, f = step(st, d3)
check('newer news after that: the news wins again', f['gold_assoc_sell'] == 16500 and f['gold_src'] == 'سانا')
d4 = copy.deepcopy(D); d4['sytra']['gold'] = {'g21_sell': 16400, 'g21_buy': 16100, 'date': '2026-12-02'}
a, f = step(st, d4)
check('sytra of a later day beats older news', f['gold_assoc_sell'] == 16400 and f['gold_src'] is None)

# ---------- أثره في القواعد: المحروقات والخبز
os.environ['SYRIABOT_NOW'] = '2026-12-01T12:00:00+03:00'
st = {}
step(st, D, first=True)
fq = {'value': 160.0, 'quote': 'وبلغ سعر ليتر المازوت 160 ليرة', 'id': 'rss:sana:2', 'ts': TS, 'day': '2026-12-01', 'name': 'سانا', 'url': 'https://sana.sy/2'}
st['extracted'] = {'diesel': fq}
a, f = step(st, D)
check('fuel in official news newer than the adopted bulletin: adopted at once, alert quotes the sentence and links the source',
      len(a) == 1 and a[0].startswith('🔔') and '150 ← 160' in a[0] and '<blockquote>وبلغ سعر ليتر المازوت 160 ليرة</blockquote>' in a[0]
      and '<a href="https://sana.sy/2">سانا</a>' in a[0] and st['adopted']['diesel'] == {'value': 160.0, 'date': '2026-12-01', 'single': True, 'src': 'سانا', 'news': 'rss:sana:2'}, a)
a, f = step(st, D)
check('the two sites still on the old bulletin: silent, value kept', a == [] and st['adopted']['diesel']['value'] == 160 and 'diesel' not in st['pending'])
check('board marks it single-source', 'مازوت: 160*' in sb.board_text(dict(f, weather=None, prayer=None), cfg))
d5 = copy.deepcopy(D); d5['sytra']['fuel']['prices']['diesel_1'] = 160
a, f = step(st, d5)
check('one site catches up without a new date: still the news value, silent', a == [] and st['adopted']['diesel']['value'] == 160)
d6 = copy.deepcopy(d5); d6['sptoday']['fuel']['diesel'] = 160; d6['sytra']['fuel']['bulletin_date'] = '2026-12-01'
a, f = step(st, d6)
check('both sites agree with the news: confirmed by them, news mark dropped', a == [] and st['adopted']['diesel'] == {'value': 160.0, 'date': '2026-12-01', 'single': False})
a, f = step(st, d6)
check('old news fact is not applied twice', a == [] and st['adopted']['diesel']['value'] == 160)
st2 = {}
step(st2, D, first=True)
st2['extracted'] = {'diesel': fq}
step(st2, D)
d7 = copy.deepcopy(D); d7['sytra']['fuel'].update(bulletin_date='2026-12-01'); d7['sytra']['fuel']['prices']['diesel_1'] = 165; d7['sptoday']['fuel']['diesel'] = 165
a, f = step(st2, d7)
check('sites agree on another value with the same date: unconfirmed, the official news value stays', len(a) == 1 and a[0].startswith('⚠️') and 'عن سانا' in a[0] and st2['adopted']['diesel']['value'] == 160, a)
d8 = copy.deepcopy(d7); d8['sytra']['fuel']['bulletin_date'] = '2026-12-05'
a, f = step(st2, d8)
check('sites agree on another value with a later bulletin: adopted', len(a) == 1 and a[0].startswith('🔔') and '160 ← 165' in a[0] and 'news' not in st2['adopted']['diesel'], a)
st3 = {}
step(st3, D, first=True)
st3['extracted'] = {'bread': dict(fq, value=50.0, quote='حددت سعر ربطة الخبز بـ 50 ليرة', id='rss:sana:9'), 'gasoline_95': dict(fq, value=195.0, id='rss:sana:9')}
a, f = step(st3, D)
check('bread from news: alert; fuel news with the same value: nothing', len(a) == 1 and 'ربطة الخبز' in a[0] and '40 ← 50' in a[0] and 'news' not in st3['adopted']['gasoline_95'], a)
st4 = {}
st4['extracted'] = {'diesel': fq}
a, f = step(st4, D, first=True)
check('first run ignores news facts for alerts', a == [] and st4['adopted']['diesel']['value'] == 150)

print('\nFAILED: ' + ', '.join(fails) if fails else '\nALL PASSED')
sys.exit(1 if fails else 0)
