# -*- coding: utf-8 -*-
"""رادار المصادر لبوت سوريا: يرصد كلّ يوم ما وُلد جديدًا من جهاتٍ ومنصّاتٍ رسميّة في سوريا عامّةً وحماة خاصّةً،
في كلّ المجالات، ويفحصه، ويضيف الرسميّ الواضح بلا سؤال (قرار صاحب البوت 2026-11-27)، ويعرض الباقي عليه.

من أين يرصد:
  1. سجلّ شهادات الأمان العامّ (crt.sh) لنطاقَي gov.sy و edu.sy: كلّ موقعٍ حكوميّ جديد يحتاج شهادة، فيظهر فيه
     غالبًا قبل إعلانه (موقع هيئة المعادن الثمينة ظهر فيه قبل إعلانه بشهرين).
  2. ما يجمعه البوت من الأخبار الرسميّة: روابط المواقع والقنوات التي تذكرها، وأخبار «إطلاق منصّة/موقع/تطبيق/قناة»،
     ومراسيم «إحداث هيئة…».
  3. ما زاد اليوم في فهارس الآخرين التي يقرؤها البوت (دليل المواقع والتطبيقات في المساحة السوريّة، جهات سيترا).

كيف يحكم: رسميٌّ؟ (نطاق gov.sy/edu.sy، أو يربطه موقعٌ رسميّ، أو أعلنته جهةٌ رسميّة ووصفُه «رسميّة»)، حيٌّ؟ (نشر
خلال 60 يومًا)، جديدٌ علينا؟، في النطاق؟ (سوريا كلّها ومدينة حماة؛ لا نواحي حماة ولا جهات محافظاتٍ أخرى ولا غير
السوريّة)، وماذا يعطي (أخبار، أو بيانات تحتاج قارئًا يُكتب لها).

ما يفعله:
  - الرسميّ الواضح: قناة تيليغرام أو خلاصة RSS → مصادر الجامع الصامت (sources.json)؛ وكلّ موقعٍ رسميّ حيّ → دليل
    «radar» الذي يقرؤه مستقبِل الأسئلة. لا يُرسل منه شيءٌ إلى المحادثة، ولا يُؤخذ سعرٌ من قناةٍ لم تتأكّد رسميّتها.
  - الضعيف: يُرقَّم ويُعرض في الرسالة الأسبوعيّة، فيردّ صاحب البوت «أضف 2 و5» أو «تجاهل 3» (يلتقطها مستقبِل الأسئلة،
    ويسحبها التشغيل التالي من تطبيق الويب). ما رُفض لا يُعرض ثانيةً، وما بقي بلا ردٍّ أربعة أسابيع يُطوى.
  - مصدرٌ رسميّ جديد لشيءٍ في اللوحة (أسعار، صرف، محروقات) → سطرٌ في نشرة الصباح فورًا (state.radar.urgent).
  - المصادر التي صمتت 45 يومًا تُذكر في الرسالة الأسبوعيّة."""
import html as H, json, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=3))
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36',
      'Accept-Language': 'ar'}
OFFICIAL_TLD = re.compile(r'(^|\.)(gov|edu)\.sy$')
INFRA = {'mail', 'webmail', 'smtp', 'imap', 'pop', 'autodiscover', 'autoconfig', 'cpanel', 'webdisk', 'cpcalendars', 'cpcontacts',
         'whm', 'vpn', 'ftp', 'ns', 'ns1', 'ns2', 'dns', 'mx', 'owa', 'remote', 'test', 'dev', 'staging', 'stage', 'api', 'crm',
         'admin', 'sso', 'auth', 'login', 'cdn', 'static', 'assets', 'storage', 'files', 'exchange', 'lyncdiscover', 'sip', 'zimbra'}
SOCIAL = re.compile(r'(^|\.)(facebook|fb|instagram|twitter|x|youtube|youtu|tiktok|whatsapp|wa|google|goo|forms|gle|apple|t|telegram|'
                    r'linkedin|bit|tinyurl|linktr|threads|snapchat|wikipedia|microsoft|office|live)\.[a-z.]+$')
LAUNCH = re.compile(r'أطلق|إطلاق|اطلاق|منصّ?ة|تطبيق|الموقع الرسمي|الموقع الإلكتروني|موقعها الإلكتروني|القناة الرسمية|قناتها|رابط')
RASMI = re.compile(r'رسمي|الرسمية|الرسميّة|official', re.I)
SYRIA = re.compile(r'سوري|سورية|سوريا|السوري|الجمهورية العربية|حماة|حماه|دمشق|Syria|Hama', re.I)
FOREIGN = re.compile(r'العراق|عراقي|اليمن|يمني|ليبيا|الليبي|الأردن|الأردني|لبنان|اللبناني|مصر\b|المصري|السعودي|فلسطين|تونس|الجزائر|'
                     r'المغرب|السودان|الكويت|قطر\b|الإمارات|Iraq|Yemen|Libya|Jordan|Leban|Egypt|Saudi', re.I)
HAMA = re.compile(r'حماة|حماه|hama', re.I)
# قراره (2026-11-23): صفحات نواحي حماة وحدها لا تُتابع، تكفي أخبارها من الصفحات العامّة
HAMA_COUNTRY = re.compile(r'سلمي|مصياف|محرد|السقيلبي|صوران|مورك|كفر ?زيتا|قمحان|الغاب|طيبة الإمام|حلفايا|اللطامنة|حربنفسه|عقيربات|'
                          r'salam|masyaf|mhardeh|suqaylabiyah|ghab', re.I)
OTHER_GOV = re.compile(r'(?<!\w)(?:حلب|حمص|اللاذقية|طرطوس|إدلب|ادلب|درعا|السويداء|القنيطرة|دير الزور|الرقة|الحسكة|ريف دمشق|دمشق)(?!\w)|'
                       r'\b(?:aleppo|homs|latakia|tartus|idlib|daraa|sweida|quneitra|deir|raqqa|hasakah)\b', re.I)
# جامعةٌ باسم مدينتها جهةٌ وطنيّة (جامعة دمشق)، ومديريّةٌ أو منصّةٌ باسم محافظةٍ أخرى محلّيّةٌ لا تخصّه
NATIONAL = re.compile(r'وزارة|الهيئة العامة|المؤسسة العامة|المركز الوطني|^جامعة|الجمهورية|ministry|^university|national', re.I)
# على edu.sy تُضاف الجامعات الحكوميّة ومنصّات الوزارة وحدها؛ الجامعات والمعاهد الخاصّة ليست جهاتٍ رسميّة (له أن يطلبها)
PUBLIC_EDU = re.compile(r'جامعة (?:دمشق|حلب|تشرين|اللاذقية|البعث|حمص|حماة|حماه|طرطوس|الفرات|إدلب|ادلب|الافتراضية)|الجامعة الافتراضية|'
                        r'المنصة التربوية السورية|وزارة|الهيئة العامة|المعهد العالي للعلوم التطبيقية|'
                        r'(?:damascus|aleppo|tishreen|latakia|albaath|homs|hama|tartous|tartus|alfurat|idlib)-?univ|\bsvu\b|'
                        r'^(?:damascusuniversity|alepuniv|tishreen|albaath-univ|hama-univ|tartous-univ|svuonline|moed|mohe)\.', re.I)
PRIVATE = re.compile(r'الخاص[ةّ]|الخاصّة|private|الدولي[ةّ]|العالمي[ةّ]|international|\bISU\b', re.I)
TIER1 = re.compile(r'وزارة|هيئة|مديرية|مؤسسة|مصرف|جامعة|محافظة|مجلس|نقابة|غرفة|المركز|الإدارة العامة|شركة|صندوق|معهد|دائرة|فرع|'
                   r'ministry|authority|directorate|university|council|bank', re.I)
MEDIA = re.compile(r'إعلام|قناة|إذاعة|تلفزيون|وكالة|صحيفة|جريدة|راديو|news|tv|radio', re.I)
DATA = re.compile(r'open-?data|البيانات المفتوحة|بيانات مفتوحة|نشرة الأسعار|نشرة أسعار|النشرة اليومية|نشرة يومية|المجموعة الإحصائية|'
                  r'لوحة البيانات|dashboard', re.I)
BOARD = re.compile(r'أسعار|سعر|صرف|ذهب|معادن|محروقات|نفط|بنزين|مازوت|غاز|خبز|مصرف|نشرة', re.I)
DECREE = re.compile(r'(?:مرسوم|قرار|قانون)[^\n]{0,80}?إحداث\s+((?:ال)?(?:هيئة|مديرية|مركز|مؤسسة|وزارة|شركة|صندوق|مجلس|معهد|جامعة|'
                    r'مكتب|إدارة|محكمة|دائرة|بنك|مصرف)[^\n،.؛:()]{3,70})')
FIELDS = [   # ترتيبها أولويّة العرض ما لم يحدّد صاحب البوت غيرها في config.json (radar.fields)
    ('إحصاء وبيانات', r'إحصاء|احصاء|بيانات|stat|data|\bcbs\b'),
    ('اتّصالات ودليل', r'اتصال|اتّصال|بريد|هاتف|دليل|نطاق|رقمي|رقميّ|telecom|\bpost|\btra\b|syriatel|mtn|digital|domain'),
    ('تعليم وجامعات', r'تربية|تربوي|تعليم|جامع|كلي|مدرس|معهد|univ|\bedu|school|moed|mohe|\bsvu\b'),
    ('نقل', r'نقل|طرق|مطار|طيران|سكك|مرور|موانئ|ميناء|حدود|منافذ|transport|airport|aviation|rail|traffic|port|border'),
    ('أحوال مدنيّة وهجرة', r'الأحوال المدنية|الأحوال المدنيّة|السجل المدني|هجرة|جواز|civil reg|passport|immigration'),
    ('كهرباء وماء وطاقة', r'كهرباء|مياه|ماء|طاقة|نفط|محروقات|غاز|electric|water|energy|oil|petro|gas'),
    ('صحّة', r'صحة|صحّة|مشف|طبي|طب\b|دواء|صيدل|health|hospital|\bmoh\b|pharma'),
    ('عقار وإسكان', r'عقار|إسكان|اسكان|سكن|مساحة|real ?estate|housing|cadast'),
    ('قضاء وأمن', r'عدل|قضاء|محكم|شرطة|أمن|داخلية|justice|court|interior|police|moi\b'),
    ('عمل وتوظيف', r'توظيف|مسابق|وظائف|تأمينات|العمل\b|labor|labour|job|employ'),
    ('اقتصاد ومال', r'مصرف|بنك|مال|اقتصاد|تجار|استثمار|ضريب|جمارك|معادن|ذهب|أسعار|سوق|مشروعات|مشاريع|تخطيط|صناع|bank|financ|econom|invest|tax|custom|trade|pma'),
    ('زراعة', r'زراع|agri'),
    ('حكم محلّيّ', r'محافظ|مجلس|بلدي|governorate|council|municipal'),
    ('ثقافة وإعلام وسياحة', r'ثقاف|إعلام|سياح|آثار|أوبرا|متحف|مكتبة|culture|media|touris|antiq|opera|museum'),
]
KEEP_SHOWN = 4          # أسابيع يُعرض فيها اقتراحٌ بلا ردّ قبل أن يُطوى
SITES_A_DAY = 70        # حدّ ما يُفحص من المواقع في اليوم، ليبقى التشغيل الساعيّ دون حدّه (15 دقيقة)
SILENT_DAYS = 45


def now():
    return datetime.now(TZ)


def fetch(url, timeout=18, limit=600000):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.geturl(), r.read(limit).decode('utf-8', 'replace')


def host_of(url):
    try:
        h = (urllib.parse.urlsplit(url if '//' in url else '//' + url).hostname or '').lower().rstrip('.')
    except ValueError:
        return ''
    return h[4:] if h.startswith('www.') else h


def base_of(host):
    """aaa.bbb.gov.sy → bbb.gov.sy (الموقع لا خدماته الفرعيّة)."""
    p = host.split('.')
    return '.'.join(p[-3:]) if OFFICIAL_TLD.search(host) and len(p) > 3 else host


def field_of(*texts):
    t = ' '.join(x or '' for x in texts)
    for name, pat in FIELDS:
        if re.search(pat, t, re.I):
            return name
    return 'أخرى'


def scope(title, desc=''):
    """None إن كان في النطاق، وإلّا سبب إخراجه."""
    t = f'{title} {desc}'
    if FOREIGN.search(t) and not SYRIA.search(t):
        return 'ليس سوريًّا'
    if HAMA_COUNTRY.search(title) and not re.search(r'جامعة حماة|جامعة حماه', t):
        return 'ناحيةٌ من ريف حماة'
    if OTHER_GOV.search(title) and not HAMA.search(title) and not NATIONAL.search(title.strip()):
        return 'جهة محافظةٍ أخرى'
    if PRIVATE.search(title):
        return 'جهةٌ خاصّة'
    return None


# ------------------------------------------------------------------ الإشارات
def crt_hosts(timeout=90):
    """أسماء المواقع في سجلّ الشهادات لنطاقَي gov.sy و edu.sy (crt.sh). يتأخّر السجلّ أحيانًا أسابيع، ولا يضرّ: يُعدّ
    الجديد بما لم يُرَ من قبل، لا بتاريخه."""
    out, err = set(), None
    for dom in ('gov.sy', 'edu.sy'):
        body = None
        for i in range(3):                       # crt.sh يردّ كثيرًا بـ 502/503 عابرة
            try:
                _, body = fetch(f'https://crt.sh/?q=%25.{dom}&output=json&exclude=expired', timeout=timeout, limit=30_000_000)
                break
            except Exception as ex:
                err = ex
                time.sleep(5 * (i + 1))
        if body is None:
            continue
        for r in json.loads(body):
            for n in str(r.get('name_value', '')).split('\n'):
                n = n.strip().lower().lstrip('*.').rstrip('.')
                if n.endswith('.' + dom) and n.split('.')[0] not in INFRA:
                    out.add(base_of(n[4:] if n.startswith('www.') else n))
    if not out and err:
        raise err
    return out


HANDLE = re.compile(r'(?:t\.me/|telegram\.me/)(?:s/)?([A-Za-z][A-Za-z0-9_]{4,31})\b|(?<![\w@.])@([A-Za-z][A-Za-z0-9_]{4,31})\b')
URL = re.compile(r'https?://[^\s<>"\'()\]]+|(?<![\w@/.])(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:gov|edu)\.sy\b[^\s<>"\'()]*', re.I)
NOT_HANDLE = {'joinchat', 'share', 'addstickers', 'proxy', 'iv', 'contact', 'boost', 'gmail', 'hotmail', 'yahoo', 'outlook'}


def from_post(r):
    """قنوات تيليغرام ومواقع يذكرها منشور: [(نوع، قيمة)]."""
    text = r.get('text', '') + '\n' + '\n'.join(r.get('links') or [])
    out = []
    for m in HANDLE.finditer(text):
        h = (m.group(1) or m.group(2)).lower()
        if h not in NOT_HANDLE and not h.endswith('bot'):
            out.append(('tg', h))
    for m in URL.finditer(text):
        u = m.group(0).rstrip('.,،؛:')
        h = host_of(u)
        if h and '.' in h and not SOCIAL.search(h) and not h.endswith('t.me'):
            out.append(('site', base_of(h)))
    return out


def tg_info(handle):
    """معاينة قناة: {title, desc, last (طابع آخر منشور), channel} أو None إن لم تكن قناةً لها منشورات."""
    _, page = fetch(f'https://t.me/s/{handle}')
    dates = re.findall(r'<time datetime="([^"]+)"', page)
    if not dates or 'tgme_channel_info' not in page:
        return None
    g = lambda pat: H.unescape(re.sub(r'<[^>]+>', ' ', (re.search(pat, page, re.S) or [0, ''])[1])).strip()
    try:
        last = max(datetime.fromisoformat(d).timestamp() for d in dates)
    except ValueError:
        last = 0
    return {'title': re.sub(r'\s+', ' ', g(r'<div class="tgme_channel_info_header_title"[^>]*>(.*?)</div>'))[:120],
            'desc': re.sub(r'\s+', ' ', g(r'<div class="tgme_channel_info_description"[^>]*>(.*?)</div>'))[:400], 'last': last}


def site_info(host):
    """الصفحة الأولى لموقع: {title, rss, tg: [قنوات يربطها], data, url} أو None إن لم يُجب."""
    for scheme in ('https://', 'http://'):
        try:
            url, page = fetch(scheme + host + '/')
            break
        except Exception:
            url = page = None
    if page is None:
        return None
    title = H.unescape(re.sub(r'\s+', ' ', (re.search(r'<title[^>]*>(.*?)</title>', page, re.S | re.I) or [0, ''])[1])).strip()[:150]
    rss = re.search(r'<link[^>]+type="application/(?:rss|atom)\+xml"[^>]*>', page, re.I)
    rss = rss and re.search(r'href="([^"]+)"', rss.group(0))
    rss = urllib.parse.urljoin(url, H.unescape(rss.group(1))) if rss else None
    tg = sorted({m.lower() for m in re.findall(r'(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z][A-Za-z0-9_]{4,31})', page)} - NOT_HANDLE)
    return {'title': title, 'rss': rss, 'tg': tg[:6], 'data': bool(DATA.search(page)), 'url': url,
            'board': bool(BOARD.search(title))}


# ------------------------------------------------------------------ ما نعرفه
def known(base, srcs):
    hosts, tg = set(), {s['id'].lower() for s in srcs.get('telegram', [])}
    for s in srcs.get('rss', []):
        hosts.add(base_of(host_of(s['url'])))
    for f in (Path(base) / 'directory').glob('*.jsonl'):
        for line in f.read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            blob = r.get('text', '') + ' ' + r.get('url', '')
            for m in URL.finditer(blob):
                h = host_of(m.group(0))
                if h and not SOCIAL.search(h):
                    hosts.add(base_of(h))
    return hosts, tg


def recent_news(base, since_ts):
    out = []
    for f in sorted((Path(base) / 'news').glob('*.jsonl'))[-3:]:
        for line in f.read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get('ts', 0) > since_ts:
                out.append(r)
    return out


def dir_rows(base, kinds=('site', 'app', 'entity')):
    rows = {}
    for k in kinds:
        f = Path(base) / 'directory' / f'{k}.jsonl'
        if f.exists():
            for line in f.read_text(encoding='utf-8').splitlines():
                try:
                    r = json.loads(line)
                    rows[r['id']] = r
                except (ValueError, KeyError):
                    pass
    return rows


# ------------------------------------------------------------------ اليوم
def daily(base, state, srcs, t=None, crt=crt_hosts, tg_lookup=tg_info, site_lookup=site_info, workers=12):
    """يرصد ويحكم ويضيف. يعيد {'sources': srcs_changed?, 'log': سطر للسجلّ}. أوّل تشغيلٍ يأخذ ما في السجلّات والفهارس
    أساسًا: المواقع الرسميّة التي لا نعرفها تُفحص وتُضاف (اكتشافٌ أوّل)، والقنوات القديمة في الأخبار تُعدّ معروفة."""
    t = t or now()
    R = state.setdefault('radar', {})
    first = 'day' not in R
    seen_h, seen_t, rejected = set(R.get('seen_hosts', [])), set(R.get('seen_tg', [])), set(R.get('rejected', []))
    hosts, tgs = known(base, srcs)
    seen_h |= hosts
    seen_t |= tgs
    pending = R.setdefault('pending', {})
    in_pending = {c['key'] for c in pending.values()}
    later = R.setdefault('later', {})                  # مواقع ردّت بصفحةٍ افتراضيّة أو «قريبًا»: تُعاد بعد أسبوعين
    wait_until = f'{t - timedelta(days=14):%Y-%m-%d}'
    for h, d in list(later.items()):
        if d <= wait_until:
            later.pop(h)
    seen_h |= set(later)
    cands = {}                                     # key → {kind, value, via, url, proof}

    def add(kind, value, via, url='', proof=0):
        key = f'{kind}:{value}'
        if key in rejected or key in in_pending:
            return
        if (kind == 'site' and value in seen_h) or (kind == 'tg' and value in seen_t):
            return
        c = cands.setdefault(key, {'key': key, 'kind': kind, 'value': value, 'via': via, 'url': url, 'proof': proof})
        if proof > c['proof']:
            c.update(via=via, url=url, proof=proof)

    log = []
    # 1. سجلّ الشهادات
    try:
        ch = crt()
        for h in sorted(ch):
            add('site', h, 'سجلّ شهادات الأمان', 'https://' + h, 2)
        log.append(f'crt {len(ch)}')
    except Exception as ex:
        log.append(f'crt failed: {type(ex).__name__}')
    # 2. الأخبار الرسميّة منذ آخر يوم
    since = R.get('news_ts', t.timestamp() - (3 if first else 1.2) * 86400)
    posts = [r for r in recent_news(base, since) if r.get('tier', 3) <= 2]
    bodies = R.setdefault('bodies', [])
    for r in posts:
        launch, tier1 = bool(LAUNCH.search(r.get('text', ''))), r.get('tier') == 1 and not r.get('uv')
        for kind, v in from_post(r):
            if kind == 'tg' and not first:
                add('tg', v, f'ذكرته {r.get("name", "")}', r.get('url', ''), 2 if tier1 else 1)
            elif kind == 'site' and (OFFICIAL_TLD.search(v) or (launch and not first)):
                add('site', v, f'ذكره خبرٌ من {r.get("name", "")}', r.get('url', ''), 2 if OFFICIAL_TLD.search(v) else 1)
        for m in DECREE.finditer(r.get('text', '')):
            name = re.sub(r'\s+', ' ', m.group(1)).strip()
            if name not in {b['name'] for b in bodies}:
                bodies.append({'name': name, 'url': r.get('url', ''), 'src': r.get('name', ''), 'day': f'{t:%Y-%m-%d}'})
    R['news_ts'] = max([since] + [r.get('ts', 0) for r in posts])
    # 3. الجديد في الفهارس
    rows = dir_rows(base)
    old_ids = set(R.get('dir_ids', []))
    if old_ids:
        for rid, r in rows.items():
            if rid not in old_ids:
                for kind, v in from_post({'text': r.get('text', '') + ' ' + r.get('url', '')}):
                    add(kind, v, f'جديدٌ في {r.get("source", "فهرس")}', r.get('url', ''), 2 if kind == 'site' and OFFICIAL_TLD.search(v) else 1)
    R['dir_ids'] = sorted(rows)

    # الفحص: المواقع أوّلًا (فما تربطه من قنوات يصير دليلًا رسميًّا عليها)
    sites = sorted((c for c in cands.values() if c['kind'] == 'site'), key=lambda c: -c['proof'])
    sites = sites[:SITES_A_DAY]                    # ما زاد يبقى غير مرئيّ، فيُفحص في الأيّام التالية (أوّل تشغيلٍ أطول)
    with ThreadPoolExecutor(workers) as ex:
        infos = list(ex.map(lambda c: safe(site_lookup, c['value']), sites))
    added, needs_reader, urgent, radar_rows = R.setdefault('added', []), R.setdefault('needs_reader', []), R.setdefault('urgent', []), []
    changed = False
    for c, info in zip(sites, infos):
        seen_h.add(c['value'])
        if not info:                                            # لم يُجب: يُعاد بعد أسبوعين
            seen_h.discard(c['value'])
            later[c['value']] = f'{t:%Y-%m-%d}'
            continue
        name = info['title'] or c['value']
        if junk(name, c['value'], info['url']):
            seen_h.discard(c['value'])                          # لم يكتمل بعد: يُعاد فحصه بعد أسبوعين
            later[c['value']] = f'{t:%Y-%m-%d}'
            continue
        why = scope(name)
        if why:
            continue
        if c['value'].endswith('edu.sy') and not PUBLIC_EDU.search(name + ' ' + c['value']):
            continue                                            # جامعةٌ أو معهدٌ خاصّ: ليس جهةً رسميّة
        official = bool(OFFICIAL_TLD.search(c['value']))
        fld = field_of(name, c['value'])
        if official:
            radar_rows.append(dir_entry(c['value'], name, fld, info, t))
            item = {'name': name, 'field': fld, 'link': info['url'], 'via': c['via'], 'day': f'{t:%Y-%m-%d}', 'what': 'موقع'}
            if info['rss'] and host_of(info['rss']) and base_of(host_of(info['rss'])) == c['value']:
                if add_rss(srcs, c['value'], name, info['rss'], hama=bool(HAMA.search(name))):
                    changed = True
                    item['what'] = 'موقع وخلاصته (RSS)'
            added.append(item)
            for h in info['tg']:
                add('tg', h, f'يربطها موقع {name}', info['url'], 3)
            if info['data']:
                needs_reader.append({'name': name, 'field': fld, 'link': info['url'], 'day': f'{t:%Y-%m-%d}'})
                if info['board']:
                    urgent.append({'name': name, 'link': info['url']})
        elif c['proof'] >= 1:
            propose(R, c, name, fld, info['url'])

    chans = [c for c in cands.values() if c['kind'] == 'tg']
    with ThreadPoolExecutor(workers) as ex:
        tinfos = list(ex.map(lambda c: safe(tg_lookup, c['value']), chans))
    for c, info in zip(chans, tinfos):
        seen_t.add(c['value'])
        if not info or t.timestamp() - (info['last'] or 0) > 60 * 86400:
            continue                                            # ليست قناة، أو صامتة منذ شهرين
        if scope(info['title'], info['desc']):
            continue
        fld = field_of(info['title'], info['desc'])
        strong = c['proof'] >= 3 or (c['proof'] >= 2 and RASMI.search(info['title'] + ' ' + info['desc']))
        if strong:
            if add_tg(srcs, c['value'], info, verified=c['proof'] >= 3):
                changed = True
                added.append({'name': info['title'] or c['value'], 'field': fld, 'link': f'https://t.me/{c["value"]}', 'via': c['via'],
                              'day': f'{t:%Y-%m-%d}', 'what': 'قناة تيليغرام'})
        else:
            propose(R, c, info['title'] or '@' + c['value'], fld, f'https://t.me/{c["value"]}', info.get('desc', ''))

    if radar_rows:
        write_dir(base, radar_rows)
    R['seen_hosts'], R['seen_tg'] = sorted(seen_h), sorted(seen_t)
    R['day'] = f'{t:%Y-%m-%d}'
    log.append(f'{len(cands)} new candidate(s), {sum(1 for a in added if a["day"] == R["day"])} added, {len(pending)} waiting')
    return {'sources': changed, 'log': ', '.join(log)}


JUNK = re.compile(r'default|index of|it works|welcome to nginx|apache|iis windows|coming soon|under construction|قريبا|قريبًا|قيد الإنشاء|'
                  r'تحت الإنشاء|login|log in|sign in|تسجيل الدخول|webutil|frmservlet|\berp\b|xmpp|^home$|^test|^الرئيسية$', re.I)


def junk(title, host, url=''):
    """صفحةٌ افتراضيّة أو قيد الإنشاء أو بوّابة دخول، أو بلا عنوانٍ يدلّ على جهة."""
    t = (title or '').strip()
    if not t or t.lower() in (host, 'www.' + host) or JUNK.search(t) or JUNK.search(urllib.parse.urlsplit(url).path or ''):
        return True
    return not re.search(r'[؀-ۿ]', t) and not TIER1.search(t)


def safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


def propose(R, c, name, fld, link, desc=''):
    n = R.get('next_num', 1)
    R['next_num'] = n + 1
    R['pending'][str(n)] = {'key': c['key'], 'kind': c['kind'], 'value': c['value'], 'name': name[:120], 'field': fld, 'link': link,
                            'via': c['via'], 'via_url': c.get('url', ''), 'desc': desc[:200], 'shown': 0}


def kind_of(title):
    return 'إعلام' if MEDIA.search(title) and not TIER1.search(title) else 'جهة رسميّة'


def add_tg(srcs, handle, info, verified):
    if any(s['id'].lower() == handle for s in srcs['telegram']):
        return False
    title = info.get('title') or handle
    e = {'id': handle, 'name': title, 'kind': kind_of(title), 'tier': 2 if kind_of(title) == 'إعلام' else 1,
         'hama': bool(HAMA.search(title + ' ' + info.get('desc', ''))), 'radar': f'{now():%Y-%m-%d}'}
    if not verified:
        e['unverified'] = True            # تُجمع وتُقرأ، ولا يُؤخذ منها سعر
    srcs['telegram'].append(e)
    return True


def add_rss(srcs, host, name, url, hama=False):
    if any(base_of(host_of(s['url'])) == host for s in srcs['rss']):
        return False
    srcs['rss'].append({'id': re.sub(r'[^a-z0-9]+', '_', host.split('.')[0]) or host, 'name': name[:80], 'kind': 'جهة رسميّة', 'tier': 1,
                        'hama': hama, 'url': url, 'radar': f'{now():%Y-%m-%d}'})
    return True


def dir_entry(host, name, fld, info, t):
    text = (f'{fld} · موقعٌ رسميّ رصده البوت يوم {t:%Y-%m-%d} · الموقع: {info["url"]}'
            + (f' · قناته على تيليغرام: ' + '، '.join('https://t.me/' + h for h in info['tg']) if info['tg'] else '')
            + (' · فيه بيانات (نشرات أو أرقام)' if info['data'] else ''))
    return {'id': 'radar:' + host, 'kind': 'radar', 'source': 'رادار المصادر', 'title': name, 'text': text, 'url': info['url']}


def write_dir(base, rows):
    f = Path(base) / 'directory' / 'radar.jsonl'
    cur = {}
    if f.exists():
        for line in f.read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(line)
                cur[r['id']] = r
            except (ValueError, KeyError):
                pass
    for r in rows:
        cur[r['id']] = r
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in cur.values()), encoding='utf-8', newline='\n')


def save_sources(path, srcs, eol_from=None):
    """يكتب sources.json بتنسيقه نفسه (مسافةٌ واحدة، ونهايات أسطره كما هي)، فلا يتغيّر في الفرق إلّا المضاف."""
    ref = Path(path) if Path(path).exists() else Path(eol_from or path)
    crlf = ref.exists() and b'\r\n' in ref.read_bytes()
    out = json.dumps(srcs, ensure_ascii=False, indent=1)
    Path(path).write_bytes((out.replace('\n', '\r\n') if crlf else out).encode('utf-8'))


# ------------------------------------------------------------------ الموافقة
NUMS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def apply(state, srcs, decisions, base, tg_lookup=tg_info, site_lookup=site_info):
    """decisions: [{id, op: add|skip, n: [أرقام]}] كما سحبها التشغيل من تطبيق الويب. يعيد (نصّ رسالة أو None، تغيّرت المصادر؟)."""
    R = state.setdefault('radar', {})
    pend, done, skipped, missing, changed = R.setdefault('pending', {}), [], [], [], False
    for d in decisions:
        for n in d.get('n', []):
            n = str(n).translate(NUMS)
            c = pend.pop(n, None)
            if not c:
                missing.append(n)
                continue
            if d.get('op') == 'skip':
                R.setdefault('rejected', []).append(c['key'])
                skipped.append(c['name'])
                continue
            if c['kind'] == 'tg':
                info = safe(tg_lookup, c['value']) or {'title': c['name'], 'desc': c.get('desc', '')}
                changed |= add_tg(srcs, c['value'], info, verified=False)
            else:
                info = safe(site_lookup, c['value'])
                if info:
                    write_dir(base, [dir_entry(c['value'], c['name'], c['field'], info, now())])
                    if info['rss']:
                        changed |= add_rss(srcs, c['value'], c['name'], info['rss'])
            R.setdefault('added', []).append({'name': c['name'], 'field': c['field'], 'link': c['link'], 'via': 'بموافقتك',
                                              'day': f'{now():%Y-%m-%d}', 'what': 'قناة تيليغرام' if c['kind'] == 'tg' else 'موقع'})
            done.append(c['name'])
    if not (done or skipped or missing):
        return None, changed
    L = ['🛰 <b>رادار المصادر</b>']
    if done:
        L.append('✅ أُضيف بموافقتك:\n' + '\n'.join('• ' + H.escape(x) for x in done))
    if skipped:
        L.append('🚫 لن يُعرض ثانيةً:\n' + '\n'.join('• ' + H.escape(x) for x in skipped))
    if missing:
        L.append('❔ لا اقتراح بالرقم ' + '، '.join(missing) + ' (قد يكون طُوي أو حُسم).')
    return '\n\n'.join(L), changed


def pull(url, key, ack=None, timeout=60):
    """يسحب ردود «أضف/تجاهل» من تطبيق الويب (ack: معرّفات ما طُبّق لتُحذف هناك)."""
    body = {'key': key, 'radar_pull': True}
    if ack:
        body['radar_ack'] = ack
    req = urllib.request.Request(url, json.dumps(body).encode('utf-8'), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.loads(r.read().decode('utf-8'))
    if not out.get('ok'):
        raise RuntimeError(out.get('error') or 'رفض تطبيق الويب')
    return out.get('radar') or []


# ------------------------------------------------------------------ الرسالة الأسبوعيّة
def silent_sources(base, srcs, t, days=SILENT_DAYS):
    files = sorted((Path(base) / 'news').glob('*.jsonl'))
    if not files or files[0].stem > f'{t - timedelta(days=days):%Y-%m-%d}':
        return []                                   # الأرشيف أقصر من المدّة: لا حكم بعد
    last = {}
    for f in files:
        for line in f.read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            last[r.get('src')] = max(last.get(r.get('src'), 0), r.get('ts', 0))
    cut = t.timestamp() - days * 86400
    out = []
    for s in srcs.get('telegram', []) + srcs.get('rss', []):
        if s.get('radar') and s['radar'] > f'{t - timedelta(days=days):%Y-%m-%d}':
            continue
        if last.get(s['id'], 0) < cut:
            out.append(s['name'])
    return out


def order(items, prio):
    rank = {f: i for i, f in enumerate(prio)}
    return sorted(items, key=lambda x: rank.get(x.get('field'), len(rank)))


def weekly(state, srcs, base, cfg, t=None):
    """نصّ الرسالة الأسبوعيّة، ثمّ تُفرَّغ قوائم الأسبوع. None إن لم يحن موعدها."""
    t = t or now()
    R = state.setdefault('radar', {})
    rc = cfg.get('radar') or {}
    week = f'{t:%G-W%V}'
    if t.weekday() != rc.get('weekday', 4) or t.hour < cfg.get('bulletin_hour', 7) or R.get('week') == week or 'day' not in R:
        return None
    prio = rc.get('fields') or [f for f, _ in FIELDS]
    added, needs, bodies = order(R.get('added', []), prio), order(R.get('needs_reader', []), prio), R.get('bodies', [])
    pend = R.get('pending', {})
    for n in list(pend):
        pend[n]['shown'] = pend[n].get('shown', 0) + 1
    shown = sorted(pend.items(), key=lambda kv: ({f: i for i, f in enumerate(prio)}.get(kv[1]['field'], 99), int(kv[0])))
    silent = silent_sources(base, srcs, t)
    a = lambda x: f'<a href="{H.escape(x["link"])}">{H.escape(x["name"])}</a>'
    L = [f'🛰 <b>رادار المصادر · أسبوع {t:%d-%m}</b>']
    if not (added or needs or bodies or pend or silent):
        L.append('لا جديد هذا الأسبوع: لم تظهر جهةٌ رسميّة جديدة، ولم تصمت أيّ مصدر.')
    if added:
        L.append(f'✅ <b>أُضيف تلقائيًّا ({len(added)})</b> · يجمع البوت أخباره بصمت ويجيب عنه\n<blockquote expandable>'
                 + '\n'.join(f'• {a(x)} · {x["field"]} · {x["what"]}' for x in added) + '</blockquote>')
    if shown:
        ns = [n for n, _ in shown]
        hint = f'«أضف {ns[0]} و{ns[1]}» أو «تجاهل {ns[-1]}»' if len(ns) > 1 else f'«أضف {ns[0]}» أو «تجاهل {ns[0]}»'
        L.append(f'🗳 <b>يحتاج موافقتك ({len(shown)})</b> · ردّ: {hint}\n<blockquote expandable>'
                 + '\n'.join(f'{n}. {a(c)} · {c["field"]}\n   {H.escape(c["via"])}' + (f' · {H.escape(c["desc"][:90])}' if c.get('desc') else '')
                             for n, c in shown) + '</blockquote>')
    if needs:
        L.append(f'🧩 <b>فيه بيانات تحتاج قارئًا يُكتب لها ({len(needs)})</b> · أطلب من Claude إن أردت أن تدخل اللوحة\n<blockquote expandable>'
                 + '\n'.join(f'• {a(x)} · {x["field"]}' for x in needs) + '</blockquote>')
    if bodies:
        L.append(f'🏛 <b>جهاتٌ أُحدثت بمرسوم أو قرار ({len(bodies)})</b> · أراقبها حتّى يظهر لها موقعٌ أو قناة\n<blockquote expandable>'
                 + '\n'.join(f'• <a href="{H.escape(b["url"])}">{H.escape(b["name"])}</a>' for b in bodies) + '</blockquote>')
    if silent:
        L.append(f'💤 <b>مصادر صامتة منذ {SILENT_DAYS} يومًا ({len(silent)})</b>\n<blockquote expandable>' + '\n'.join('• ' + H.escape(x) for x in silent)
                 + '</blockquote>')
    # بعد الإرسال: ما عُرض أربع مرّاتٍ بلا ردّ يُطوى (يبقى في «ما رأيناه» فلا يُقترح ثانيةً)
    for n in [n for n, c in pend.items() if c['shown'] >= KEEP_SHOWN]:
        pend.pop(n)
    R['added'], R['needs_reader'], R['bodies'], R['week'] = [], [], [], week
    return '\n\n'.join(L)


if __name__ == '__main__':      # تجربة على الحاسوب: python radar.py [--dry]  (لا يكتب شيئًا مع --dry)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    base = Path(__file__).resolve().parent
    srcs = json.loads((base / 'sources.json').read_text(encoding='utf-8'))
    st = json.loads((base / 'state.json').read_text(encoding='utf-8'))
    if '--dry' in sys.argv:
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        shutil.copytree(base / 'directory', tmp / 'directory')
        shutil.copytree(base / 'news', tmp / 'news')
        base = tmp
    res = daily(base, st, srcs)
    R = st['radar']
    print(res['log'])
    print(json.dumps({'added': R.get('added'), 'pending': R.get('pending'), 'needs_reader': R.get('needs_reader'),
                      'bodies': R.get('bodies'), 'urgent': R.get('urgent'), 'new_tg': [s for s in srcs['telegram'] if s.get('radar')],
                      'new_rss': [s for s in srcs['rss'] if s.get('radar')]}, ensure_ascii=False, indent=1))
    cfg = json.loads((Path(__file__).resolve().parent / 'config.json').read_text(encoding='utf-8'))
    R['week'] = None
    fri = now() + timedelta(days=(4 - now().weekday()) % 7)
    print('\n----- weekly preview -----\n' + (weekly(st, srcs, base, cfg, fri.replace(hour=9)) or 'none'))
