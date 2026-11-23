"""اختبارات الجامع الصامت بلا شبكة: قارئ صفحات تيليغرام والخلاصات، ومنطق الجديد، والحفظ، وتنبيه المراسيم، والموجز.
  python tests/t_news.py           (من مجلّد البوت)
  python tests/t_news.py --save    يحفظ صفحة قناةٍ حيّة في tests/fixtures (يحتاج الشبكة)"""
import json, shutil, sys, tempfile, time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import news

FX = HERE / 'fixtures'
fails = []


def check(name, cond, extra=''):
    print(('ok   ' if cond else 'FAIL ') + name, extra if not cond else '')
    if not cond:
        fails.append(name)


if '--save' in sys.argv:
    FX.mkdir(exist_ok=True)
    (FX / 'tg_channel.html').write_text(news.fetch('https://t.me/s/SyrMOfA'), encoding='utf-8')
    print('saved'); sys.exit(0)


def post(n, ts, text, extra=''):
    return (f'<div class="tgme_widget_message_wrap js-widget_message_wrap"><div class="tgme_widget_message text_not_supported_wrap js-widget_message" data-post="chan/{n}">'
            f'{extra}<div class="tgme_widget_message_text js-message_text" dir="auto">{text}</div>'
            f'<div class="tgme_widget_message_footer"><a class="tgme_widget_message_date" href="https://t.me/chan/{n}"><time datetime="{ts}" class="time">10:00</time></a></div></div></div>')


# ---------- قارئ صفحة تيليغرام
page = ('<html><body>' + post(5, '2026-12-01T06:00:00+00:00', 'عنوان الخبر<br/>تفصيل أوّل <b>مهمّ</b> <a href="https://moh.gov.sy/x">الرابط</a><div class="inner">داخل <i>عنصر</i></div> وبعده نصّ')
        + post(6, '2026-12-01T07:00:00+00:00', '', '<a class="tgme_widget_message_photo_wrap" style="x"></a>')
        + post(7, '2026-12-01T08:00:00+00:00', 'منشور &amp; ثالث', '<div class="tgme_widget_message_forwarded_from">من قناة</div>'
               '<div class="tgme_widget_message_text js-message_reply_text">اقتباس ردّ لا يدخل</div>') + '</body></html>')
ps = news.tg_parse(page)
check('telegram: three posts in order', [p['n'] for p in ps] == [5, 6, 7])
check('telegram: text survives a nested element, line break kept', ps[0]['text'] == 'عنوان الخبر\nتفصيل أوّل مهمّ الرابط\nداخل عنصر\nوبعده نصّ', repr(ps[0]['text']))
check('telegram: link, time, media, forward flags', ps[0]['links'] == ['https://moh.gov.sy/x'] and ps[0]['ts'] == 1796104800.0 and ps[1]['media'] and ps[2]['fwd'] and not ps[0]['media'])
check('telegram: reply quote is not the text, entities decoded', ps[2]['text'] == 'منشور & ثالث', repr(ps[2]['text']))
if (FX / 'tg_channel.html').exists():
    live = news.tg_parse((FX / 'tg_channel.html').read_text(encoding='utf-8'))
    check('telegram: saved live page parses', len(live) >= 5 and all(p['ts'] for p in live) and sum(len(p['text']) > 40 for p in live) >= 3, len(live))

SRC = {'id': 'chan', 'name': 'وزارة التجربة', 'kind': 'وزارة', 'tier': 1, 'hama': False}
NOW = 1796104800.0 + 3 * 3600                     # 2026-12-01 09:00 UTC
calls = []


def fake_pages(pages):
    def f(url, timeout=40):
        calls.append(url)
        key = url.split('before=')[1] if 'before=' in url else ''
        return pages.get(key, '<html></html>')
    return f


news.time.sleep = lambda s: None
p1 = '<html>' + post(18, '2026-11-28T08:00:00+00:00', 'قديم جدًّا خارج النافذة') + post(19, '2026-12-01T05:00:00+00:00', 'خبر تسعة عشر') + post(20, '2026-12-01T08:30:00+00:00', 'خبر عشرين') + '</html>'
news.fetch = fake_pages({'': p1})
items, newest = news.read_channel(SRC, None, NOW)
check('channel first time: only the last 48 hours, newest id kept', [i['id'] for i in items] == ['tg:chan/19', 'tg:chan/20'] and newest == 20, [i['id'] for i in items])
check('item shape', items[0]['tier'] == 1 and items[0]['name'] == 'وزارة التجربة' and items[0]['url'] == 'https://t.me/chan/19' and items[0]['title'] == 'خبر تسعة عشر')
items, newest = news.read_channel(SRC, 20, NOW)
check('channel: nothing new', items == [] and newest == 20)
calls.clear()
news.fetch = fake_pages({'': '<html>' + post(30, '2026-12-01T08:00:00+00:00', 'ثلاثون') + post(31, '2026-12-01T08:10:00+00:00', 'واحد وثلاثون') + '</html>',
                         '30': '<html>' + post(27, '2026-12-01T07:00:00+00:00', 'سبعة وعشرون') + post(28, '2026-12-01T07:10:00+00:00', '') + post(29, '2026-12-01T07:20:00+00:00', 'تسعة وعشرون') + '</html>',
                         '27': '<html>' + post(25, '2026-12-01T06:00:00+00:00', 'خمسة وعشرون') + post(26, '2026-12-01T06:10:00+00:00', 'ستّة وعشرون') + '</html>'})
items, newest = news.read_channel(SRC, 26, NOW)
check('channel gap: older pages read until the last seen, photo-only post skipped', [i['id'].split('/')[1] for i in items] == ['27', '29', '30', '31'] and newest == 31 and len(calls) == 2, ([i['id'] for i in items], calls))

# ---------- الخلاصات
rss = '''<rss><channel><item><title><![CDATA[المرسوم رقم (210) لعام 2026: تعيين محافظ جديد لحماة]]></title><link>https://sana.sy/p/1/</link><guid isPermaLink="false">https://sana.sy/?p=1</guid>
<pubDate>Tue, 01 Dec 2026 08:00:00 +0000</pubDate><category><![CDATA[رئاسة]]></category><description><![CDATA[<p>موجز</p>]]></description>
<content:encoded><![CDATA[<p>أصدر الرئيس المرسوم رقم 210.</p><p>الفقرة الثانية &amp; تتمّة</p><p>ظهرت المقالة المرسوم أولاً على سانا.</p>]]></content:encoded></item>
<item><title>خبر قديم</title><link>https://sana.sy/p/0/</link><guid>https://sana.sy/?p=0</guid><pubDate>Fri, 27 Nov 2026 08:00:00 +0000</pubDate><description>نصّ</description></item></channel></rss>'''
rows = news.rss_parse(rss)
check('rss: two items, full text preferred, tail line dropped', len(rows) == 2 and rows[0]['text'] == 'أصدر الرئيس المرسوم رقم 210.\nالفقرة الثانية & تتمّة' and rows[0]['cats'] == ['رئاسة'], repr(rows[0]['text']))
RS = {'id': 'sana', 'name': 'سانا', 'kind': 'إعلام', 'tier': 2, 'hama': False, 'url': 'x'}
news.fetch = lambda url, timeout=40: rss
got, guids = news.read_rss(RS, set(), NOW)
check('rss first time: only the last 48 hours; all guids remembered', [g['title'][:7] for g in got] == ['المرسوم'] and len(guids) == 2)
got, guids = news.read_rss(RS, {'https://sana.sy/?p=1', 'https://sana.sy/?p=0'}, NOW)
check('rss: seen items are not returned', got == [])

# ---------- الجمع والحفظ
tmp = Path(tempfile.mkdtemp())
news.fetch = lambda url, timeout=40: rss if url == 'x' else ((_ for _ in ()).throw(OSError('down')) if 'dead' in url else p1)
st = {}
sources = {'telegram': [SRC, {'id': 'dead', 'name': 'قناة معطّلة', 'tier': 1}], 'rss': [RS]}
got, failed = news.collect(sources, st, NOW, workers=2)
check('collect: one source down does not stop the others', failed == 1 and {g['src'] for g in got} == {'chan', 'sana'} and st['fail'] == {'dead': 1} and st['tg'] == {'chan': 20}, (failed, st.get('fail')))
added = news.store(tmp, got, 60, datetime(2026, 12, 1, tzinfo=news.TZ))
again = news.store(tmp, got, 60, datetime(2026, 12, 1, tzinfo=news.TZ))
files = sorted(f.name for f in (tmp / 'news').glob('*.jsonl'))
check('store: daily file, no duplicates on a second write', len(added) == 3 and again == [] and files == ['2026-12-01.jsonl'] and len((tmp / 'news' / files[0]).read_text(encoding='utf-8').splitlines()) == 3, (len(added), files))
got2, failed = news.collect(sources, st, NOW, workers=2)
check('collect again: nothing new, failure counted', got2 == [] and st['fail'] == {'dead': 2})
(tmp / 'news' / '2026-09-01.jsonl').write_text('{"id":"old","ts":1}\n', encoding='utf-8')
news.store(tmp, [], 60, datetime(2026, 12, 1, tzinfo=news.TZ))
check('store: files older than the keep window are removed', not (tmp / 'news' / '2026-09-01.jsonl').exists())
rc = news.recent(tmp, NOW - 86400, NOW)
check('recent: last 24 hours, oldest first', [r['ts'] for r in rc] == sorted(r['ts'] for r in rc) and len(rc) == 3)


# ---------- تنبيه المراسيم
def it(title, src='sana', tier=2, text='', name='سانا'):
    return {'id': title, 'src': src, 'name': name, 'tier': tier, 'hama': False, 'ts': int(NOW), 'title': title, 'text': text or title, 'url': 'https://u/' + src}


d = {}
a = news.decree_alerts([it('الرئيس الشرع يصدر المرسوم رقم (210) لعام 2026 القاضي بتعيين محافظ لحماة', text='الرئيس الشرع يصدر المرسوم رقم (210) لعام 2026 القاضي بتعيين محافظ لحماة\nنصّ المرسوم كاملًا هنا.')], d, 2026)
check('decree with a number: one alert, keyed by year and number', len(a) == 1 and d['decrees'] == ['2026-210'] and 'المرسوم رقم (210)' in a[0] and 'نصّ المرسوم كاملًا' in a[0] and '<blockquote expandable>' in a[0], a)
a = news.decree_alerts([it('رئاسة الجمهورية: المرسوم ٢١٠ لعام ٢٠٢٦ بتعيين محافظ حماة', src='presidency', tier=1, name='رئاسة الجمهوريّة')], d, 2026)
check('same decree from another channel, Arabic digits: not repeated', a == [])
a = news.decree_alerts([it('مرسوم تشريعي رقم 14 بزيادة الرواتب 50 بالمئة', src='moad', tier=1)], d, 2026)
check('legislative decree, year from the clock', len(a) == 1 and '2026-14' in d['decrees'])
a = news.decree_alerts([it('تعيين المهندس فلان الفلاني وزيراً للصحة')], d, 2026)
b = news.decree_alerts([it('تعيين المهندس فلان الفلاني وزيراً للصحة', src='moh', tier=1)], d, 2026)
check('appointment without a number: from SANA only, once', len(a) == 1 and b == [])
neg = [it('وزير الصحة يبحث مع نظيره الأردني تعزيز التعاون'), it('إعفاء المستوردين من الرسوم بموجب المرسوم رقم 100 لعام 2025'),
       it('في ذكرى صدور المرسوم رقم 5'), it('مرسوم رقم 300 لعام 2026', tier=3, src='enab'), it('المحافظ يتفقد أعمال تأهيل طريق حماة'),
       it('خبر عادي', text='وكان المرسوم رقم 9 قد صدر سابقًا')]
a = news.decree_alerts(neg, d, 2026)
check('not decrees: meetings, "by decree", anniversaries, private media, body-only mentions', a == [], a)

# ---------- الموجز
rows = [dict(it(f'خبر رقم {i} عن خدمة تهمّ المواطنين في البلاد وتفاصيله الكافية هنا للقراءة', src='moh', tier=1, name='وزارة الصحّة'), id=f'x{i}', ts=int(NOW) - 600 * i) for i in range(1, 9)]
rows[2].update(hama=True, name='محافظة حماة', src='HamaGov1')
rows.append(dict(it('خبر خاصّ لا يدخل الموجز لأنّه من إعلام خاصّ وليس من مصدر رسميّ هنا', tier=3, src='enab'), id='p', ts=int(NOW) - 60))
shutil.rmtree(tmp / 'news'); news.store(tmp, rows, 60, datetime(2026, 12, 1, tzinfo=news.TZ))
seen_prompt = {}


def ask(prompt):
    seen_prompt['p'] = prompt
    return {'general': [{'line': 'بند  أوّل <مهمّ>', 'refs': [1, 2, 99]}, {'line': 'بند بلا مصدر صحيح', 'refs': [500]}, {'line': 'بند ثالث', 'refs': [3]}],
            'hama': [{'line': 'بند حماة', 'refs': [6]}]}


dg = news.digest(tmp, {'city': 'حماة'}, NOW, ask=ask)
check('digest: only official sources go to the model', dg['count'] == 8 and 'إعلام خاصّ' not in seen_prompt['p'] and '[1] ' in seen_prompt['p'])
check('digest: lines escaped, linked to sources, invalid refs dropped', len(dg['general']) == 2 and dg['general'][0].startswith('• بند أوّل &lt;مهمّ&gt;') and 'href="https://u/moh"' in dg['general'][0] and dg['general'][0].count('<a ') == 1, dg['general'])
check('digest: hama section', len(dg['hama']) == 1 and 'محافظة حماة' in dg['hama'][0], dg['hama'])
check('digest: model failure gives None', news.digest(tmp, {'city': 'حماة'}, NOW, ask=lambda p: None) is None)
import os
os.environ.pop('GEMINI_API_KEY', None)
check('digest: no key gives None', news.digest(tmp, {'city': 'حماة'}, NOW) is None)
shutil.rmtree(tmp, ignore_errors=True)

print('\nFAILED: ' + ', '.join(fails) if fails else '\nALL PASSED')
sys.exit(1 if fails else 0)
