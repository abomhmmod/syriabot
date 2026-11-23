# -*- coding: utf-8 -*-
"""يستورد إلى «القسم الخاصّ» في البوت دفعةً واحدة، من حاسوب صاحبه مباشرةً إلى مشروعه في جوجل (HTTPS)، بلا تيليغرام وبلا
أيّ نموذج. لا يطبع قيمةً ولا يحفظها في ملفّ: يطبع الأعداد فقط.

  - كلمات السرّ من ملفّات تصدير المتصفّحات (CSV من كروم أو إيدج أو فايرفوكس):
        الاسم «حساب <الموقع> · <المستخدم>»، والقيمة المستخدم وكلمة السرّ والموقع.
  - أرقام الهاتف من جهات اتّصال الهاتف الموصول بالكبل (adb):
        الاسم «هاتف <الاسم>»، والقيمة أرقامه.

  pythonw tools/vault_import.py                 نافذة لاختيار ملفّات CSV، ثمّ تعرض الأعداد وتعرض حذف الملفّات
  python tools/vault_import.py --csv A.csv B.csv
  python tools/vault_import.py --contacts       جهات اتّصال الهاتف الموصول
  أضف --dry ليَعدّ ولا يرفع.

العنوان والمفتاح في local/push.json (هما عنوان الرفع ومفتاحه نفسهما).
"""
import csv, json, re, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
AR = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
COLS = {'url': ('url', 'origin', 'website', 'login_uri', 'web site', 'uri'), 'user': ('username', 'login', 'user', 'login_username', 'user name', 'email'),
        'password': ('password', 'login_password', 'pass'), 'name': ('name', 'title'), 'note': ('note', 'notes', 'comments', 'extra')}


def site_of(url, name=''):
    u = (url or '').strip()
    if u.startswith('android://'):                         # تطبيق أندرويد: اسم الحزمة
        return u.split('@')[-1].strip('/') or name
    host = urllib.parse.urlparse(u if '://' in u else 'https://' + u).netloc if u else ''
    host = re.sub(r'^www\.', '', host.split('@')[-1].split(':')[0])
    return host or (name or '').strip()


def from_csv(paths):
    """مداخل كلمات السرّ من ملفّات التصدير، بلا تكرار: الحساب نفسه بكلمة السرّ نفسها مرّة واحدة، وبكلمةٍ أخرى «نسخة 2»."""
    seen, out, rows = {}, [], 0
    for path in paths:
        with open(path, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                rows += 1
                low = {(k or '').strip().lower(): (v or '') for k, v in r.items()}
                get = lambda kind: next((low[c] for c in COLS[kind] if low.get(c)), '')
                pw, user, url = get('password'), get('user').strip(), get('url').strip()
                site = site_of(url, get('name'))
                if not pw or not site:
                    continue
                key = (site.lower(), user.lower())
                if pw in seen.setdefault(key, []):
                    continue
                seen[key].append(pw)
                n = len(seen[key])
                name = f'حساب {site}' + (f' · {user}' if user else '') + (f' · نسخة {n}' if n > 1 else '')
                value = (f'المستخدم: {user}\n' if user else '') + f'كلمة السرّ: {pw}' + (f'\nالموقع: {url}' if url else '') + (f'\nملاحظة: {get("note").strip()}' if get('note').strip() else '')
                out.append({'name': name[:200], 'value': value[:3000]})
    return out, rows


def from_phone():
    """جهات اتّصال الهاتف الموصول: اسمٌ ← أرقامه."""
    r = subprocess.run(['adb', 'shell', 'content query --uri content://com.android.contacts/data/phones --projection display_name:data1'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180, creationflags=0x08000000)
    people, rows = {}, 0
    for line in r.stdout.splitlines():
        m = re.search(r'display_name=(.*), data1=(.*)$', line)
        if not m:
            continue
        rows += 1
        name = re.sub(r'\s+', ' ', m.group(1)).strip()
        num = re.sub(r'[^\d+]', '', m.group(2).translate(AR))
        if not name or name == 'NULL' or len(re.sub(r'\D', '', num)) < 5:
            continue
        nums = people.setdefault(name, [])
        if not any(re.sub(r'\D', '', x)[-9:] == re.sub(r'\D', '', num)[-9:] for x in nums):
            nums.append(num)
    return [{'name': f'هاتف {name}'[:200], 'value': '\n'.join(nums)} for name, nums in sorted(people.items())], rows


def upload(items):
    cfg = json.loads((BASE / 'local' / 'push.json').read_text(encoding='utf-8'))
    add = upd = total = 0
    for i in range(0, len(items), 250):
        body = json.dumps({'key': cfg['key'], 'files': [], 'vault': items[i:i + 250]}).encode('utf-8')
        req = urllib.request.Request(cfg['url'], body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=240) as r:
            j = json.loads(r.read().decode('utf-8'))
        if not j.get('ok') or 'vault' not in j:
            raise RuntimeError(j.get('error') or 'المستقبِل لم يُجب عن الاستيراد (هل نُشرت نسخته الجديدة؟)')
        add, upd, total = add + j['vault']['added'], upd + j['vault']['updated'], j['vault']['total']
    return add, upd, total


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    paths = filedialog.askopenfilenames(parent=root, title='اختر ملفّات كلمات السرّ المصدَّرة من المتصفّحات (CSV)', filetypes=[('CSV', '*.csv'), ('الكلّ', '*.*')])
    if not paths:
        return
    try:
        items, rows = from_csv(paths)
        if not items:
            messagebox.showerror('القسم الخاصّ', f'لم أجد كلمات سرّ في {len(paths)} ملفّ ({rows} سطرًا). هل هي ملفّات تصدير كلمات السرّ؟')
            return
        add, upd, total = upload(items)
    except Exception as ex:
        messagebox.showerror('القسم الخاصّ', f'تعذّر الاستيراد: {type(ex).__name__}: {str(ex)[:200]}\nلم يُحذف شيء.')
        return
    messagebox.showinfo('القسم الخاصّ', f'تمّ.\nقُرئ {rows} سطرًا من {len(paths)} ملفّ.\nأُضيف {add}، وحُدّث {upd}.\nفي القسم الخاصّ الآن {total} معلومة.')
    if messagebox.askyesno('القسم الخاصّ', 'ملفّات التصدير فيها كلمات سرّك مكشوفة.\nأأحذفها الآن؟ (أنصح بذلك)'):
        for p in paths:
            try:
                Path(p).unlink()
            except OSError:
                pass
        messagebox.showinfo('القسم الخاصّ', 'حُذفت ملفّات التصدير.')


def main(argv):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    if not argv:
        return gui()
    items, rows = [], 0
    if '--contacts' in argv:
        got, n = from_phone()
        items, rows = items + got, rows + n
    if '--csv' in argv:
        paths = [a for a in argv[argv.index('--csv') + 1:] if not a.startswith('--')]
        got, n = from_csv(paths)
        items, rows = items + got, rows + n
    print(f'قُرئ {rows} سطرًا ← {len(items)} معلومة.')
    if '--dry' in argv or not items:
        return
    add, upd, total = upload(items)
    print(f'أُضيف {add}، وحُدّث {upd}. في القسم الخاصّ الآن {total} معلومة.')


if __name__ == '__main__':
    main(sys.argv[1:])
