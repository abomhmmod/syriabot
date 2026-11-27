"""اختبارات رادار المصادر بلا شبكة: الإشارات والغربال والإضافة والموافقة والرسالة الأسبوعيّة على بياناتٍ مصنوعة.
  python tests/t_radar.py            (من مجلّد البوت)"""
import copy, json, shutil, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import radar

fails = []


def check(name, cond, extra=''):
    print(('ok   ' if cond else 'FAIL ') + name, extra if not cond else '')
    if not cond:
        fails.append(name)


TZ = timezone(timedelta(hours=3))
T0 = datetime(2026, 12, 1, 9, 0, tzinfo=TZ)            # الثلاثاء

# ---------- الإشارات
got = radar.from_post({'text': 'تابعوا القناة الرسمية @MinStats_SY وموقعنا www.stats.gov.sy/ar/ ومنصّة https://new-platform.sy/x '
                               'وصفحتنا facebook.com/x وبوت @help_bot وبريد info@stats.gov.sy', 'links': ['https://t.me/s/AnotherChan']})
check('post: channels and sites, no social, no bots, no e-mail as a handle',
      ('tg', 'minstats_sy') in got and ('tg', 'anotherchan') in got and ('site', 'stats.gov.sy') in got and ('site', 'new-platform.sy') in got
      and not any(v in ('help_bot', 'facebook.com') for _, v in got) and ('tg', 'stats') not in got, got)
check('host: sub-site of gov.sy reduced to the site', radar.base_of('portal.pma.gov.sy') == 'pma.gov.sy' and radar.base_of('pma.gov.sy') == 'pma.gov.sy')
check('field: statistics, transport, education', radar.field_of('الهيئة العامة للإحصاء') == 'إحصاء وبيانات'
      and radar.field_of('الهيئة العامة للطيران المدني') == 'نقل' and radar.field_of('المنصة التربوية السورية') == 'تعليم وجامعات')
for t, want in (('مديرية تربية حلب', 'جهة محافظةٍ أخرى'), ('مجلس مدينة مصياف', 'ناحيةٌ من ريف حماة'), ('وزارة الداخلية العراقية', 'ليس سوريًّا'),
                ('جامعة الشمال الخاصة', 'جهةٌ خاصّة'), ('جامعة دمشق', None), ('مديرية التربية في حماة', None), ('وزارة الاقتصاد - دمشق', None)):
    check(f'scope: {t} → {want}', radar.scope(t) == want, radar.scope(t))
check('junk: default pages, logins, bare host, coming soon',
      all(radar.junk(x, 'a.gov.sy') for x in ('Domain Default page', 'a.gov.sy', 'قريباً | مطار', 'Login', 'ITTC', ''))
      and not radar.junk('الهيئة العامة للإحصاء', 'a.gov.sy') and radar.junk('منصة', 'a.gov.sy', 'https://a.gov.sy/site-login'))

# ---------- يومٌ أوّل
tmp = Path(tempfile.mkdtemp())
(tmp / 'directory').mkdir()
(tmp / 'news').mkdir()
(tmp / 'directory' / 'entity.jsonl').write_text(json.dumps({'id': 'entity:old', 'kind': 'entity', 'source': 'دليل الجهات · سيترا', 'title': 'قديم',
                                                             'text': 'الموقع: https://old.gov.sy', 'url': 'https://old.gov.sy'}, ensure_ascii=False) + '\n', encoding='utf-8')
srcs = {'note': 'x', 'telegram': [{'id': 'known_chan', 'name': 'قناة معروفة', 'kind': 'جهة رسميّة', 'tier': 1, 'hama': False}],
        'rss': [{'id': 'sana', 'name': 'سانا', 'kind': 'إعلام', 'tier': 2, 'hama': False, 'url': 'https://sana.sy/feed/'}]}
SITES = {'stats.gov.sy': {'title': 'الهيئة العامة للإحصاء', 'rss': 'https://stats.gov.sy/feed/', 'tg': ['statsy'], 'data': True, 'url': 'https://stats.gov.sy/', 'board': False},
         'gold.gov.sy': {'title': 'نشرة أسعار المعادن الرسمية', 'rss': None, 'tg': [], 'data': True, 'url': 'https://gold.gov.sy/', 'board': True},
         'soon.gov.sy': {'title': 'Coming Soon', 'rss': None, 'tg': [], 'data': False, 'url': 'https://soon.gov.sy/', 'board': False},
         'aleppo-edu.gov.sy': {'title': 'مديرية تربية حلب', 'rss': None, 'tg': [], 'data': False, 'url': 'https://aleppo-edu.gov.sy/', 'board': False},
         'shamal.edu.sy': {'title': 'جامعة الشمال الخاصة', 'rss': None, 'tg': [], 'data': False, 'url': 'https://shamal.edu.sy/', 'board': False},
         'hama-univ.edu.sy': {'title': 'جامعة حماة', 'rss': None, 'tg': [], 'data': False, 'url': 'https://hama-univ.edu.sy/', 'board': False},
         'new-platform.sy': {'title': 'منصّة الخدمات الحكوميّة', 'rss': None, 'tg': [], 'data': False, 'url': 'https://new-platform.sy/', 'board': False}}
CHANS = {'statsy': {'title': 'الهيئة العامة للإحصاء', 'desc': 'القناة الرسمية', 'last': T0.timestamp() - 86400},
         'officialnew': {'title': 'مديرية الطاقة في حماة', 'desc': 'القناة الرسمية لمديرية الطاقة في حماة', 'last': T0.timestamp() - 3600},
         'maybechan': {'title': 'أخبار الخدمات', 'desc': 'متابعة يومية', 'last': T0.timestamp() - 3600},
         'deadchan': {'title': 'مديرية قديمة', 'desc': 'القناة الرسمية', 'last': T0.timestamp() - 90 * 86400}}
calls = []


def site_lookup(h):
    calls.append(h)
    return copy.deepcopy(SITES.get(h))


def tg_lookup(h):
    return copy.deepcopy(CHANS.get(h))


crt = lambda: {'stats.gov.sy', 'old.gov.sy', 'gold.gov.sy', 'soon.gov.sy', 'down.gov.sy', 'aleppo-edu.gov.sy', 'shamal.edu.sy', 'hama-univ.edu.sy'}
state = {}
res = radar.daily(tmp, state, srcs, T0, crt=crt, tg_lookup=tg_lookup, site_lookup=site_lookup)
R = state['radar']
added = {a['name'] for a in R['added']}
check('day 1: the known site is not fetched', 'old.gov.sy' not in calls, calls)
check('day 1: official sites added, with RSS, and the channel the site links (verified)',
      res['sources'] and 'الهيئة العامة للإحصاء' in added and any(s['url'] == 'https://stats.gov.sy/feed/' for s in srcs['rss'])
      and any(s['id'] == 'statsy' and not s.get('unverified') and s['tier'] == 1 for s in srcs['telegram']), (added, srcs))
check('day 1: public university added, private one, other governorate and junk left out',
      'جامعة حماة' in added and 'جامعة الشمال الخاصة' not in added and 'مديرية تربية حلب' not in added and 'Coming Soon' not in added, added)
check('day 1: junk and unanswered sites wait two weeks, not marked seen',
      set(R['later']) == {'soon.gov.sy', 'down.gov.sy'} and 'soon.gov.sy' not in R['seen_hosts'], R['later'])
check('day 1: data sites listed for a reader; a board-related one is urgent',
      {x['name'] for x in R['needs_reader']} == {'الهيئة العامة للإحصاء', 'نشرة أسعار المعادن الرسمية'} and R['urgent'][0]['name'] == 'نشرة أسعار المعادن الرسمية')
rows = [json.loads(x) for x in (tmp / 'directory' / 'radar.jsonl').read_text(encoding='utf-8').splitlines()]
check('day 1: radar directory for the answers', {r['id'] for r in rows} == {'radar:stats.gov.sy', 'radar:gold.gov.sy', 'radar:hama-univ.edu.sy'}
      and 'https://t.me/statsy' in next(r for r in rows if r['id'] == 'radar:stats.gov.sy')['text'], rows)

# ---------- يومٌ ثانٍ: أخبار ومنشورات
T1 = T0 + timedelta(days=1)
posts = [{'id': 'tg:a/1', 'src': 'a', 'name': 'محافظة حماة', 'tier': 1, 'ts': int(T1.timestamp()) - 3600, 'url': 'https://t.me/a/1',
          'text': 'تابعوا قناة @OfficialNew للاطلاع', 'title': 'x'},
         {'id': 'tg:b/2', 'src': 'b', 'name': 'الإخبارية', 'tier': 2, 'ts': int(T1.timestamp()) - 3000, 'url': 'https://t.me/b/2',
          'text': 'أطلقت الحكومة منصّة جديدة https://new-platform.sy وقناة @MaybeChan و @DeadChan', 'title': 'y'},
         {'id': 'tg:c/3', 'src': 'c', 'name': 'صفحة خاصّة', 'tier': 3, 'ts': int(T1.timestamp()) - 2000, 'url': 'u', 'text': '@Ignored3', 'title': 'z'},
         {'id': 'rss:sana:1', 'src': 'sana', 'name': 'سانا', 'tier': 2, 'ts': int(T1.timestamp()) - 1000, 'url': 'https://sana.sy/1',
          'text': 'أصدر الرئيس المرسوم رقم 12 القاضي بإحداث الهيئة العامة للمواصفات والمقاييس، ومقرّها دمشق.', 'title': 'مرسوم'}]
(tmp / 'news' / f'{T1:%Y-%m-%d}.jsonl').write_text(''.join(json.dumps(p, ensure_ascii=False) + '\n' for p in posts), encoding='utf-8')
calls.clear()
res = radar.daily(tmp, state, srcs, T1, crt=crt, tg_lookup=tg_lookup, site_lookup=site_lookup)
R = state['radar']
check('day 2: sites already seen are not fetched again; waiting ones not before two weeks', calls == ['new-platform.sy'], calls)
check('day 2: a channel a tier-1 body names and that calls itself official is added, unverified',
      any(s['id'] == 'officialnew' and s.get('unverified') and s['hama'] for s in srcs['telegram']))
pend = {c['value']: n for n, c in R['pending'].items()}
check('day 2: weak ones numbered for approval (channel without «official», non-gov platform); dead and private-page ones not',
      set(pend) == {'maybechan', 'new-platform.sy'} and 'deadchan' not in pend and 'ignored3' not in pend, R['pending'])
check('day 2: decree creating a body is noted', any('الهيئة العامة للمواصفات والمقاييس' in b['name'] for b in R['bodies']), R['bodies'])
res = radar.daily(tmp, state, srcs, T1 + timedelta(hours=1), crt=crt, tg_lookup=tg_lookup, site_lookup=site_lookup)
check('same posts again: nothing proposed twice', len(R['pending']) == 2)

# ---------- الموافقة
n_ch, n_site = pend['maybechan'], pend['new-platform.sy']
msg, ch = radar.apply(state, srcs, [{'id': 'd1', 'op': 'add', 'n': [int(n_ch), '٩٩']}, {'id': 'd2', 'op': 'skip', 'n': [n_site]}], tmp,
                      tg_lookup=tg_lookup, site_lookup=site_lookup)
check('approve: «أضف» adds the channel (unverified), «تجاهل» rejects for good, an unknown number is reported',
      ch and any(s['id'] == 'maybechan' and s.get('unverified') for s in srcs['telegram']) and 'site:new-platform.sy' in R['rejected']
      and R['pending'] == {} and 'أُضيف بموافقتك' in msg and 'لن يُعرض ثانيةً' in msg and '99' in msg, msg)
check('approve: Arabic digits accepted', '٩٩' not in msg)
calls.clear()
R['seen_hosts'].remove('new-platform.sy')
radar.daily(tmp, state, srcs, T1 + timedelta(hours=2), crt=crt, tg_lookup=tg_lookup, site_lookup=site_lookup)
check('rejected: never proposed again', R['pending'] == {} and 'new-platform.sy' not in calls)

# ---------- الرسالة الأسبوعيّة
cfg = {'bulletin_hour': 7}
FRI = datetime(2026, 12, 4, 9, 0, tzinfo=TZ)
check('weekly: not on another day', radar.weekly(copy.deepcopy(state), srcs, tmp, cfg, T1) is None)
radar.propose(R, {'key': 'tg:later1', 'kind': 'tg', 'value': 'later1', 'url': '', 'via': 'ذكرته جهة'}, 'قناة تنتظر', 'نقل', 'https://t.me/later1')
w = radar.weekly(state, srcs, tmp, cfg, FRI)
check('weekly: folded sections, numbered approvals with the reply to send, data sites, decrees',
      all(x in w for x in ('رادار المصادر', 'أُضيف تلقائيًّا', 'يحتاج موافقتك (1)', '«أضف 3» أو «تجاهل 3»', 'قناة تنتظر', 'تحتاج قارئ', 'للمواصفات والمقاييس'))
      and w.count('<blockquote expandable>') == w.count('</blockquote>') >= 4, w)
check('weekly: lists emptied after it, pending kept', R['added'] == [] and R['needs_reader'] == [] and R['bodies'] == [] and len(R['pending']) == 1)
check('weekly: once a week', radar.weekly(state, srcs, tmp, cfg, FRI + timedelta(hours=1)) is None)
for k in range(1, 4):
    radar.weekly(state, srcs, tmp, cfg, FRI + timedelta(days=7 * k))
check('weekly: a proposal unanswered four weeks is folded away', R['pending'] == {}, R['pending'])
w = radar.weekly(state, srcs, tmp, cfg, FRI + timedelta(days=28))
check('weekly: a quiet week says so in one line', 'لا جديد هذا الأسبوع' in w, w)

# ---------- الصامتة وحفظ المصادر
old = T0 - timedelta(days=50)
(tmp / 'news' / f'{old:%Y-%m-%d}.jsonl').write_text(json.dumps({'src': 'sana', 'ts': int(old.timestamp())}) + '\n', encoding='utf-8')
(tmp / 'news' / f'{T1:%Y-%m-%d}.jsonl').write_text(''.join(json.dumps(p, ensure_ascii=False) + '\n' for p in posts), encoding='utf-8')
sil = radar.silent_sources(tmp, srcs, T1)
check('silent: a source with no post in 45 days is listed; one the radar just added is not',
      'قناة معروفة' in sil and 'سانا' not in sil and 'الهيئة العامة للإحصاء' not in sil, sil)
p = tmp / 'sources.json'
p.write_bytes(json.dumps(srcs, ensure_ascii=False, indent=1).replace('\n', '\r\n').encode('utf-8'))
radar.save_sources(p, srcs)
check('sources.json: written back with its own line endings, round-trips', b'\r\n' in p.read_bytes() and json.loads(p.read_text(encoding='utf-8')) == srcs)

# ---------- صندوق البحث الشهريّ (من الحاسوب)
T2 = T1 + timedelta(days=3)
CHANS.update({'monthly_ok': {'title': 'مديرية المياه في حماة', 'desc': 'القناة الرسمية لمؤسسة مياه حماة', 'last': T2.timestamp() - 3600},
              'monthly_weak': {'title': 'مديرية النقل', 'desc': 'خدمات النقل', 'last': T2.timestamp() - 3600},
              'monthly_iraq': {'title': 'وزارة الصحة العراقية', 'desc': 'القناة الرسمية', 'last': T2.timestamp() - 3600}})
inbox = {'runs': [{'id': '2026-11-30', 'tg_seen': 420, 'fb_seen': 900,
                   'tg': [{'id': 'Monthly_OK', 'proof': 3, 'via': 'موثّقة في تيليغرام'}, {'id': 'monthly_weak', 'proof': 1},
                          {'id': 'monthly_iraq', 'proof': 3}, {'id': 'known_chan', 'proof': 3}],
                   'fb': [{'name': 'مديرية صحة حماة', 'url': 'https://www.facebook.com/hama.health'}]}]}
(tmp / radar.INBOX).write_text(json.dumps(inbox, ensure_ascii=False), encoding='utf-8')
n_tg = len(srcs['telegram'])
radar.daily(tmp, state, srcs, T2, crt=crt, tg_lookup=tg_lookup, site_lookup=site_lookup)
ids = [s['id'] for s in srcs['telegram']]
check('inbox: a proven channel is added verified; a foreign one and a known one are not',
      'monthly_ok' in ids and not any(s.get('unverified') for s in srcs['telegram'] if s['id'] == 'monthly_ok')
      and 'monthly_iraq' not in ids and ids.count('known_chan') == 1, ids[n_tg:])
check('inbox: a weak one is numbered for approval', any(c['value'] == 'monthly_weak' for c in R['pending'].values()), R['pending'])
check('inbox: the Facebook follows are listed as added, with the run noted',
      any(a['what'].startswith('صفحة فيسبوك') for a in R['added']) and R['monthly']['fb_followed'] == 1 and R['monthly_last'] == '2026-11-30')
before = len(srcs['telegram'])
radar.daily(tmp, state, srcs, T2 + timedelta(days=1), crt=crt, tg_lookup=tg_lookup, site_lookup=site_lookup)
check('inbox: a run is read once', len(srcs['telegram']) == before and R['inbox_done'] == ['2026-11-30'])
FRI2 = datetime(2027, 1, 8, 9, 0, tzinfo=TZ)
w = radar.weekly(state, srcs, tmp, cfg, FRI2)
check('weekly: the monthly search line, then it is cleared', 'البحث الشهريّ داخل تيليغرام وفيسبوك' in w and 'تابع 1 صفحة' in w and 'monthly' not in R, w)
w = radar.weekly(state, srcs, tmp, cfg, datetime(2027, 1, 15, 9, 0, tzinfo=TZ))
check('weekly: a monthly search 40+ days late is flagged', 'لم يعمل منذ 2026-11-30' in w, w)
w = radar.weekly(state, srcs, tmp, cfg, datetime(2026, 12, 25, 9, 0, tzinfo=TZ))
check('weekly: not flagged while on time', w is None or 'لم يعمل منذ' not in w)

shutil.rmtree(tmp, ignore_errors=True)
print('\nFAILED:' + ', '.join(fails) if fails else '\nALL PASSED')
sys.exit(1 if fails else 0)
