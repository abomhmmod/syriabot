# -*- coding: utf-8 -*-
"""التحديث الأسبوعيّ لدليل الحيّ (قرار صاحب البوت 2026-11-27: «نعم، كلّ أسبوع»). يقرأ أرشيف MsgKeeper قراءةً فقط،
ولا يكتب شيئًا خاصًّا في المستودع: كلّ ما يخرج منه في local/ (خارج git).

  python tools/hay_week.py export   رسائل مجموعات الحيّ الجديدة منذ آخر تحديث → local/hay_new.txt، ونسخةٌ احتياطيّة من الدليل
  python tools/hay_week.py check    كلّ رقمٍ في الدليل يجب أن يكون في رسالةٍ من الرسائل المقروءة، خانةً خانة
  python tools/hay_week.py done     بعد تعديل الدليل: الفحص، ثمّ hay.jsonl، ثمّ الرفع إلى مجلّد البوت في Drive، ثمّ يُحفظ موضع القراءة

بين export و done يقرأ Claude (المهمّة المجدولة «دليل الحيّ الأسبوعيّ») الرسائل ويعدّل local/دليل-الحيّ.html.
"""
import json, re, shutil, sqlite3, subprocess, sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOCAL = BASE / 'local'
GUIDE = LOCAL / 'دليل-الحيّ.html'
NEW = LOCAL / 'hay_new.txt'
WEEKS = LOCAL / 'hay_weeks'                 # رسائل كلّ أسبوعٍ قُرئ، ليُفحص بها كلّ رقمٍ في الدليل لاحقًا
BACKUPS = LOCAL / 'hay_backups'
STATE = LOCAL / 'hay_week_state.json'
GROUPS = LOCAL / 'hay_groups.json'
DB = Path(r'D:\Work\Bots\MsgKeeper\data\archive.sqlite3')
FIRST_CUT = '2026-11-23 10:42'              # آخر رسالةٍ في الجرد الأوّل (local/hay_dump.txt)
AR = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')


def load(p, d):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return d


def save(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


def export():
    st = load(STATE, {})
    cut = st.get('last_ts') or int(datetime.strptime(FIRST_CUT, '%Y-%m-%d %H:%M').timestamp()) + 59
    groups = load(GROUPS, {})['groups']
    con = sqlite3.connect(f'file:{DB.as_posix()}?mode=ro', uri=True)
    rows = con.execute(f"select chat_id, sender, date, text, media, transcript, deleted_at from messages where platform = 'wa' and chat_id in "
                       f"({','.join('?' * len(groups))}) and date > ? order by chat_id, date", list(groups) + [cut]).fetchall()
    con.close()
    by = {}
    for chat, sender, date, text, media, transcript, deleted in rows:
        body = (text or '').strip()
        if media:
            body = (body + ' ' if body else '') + f'[وسائط: {media}]'
        if transcript:
            body += f' [نصّ الرسالة الصوتيّة: {transcript.strip()}]'
        if deleted:
            body += ' [حذفها صاحبها]'
        by.setdefault(chat, []).append(f'[{datetime.fromtimestamp(date):%Y-%m-%d %H:%M}] {sender or "؟"}: {body}')
    out = [f'رسائل مجموعات الحيّ من {datetime.fromtimestamp(cut):%Y-%m-%d %H:%M} إلى الآن ({len(rows)} رسالة)']
    for chat, label in groups.items():
        lines = by.get(chat, [])
        out.append(f'\n######## المجموعة: {label} ({len(lines)} رسالة)\n')
        out.extend(lines)
    NEW.write_text('\n'.join(out) + '\n', encoding='utf-8')
    st['pending_to'] = max([cut] + [r[2] for r in rows])
    save(STATE, st)
    BACKUPS.mkdir(exist_ok=True)
    shutil.copy(GUIDE, BACKUPS / f'دليل-الحيّ.{datetime.now():%Y%m%d-%H%M}.html')
    print(f'{len(rows)} new message(s): ' + ', '.join(f'{groups[c]} {len(v)}' for c, v in by.items()) + f' → {NEW}')
    return len(rows)


def digits(s):
    return re.sub(r'\D', '', s.translate(AR))


def check():
    """رقمٌ في الدليل لا يُرى في أيّ رسالةٍ مقروءة خطأ نسخ: يُرفض الرفع حتّى يُصحَّح."""
    html = GUIDE.read_text(encoding='utf-8')
    corpus = [LOCAL / 'hay_dump.txt', NEW] + sorted(WEEKS.glob('*.txt'))
    seen = digits(' '.join(p.read_text(encoding='utf-8') for p in corpus if p.exists()).replace('\n', ' '))
    raw = ' '.join(p.read_text(encoding='utf-8').translate(AR) for p in corpus if p.exists())
    nums = set(re.findall(r'class="num">([^<]+)<', html))
    bad = []
    for n in nums:
        d = digits(n)
        if len(d) < 3:
            continue
        variants = {d, d[3:] if d.startswith('963') else d, d[5:] if d.startswith('00963') else d}
        if d.startswith('963'):
            variants.add('0' + d[3:])
        if d.startswith('00963'):
            variants.add('0' + d[5:])
        if not any(v and (v in seen or v in re.sub(r'[\s\-]', '', raw)) for v in variants):
            bad.append(n)
    if bad:
        print('NOT FOUND in the messages (fix or remove):', ', '.join(sorted(bad)))
        return False
    print(f'all {len(nums)} numbers found in the messages')
    return True


def done():
    if not check():
        return 1
    r = subprocess.run([sys.executable, str(BASE / 'tools' / 'build_hay.py')], capture_output=True, text=True, encoding='utf-8')
    print(r.stdout.strip()[-300:], r.stderr.strip()[-300:])
    if r.returncode:
        return 1
    st = load(STATE, {})
    WEEKS.mkdir(exist_ok=True)
    if NEW.exists():
        shutil.copy(NEW, WEEKS / f'{datetime.now():%Y-%m-%d}.txt')
    r = subprocess.run([sys.executable, str(BASE / 'tools' / 'push_private.py'), '--force'], capture_output=True, text=True, encoding='utf-8')
    print(r.stdout.strip()[-300:], r.stderr.strip()[-300:])
    if r.returncode:
        print('upload failed: the reading position is kept, the next run will upload again')
        return 1
    if st.get('pending_to'):
        st['last_ts'] = st.pop('pending_to')
    st['last_done'] = f'{datetime.now():%Y-%m-%d %H:%M}'
    save(STATE, st)
    NEW.unlink(missing_ok=True)
    print('done: guide rebuilt and uploaded; next run reads from', datetime.fromtimestamp(st['last_ts']).strftime('%Y-%m-%d %H:%M'))
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'export':
        export()
    elif cmd == 'check':
        sys.exit(0 if check() else 1)
    elif cmd == 'done':
        sys.exit(done())
    else:
        print(__doc__)
