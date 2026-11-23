# -*- coding: utf-8 -*-
"""يحوّل صفحة دليل الحيّ (HTML خاصّة، خارج المستودع) إلى مداخل صغيرة قابلة للبحث: سطرٌ لكلّ صفّ جدول ولكلّ بند.
الناتج ملفّ JSONL خاصّ يُرفع إلى مجلّد البوت في Drive، ولا يدخل المستودع العامّ.

  python tools/build_hay.py [الصفحة] [الناتج]      الأصل: local/دليل-الحيّ.html ← local/hay.jsonl
"""
import json, re, sys
from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
EMPTY = {'', '—', '-', '–'}
# قرار صاحب البوت: لا أرقام معلنين في الدليل. يُحذف ما كتب صاحبه إعلانه بنفسه، وما أُرسل رقمًا بلا وصف؛
# ويبقى من أوصى به الجيران (حِرفيٌّ سُئل عنه فأُجيب برقمه) والجهات الرسميّة واللجنة.
ADS = re.compile(r'إعلان من صاحبه|لا توصية|الخدمة: غير واضح')


def text(parts):
    return re.sub(r'\s+', ' ', ''.join(parts or [])).strip()


class Guide(HTMLParser):
    """العناوين تحدّد القسم. صفّ الجدول مدخل («العمود: القيمة» لكلّ خانة). البند مدخل، والبند الفرعيّ يحمل أوّل بنده الأب."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.title, self.h2, self.h3 = [], '', '', ''
        self.skip, self.block, self.buf = 0, None, None        # block: h1/h2/h3/p الجاري
        self.heads, self.cells, self.cell = [], None, None
        self.lis = []                                           # كلّ بندٍ مفتوح: [أجزاء نصّه، عدد أبنائه]

    def emit(self, body):
        body = text([body])
        if len(body) >= 12:
            self.out.append({'section': ' › '.join(x for x in (self.h2, self.h3) if x), 'text': body})

    def handle_starttag(self, tag, attrs):
        if tag in ('nav', 'style', 'script', 'head'):
            self.skip += 1
        if self.skip:
            return
        if tag in ('h1', 'h2', 'h3') or (tag == 'p' and self.cells is None and not self.lis):
            self.block, self.buf = tag, []
        elif tag == 'table':
            self.heads = []
        elif tag == 'tr':
            self.cells = []
        elif tag in ('td', 'th') and self.cells is not None:
            self.cell = [tag, []]
        elif tag == 'li':
            self.lis.append([[], 0])
        elif tag == 'br':
            self.handle_data(' ')

    def handle_endtag(self, tag):
        if tag in ('nav', 'style', 'script', 'head'):
            self.skip -= 1
            return
        if self.skip:
            return
        if tag == self.block:
            t = text(self.buf)
            if tag == 'h1':
                self.title = t
            elif tag == 'h2':
                self.h2, self.h3 = re.sub(r'^[\d٠-٩]+[.\-]\s*', '', t), ''
            elif tag == 'h3':
                self.h3 = t
            else:
                self.emit(t)
            self.block = self.buf = None
        elif tag in ('td', 'th') and self.cell:
            self.cells.append((self.cell[0], text(self.cell[1])))
            self.cell = None
        elif tag == 'tr' and self.cells is not None:
            if self.cells and all(k == 'th' for k, _ in self.cells):
                self.heads = [v for _, v in self.cells]
            else:
                vals = [v for _, v in self.cells]
                pairs = [(self.heads[i] if i < len(self.heads) else '', v) for i, v in enumerate(vals) if v not in EMPTY]
                self.emit(' · '.join(f'{h}: {v}' if h else v for h, v in pairs))
            self.cells = None
        elif tag == 'li' and self.lis:
            parts, kids = self.lis.pop()
            own = text(parts)
            if self.lis:
                self.lis[-1][1] += 1
                lead = text(self.lis[-1][0])
                self.emit((lead[:90] + ' ' if lead else '') + own)
            elif own and (not kids or len(own) >= 40):
                self.emit(own)

    def handle_data(self, data):
        if self.skip:
            return
        if self.cell is not None:
            self.cell[1].append(data)
        elif self.buf is not None:
            self.buf.append(data)
        elif self.lis:
            self.lis[-1][0].append(data)


def build(page):
    g = Guide()
    g.feed(Path(page).read_text(encoding='utf-8'))
    until = re.search(r'إلى (\d{4}-\d\d-\d\d)', ' '.join(e['text'] for e in g.out[:3]))
    source = 'دليل الحيّ (من مجموعات واتساب لجنة الحيّ' + (f'، حتّى {until.group(1)}' if until else '') + ')'
    kept = [e for e in g.out if not ADS.search(e['text'])]
    return [{'id': f'hay:{i}', 'kind': 'hay', 'source': source, 'title': e['section'] or g.title, 'text': e['text'], 'url': ''}
            for i, e in enumerate(kept, 1)]


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / 'local' / 'دليل-الحيّ.html'
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE / 'local' / 'hay.jsonl'
    rows = build(src)
    dst.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8', newline='\n')
    print(f'{len(rows)} مدخلًا ← {dst}')
