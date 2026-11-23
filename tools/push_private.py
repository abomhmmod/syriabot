# -*- coding: utf-8 -*-
"""يرفع البيانات الخاصّة إلى مجلّد البوت في Google Drive (عبر مستقبِل السؤال والجواب نفسه)، ولا يمرّ شيءٌ منها بالمستودع:
  - أرشيف منشورات فيسبوك وX التي يحفظها SocialWatch في archive/  ← ملفٌّ لكلّ يوم  social-YYYY-MM-DD.jsonl
  - مداخل دليل الحيّ local/hay.jsonl (يبنيها tools/build_hay.py)      ← hay.jsonl
يُرفع ما تغيّر فقط (ببصمة كلّ ملفّ)، ومرّةً في الساعة على الأكثر إلّا مع --force.

الإعداد في local/push.json (خارج المستودع): {"url": "عنوان تطبيق الويب", "key": "مفتاح الرفع"}. المفتاح يولَّد هنا أوّل مرّة،
ويسجّله المستقبِل عند أوّل رفع ثمّ لا يقبل غيره.

  python tools/push_private.py            رفعٌ عاديّ
  python tools/push_private.py --force    الآن ولو لم تمضِ ساعة
  python tools/push_private.py --dry DIR  يكتب الملفّات في DIR بدل رفعها (للتجربة)
"""
import hashlib, json, re, secrets, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOCAL, ARCHIVE = BASE / 'local', BASE / 'archive'
TZ = timezone(timedelta(hours=3))
KEEP_DAYS, TEXT_MAX, BATCH = 45, 1500, 3_000_000
NET = {'facebook': 'فيسبوك', 'x': 'X', 'instagram': 'إنستغرام', 'reddit': 'ريديت'}


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def note(msg):
    """يُطبع ويُكتب في local/push.log (آخر 200 سطر): الرفع يجري في الخلفيّة بلا نافذة."""
    print(msg)
    try:
        log = LOCAL / 'push.log'
        old = log.read_text(encoding='utf-8').splitlines()[-200:] if log.exists() else []
        log.write_text('\n'.join(old + [f'{datetime.now(TZ):%Y-%m-%d %H:%M} {msg}']) + '\n', encoding='utf-8')
    except OSError:
        pass


def flat(v):
    """نصّ منشورٍ مشارَك أو مقتبَس: قائمة [الاسم، المعرّف، النصّ] أو نصّ."""
    if isinstance(v, (list, tuple)):
        return ' — '.join(str(x) for x in v if x and not str(x).startswith('http'))
    return str(v or '')


def compact(r):
    """سطرٌ صغير للبحث: المعرّف، الصفحة، الشبكة، النصّ (مع ما شاركه أو اقتبسه)، الرابط، الوقت."""
    text = '\n'.join(x for x in (r.get('title') or '', r.get('t') or '') if x).strip()
    for label, key in (('يشارك', 'shared'), ('يقتبس', 'quote')):
        if r.get(key):
            text += f'\n[{label}: {flat(r[key])}]'
    ts = r.get('pt') if isinstance(r.get('pt'), (int, float)) and r['pt'] > 1e9 else r.get('ts')
    if not text or len(text) < 15 or not isinstance(ts, (int, float)):
        return None
    return {'id': r.get('id'), 'n': r.get('n') or '', 'k': NET.get(r.get('k'), r.get('k') or ''), 't': text[:TEXT_MAX],
            'u': r.get('u') or '', 'ts': int(ts)}


def day_files(archive=ARCHIVE, now=None):
    """{اسم الملفّ: نصّه} لأيّام آخر KEEP_DAYS يومًا، بلا تكرار (المعرّف، ثمّ الصفحة مع أوّل النصّ)."""
    now = now or time.time()
    days, seen = {}, set()
    for f in sorted(Path(archive).glob('social-*.jsonl')):
        for line in f.read_text(encoding='utf-8').splitlines():
            try:
                c = compact(json.loads(line))
            except ValueError:
                continue
            if not c or c['ts'] < now - KEEP_DAYS * 86400:
                continue
            twin = (c['n'], re.sub(r'\W+', '', c['t'])[:120])
            if c['id'] in seen or twin in seen:
                continue
            seen.update((c['id'], twin))
            days.setdefault(datetime.fromtimestamp(c['ts'], TZ).strftime('%Y-%m-%d'), []).append(c)
    return {f'social-{d}.jsonl': ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in sorted(rows, key=lambda r: r['ts']))
            for d, rows in days.items()}


def post(url, body, timeout=180):
    req = urllib.request.Request(url, json.dumps(body).encode('utf-8'), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:        # تطبيق الويب يجيب بتحويلٍ يتبعه urllib
        return json.loads(r.read().decode('utf-8'))


def main(argv):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    dry = Path(argv[argv.index('--dry') + 1]) if '--dry' in argv else None
    cfg, state = load(LOCAL / 'push.json', {}), load(LOCAL / 'push_state.json', {})
    if not dry and not cfg.get('url'):
        print('لا عنوان للرفع في local/push.json بعد.')
        return 0
    if not dry and '--force' not in argv and time.time() - state.get('at', 0) < 3300:
        return 0
    if not dry and not cfg.get('key'):
        cfg['key'] = secrets.token_urlsafe(32)
        (LOCAL / 'push.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding='utf-8')
    files = day_files()
    hay = LOCAL / 'hay.jsonl'
    if hay.exists():
        files['hay.jsonl'] = hay.read_text(encoding='utf-8')
    sums = {name: hashlib.sha1(text.encode('utf-8')).hexdigest() for name, text in files.items()}
    known = state.get('sums', {}) if not dry else {}
    todo = [name for name in sorted(files) if known.get(name) != sums[name]]
    if dry:
        dry.mkdir(parents=True, exist_ok=True)
        for name in todo:
            (dry / name).write_text(files[name], encoding='utf-8', newline='\n')
        print(f'{len(todo)} ملفًّا في {dry} ({sum(len(files[n]) for n in todo):,} حرفًا)')
        return 0
    sent, batch, size = 0, [], 0
    for name in todo + [None]:
        if batch and (name is None or size + len(files[name]) > BATCH):
            r = post(cfg['url'], {'key': cfg['key'], 'files': [{'name': n, 'text': files[n]} for n in batch], 'keep': sorted(files)})
            if not r.get('ok'):
                note(f'رُفض الرفع: {r.get("error")}')
                return 1
            for n in r.get('saved', []):
                known[n] = sums[n]
            sent += len(r.get('saved', []))
            state.update(sums=known, at=time.time())
            (LOCAL / 'push_state.json').write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
            batch, size = [], 0
        if name is not None:
            batch.append(name)
            size += len(files[name])
    state.update(sums={n: s for n, s in known.items() if n in files}, at=time.time())
    (LOCAL / 'push_state.json').write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    if sent:
        note(f'رُفع {sent} ملفًّا من {len(files)}.')
    else:
        print('لا جديد يُرفع.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as ex:
        note(f'تعذّر الرفع: {type(ex).__name__}: {str(ex)[:200]}')
        sys.exit(1)
