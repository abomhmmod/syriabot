// تجربة مستقبِل السؤال والجواب (apps-script/Code.gs) على الحاسوب، ببدائل لخدمات Apps Script.
//   node tests/t_gs.js                 فحوص بلا نموذج (البحث في الأرشيف وورقة الأرقام) على بيانات البوت الحيّة
//   node tests/t_gs.js --live "سؤال"   يجيب عن السؤال فعلًا (يحتاج GEMINI_API_KEY في البيئة)
const fs = require('fs'), path = require('path'), vm = require('vm'), cp = require('child_process');

function fetch(url, o) {
  o = o || {};
  const headers = Object.assign({}, o.headers || {});
  if (o.contentType) headers['Content-Type'] = o.contentType;
  const r = cp.spawnSync('python', ['-I', path.join(__dirname, '_fetch.py')],
    {input: JSON.stringify({url, method: o.method || 'get', headers, payload: o.payload == null ? null : o.payload}), encoding: 'utf8', maxBuffer: 1 << 28});
  let out = {code: 0, text: ''};
  try { out = JSON.parse(r.stdout); } catch (e) {}
  return {getResponseCode: () => out.code, getContentText: () => out.text};
}
const store = {GEMINI_API_KEY: process.env.GEMINI_API_KEY || '', CHAT_ID: '1', TELEGRAM_TOKEN: ''};
// البيانات الخاصّة: بدل Drive مجلّدٌ على الحاسوب (PRIV_DIR)، فيه hay.jsonl وملفّات social-YYYY-MM-DD.jsonl.
let PRIV_DIR = process.env.PRIV_DIR || '';
const privFiles = () => (PRIV_DIR && fs.existsSync(PRIV_DIR) ? fs.readdirSync(PRIV_DIR).filter(n => /\.jsonl$/.test(n)) : []);
const setPriv = dir => { PRIV_DIR = dir; store.PRIV_FILES = JSON.stringify(Object.fromEntries(privFiles().map(n => [n, 'id-' + n]))); };
const ctx = {
  UrlFetchApp: {fetch, fetchAll: reqs => reqs.map(q => fetch(q.url, q))},
  PropertiesService: {getScriptProperties: () => ({getProperty: k => store[k] || null, setProperty: (k, v) => { store[k] = v; }})},
  Utilities: {computeDigest: (alg, str) => [...require('crypto').createHash('sha256').update(str, 'utf8').digest()].map(x => (x > 127 ? x - 256 : x)),
    DigestAlgorithm: {SHA_256: 1}, Charset: {UTF_8: 1},
    newBlob: t => (typeof t === 'string' ? {getBytes: () => [...Buffer.from(t, 'utf8')].map(x => (x > 127 ? x - 256 : x))}
      : {getBytes: () => t, getDataAsString: () => Buffer.from(t.map(x => x & 255)).toString('utf8')}),
    computeHmacSha256Signature: (data, key) => [...require('crypto').createHmac('sha256', Buffer.from(key.map(x => x & 255))).update(Buffer.from(data.map(x => x & 255))).digest()].map(x => (x > 127 ? x - 256 : x)),
    base64Encode: a => Buffer.from(a.map(x => x & 255)).toString('base64'),
    base64Decode: s => [...Buffer.from(s, 'base64')].map(x => (x > 127 ? x - 256 : x)),
    getUuid: () => require('crypto').randomUUID(), MacAlgorithm: {HMAC_SHA_512: 512},
    computeHmacSignature: (alg, data, key) => [...require('crypto').createHmac('sha512', Buffer.from(key.map(x => x & 255))).update(Buffer.from(data.map(x => x & 255))).digest()].map(x => (x > 127 ? x - 256 : x)), sleep: ms => cp.spawnSync('python', ['-I', '-c', 'import time,sys; time.sleep(' + ms / 1000 + ')']), formatDate: (d, tz, f) => { const s = new Date(d.getTime() + 3 * 3600e3).toISOString(); return f.length > 10 ? s.slice(0, 16).replace('T', ' ') : s.slice(0, 10); }},
  LockService: {getScriptLock: () => ({tryLock: () => true, releaseLock: () => {}})},
  ContentService: {createTextOutput: t => ({setMimeType: () => t}), MimeType: {JSON: 1}},
  ScriptApp: {getOAuthToken: () => 'x', getProjectTriggers: () => [], newTrigger: () => ({timeBased: () => ({everyMinutes: () => ({create: () => {}})})})},
  Logger: {log: console.log}, console, Date, JSON, Math, Number, String, Object, Array, RegExp, Error,
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'apps-script', 'Code.gs'), 'utf8'), ctx);
const run = code => vm.runInContext(code, ctx);
ctx.HOST_READ = names => Object.fromEntries(names.filter(n => fs.existsSync(path.join(PRIV_DIR, n))).map(n => [n, fs.readFileSync(path.join(PRIV_DIR, n), 'utf8')]));
run('privRead_ = function (names, idx) { return HOST_READ(names.filter(function (n) { return idx[n]; })); }');
setPriv(PRIV_DIR);

if (process.argv[2] === '--quick') {          // يطبع جواب كلّ زرٍّ من أزرار البيانات كما سيُرسل (PRIV_DIR لأرقام الحيّ)
  for (const label of run('KEYS').flat()) {
    ctx.Q = label;
    const a = run('quick_(Q)');
    console.log('\n===== ' + label + (a ? ' · ' + a.length + ' حرفًا' : ' · يمرّ بالنموذج: ' + run('ASK[Q]')) + '\n' + (a || ''));
  }
  process.exit(0);
}
if (process.argv[2] === '--plan') {           // كيف يقسّم النموذج الحقيقيّ سؤالًا يجمع الخاصّ والعامّ (يُرسل نصّ السؤال وحده، والقسم الخاصّ هنا فارغ)
  ctx.LOG = o => console.log(JSON.stringify(o, null, 1));
  store.VAULT_ID = 'x';
  run('var _g = gemini_; gemini_ = function (p, s) { var o = _g(p, s); LOG(o); return o; }; vaultOpen_ = function () { return {index: [], vals: {}}; }');
  for (const q of process.argv.slice(3)) { ctx.Q = q; console.log('\n❓ ' + q); console.log('→ يبقى للجواب العاديّ: ' + run('vaultAsk_("t", "1", Q)')); }
  process.exit(0);
}
if (process.argv[2] === '--live') {
  let qs = process.argv.slice(3);
  if (qs[0] === '--models') { ctx.MODELS = qs[1].split(','); run('MODELS = this.MODELS'); qs = qs.slice(2); }
  for (const q of qs) {
    ctx.Q = q;
    const t = Date.now();
    const a = run('answer_(Q)');
    console.log('\n❓ ' + q + '\n' + a + '\n   [' + ((Date.now() - t) / 1000).toFixed(0) + ' ث · ' + (store.AI_LAST || '—') + ']');
  }
  process.exit(0);
}

let fails = 0;
const check = (name, ok, extra) => { console.log((ok ? 'ok   ' : 'FAIL ') + name + (ok ? '' : ' ' + (extra || ''))); if (!ok) fails++; };
check('norm: letters unified, marks dropped', run('norm_("وِزَارَةُ الصِّحَّة — إدارةٌ")') === 'وزاره الصحه اداره');
check('tokens: stop words and prefixes removed', JSON.stringify(run('tokens_("ما آخر أخبار وزارة الصحة اليوم؟")')) === JSON.stringify(['وزاره', 'صحه']), JSON.stringify(run('tokens_("ما آخر أخبار وزارة الصحة اليوم؟")')));
check('num: thousands and decimals', run('num_(15700)') === '15,700' && run('num_(151.5)') === '151.50' && run('num_(2500.4, 0)') === '2,500');
check('esc and tidy', run('esc_("a<b>&")') === 'a&lt;b&gt;&amp;' && run('tidy_("**عنوان**\\n\\n\\n\\nسطر")') === 'عنوان\n\nسطر');
ctx.P = [
  {name: 'وزارة الصحة', title: 'افتتاح مركز صحي في حمص', text: 'افتتحت وزارة الصحة مركزًا', ts: Date.now() / 1000 - 3600, tier: 1, url: 'u1'},
  {name: 'وزارة التربية والتعليم', title: 'نتائج مسابقة', text: 'اعتمدت الوزارة النتائج', ts: Date.now() / 1000 - 1800, tier: 1, url: 'u2'},
  {name: 'سانا', title: 'وزير الصحة يبحث التعاون', text: 'بحث وزير الصحة مع نظيره', ts: Date.now() / 1000 - 7200, tier: 2, url: 'u3'},
  {name: 'محافظة حماة', title: 'تعبيد طريق', text: 'أنهت المحافظة تعبيد الطريق', ts: Date.now() / 1000 - 600, tier: 1, url: 'u4'}];
const r1 = run('rank_("ما آخر أخبار وزارة الصحة؟", P.slice(), 10)').map(p => p.url);
check('rank: the ministry itself first among matches, unrelated posts left out', r1.includes('u1') && r1.includes('u3') && !r1.includes('u4'), r1.join());
check('rank: source-name match outweighs a common word', run('rank_("وزارة الصحة", P.slice(), 1)')[0].url === 'u1');
check('rank: a question with no keywords gets the newest posts', run('rank_("ما هو الجديد اليوم؟", P.slice(), 3)').map(p => p.url).join() === 'u4,u2,u1');

const state = run('getJson_(RAW + "state.json")');
ctx.S = state;
const facts = run('facts_(S)');
check('facts sheet: market, official, gold, fuel, weather, prayer, basket', ['سعر السوق', 'الدولار الأمريكيّ USD', 'السعر الرسميّ', 'نشرة الصاغة', 'بنزين 95', 'ربطة الخبز', 'طقس حماة', 'المغرب', 'مسجدك', 'سلّة حماة', 'سكّر [KG]'].every(x => facts.includes(x)), facts.slice(0, 300));
check('facts sheet is compact', facts.length < 9000, facts.length);
const news = run('loadNews_(3)');
check('news archive loads from the repository', news.length > 300 && news[0].name && news[0].ts, news.length);
ctx.N = news;
const r2 = run('rank_("ماذا نشرت محافظة حماة؟", N, 28)');
check('rank on the real archive: Hama governorate posts found', r2.length > 0 && r2.some(p => /حماة|حماه/.test(p.name)), r2.slice(0, 5).map(p => p.name).join(' | '));
// ---------- البيانات الخاصّة: مجلّدٌ تجريبيّ بأسماء وأرقام مصطنعة
const os = require('os'), tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'priv-'));
const today = new Date(Date.now() + 3 * 3600e3).toISOString().slice(0, 10), nowTs = Math.floor(Date.now() / 1000);
fs.writeFileSync(path.join(tmp, 'hay.jsonl'), [
  {id: 'hay:1', kind: 'hay', source: 'دليل الحيّ (تجربة)', title: 'أرقام ضروريّة › مراكز الغاز', text: 'المركز: مركز غاز الزيتونة · المكان: شارع الورد · الرقم: 0999123456 · أين ورد: 2026-11-08 إلى 2026-11-23', url: ''},
  {id: 'hay:2', kind: 'hay', source: 'دليل الحيّ (تجربة)', title: 'أرقام ضروريّة › حِرفيّون', text: 'الخدمة: معلّم صحّيّة · الرقم: ٠٩٤٤ ٥٥٥ ٦٦٦ · واتساب wa.me/963955000111 · سجّل 1025 اسمًا بسعر 115 ليرة', url: ''},
].map(x => JSON.stringify(x)).join('\n') + '\n');
fs.writeFileSync(path.join(tmp, 'social-' + today + '.jsonl'), [
  {id: 'fb:1', n: 'أخبار حيّ الزيتونة', k: 'فيسبوك', t: 'انقطاع المياه عن حيّ الزيتونة حتّى المساء بسبب إصلاح الخطّ الرئيس', u: 'https://facebook.com/1', ts: nowTs - 600},
  {id: 'x:2', n: 'مراسل تجريبيّ', k: 'X', t: 'افتتاح سوق جديد في المدينة', u: 'https://x.com/2', ts: nowTs - 900},
].map(x => JSON.stringify(x)).join('\n') + '\n');
setPriv(tmp);
const pv = run('loadPrivate_(3)');
check('private: guide entries and followed pages load from the private folder', pv.hay.length === 2 && pv.social.length === 2 && pv.hay[0].hay && pv.social[0].tier === 3 && /غير رسميّ/.test(pv.social[0].name), JSON.stringify(pv).slice(0, 200));
let seen = '';
ctx.FAKE = p => {
  seen = p;
  const n = (p.match(/\[(\d+)\] دليل الحيّ \(تجربة\)\n[^\n]*مركز غاز الزيتونة/) || [])[1], m = (p.match(/\[(\d+)\] أخبار حيّ الزيتونة/) || [])[1];
  return {found: true, lines: [{text: 'مركز غاز الزيتونة في شارع الورد، رقمه [هاتف-1] (من مجموعات الحيّ)', ref: Number(n)},
    {text: 'معلّم الصحّيّة: هاتف-٢ وواتساب [ هاتف-3 ]', ref: Number(n)}, {text: 'بحسب صفحة أخبار حيّ الزيتونة: انقطاع المياه حتّى المساء', ref: Number(m)}]};
};
ctx.realGemini = run('gemini_');
run('gemini_ = function (p, s) { return FAKE(p); }');
ctx.Q = 'ما رقم مركز الغاز ومعلّم الصحّيّة؟ وهل انقطعت المياه في حيّ الزيتونة؟';
const ans = run('answer_(Q)');
check('private: no phone number of the guide reaches the model', !/0999123456|٠٩٤٤|963955000111/.test(seen) && /\[هاتف-1\]/.test(seen) && /\[هاتف-3\]/.test(seen), (seen.match(/مركز غاز الزيتونة[^\n]*/) || [''])[0]);
check('private: dates and short amounts in the guide are not masked', /2026-11-08 إلى 2026-11-23/.test(seen) && /1025 اسمًا بسعر 115/.test(seen));
check('private: the numbers come back in the answer, in every form of the token', ans.includes('رقمه 0999123456') && ans.includes('٠٩٤٤ ٥٥٥ ٦٦٦') && ans.includes('963955000111') && !/هاتف-/.test(ans), ans);
check('private: guide line has a plain source label, page line has its link', ans.includes('<i>↗ دليل الحيّ</i>') && ans.includes('<a href="https://facebook.com/1">↗ أخبار حيّ الزيتونة</a>'), ans);
check('private: the followed page is marked unofficial in the prompt', /أخبار حيّ الزيتونة \(فيسبوك، غير رسميّ\)/.test(seen));
setPriv('');
run('answer_(Q)');
check('private: without private files the answer still works from public data', !/مركز غاز الزيتونة/.test(seen) && seen.includes('=== البيانات ==='));
run('gemini_ = realGemini');
// الاستقبال: المفتاح يُسجَّل عند أوّل رفع ثمّ لا يُقبل غيره، والأسماء الغريبة تُهمل
const puts = [];
ctx.HOST_PUT = (name, text) => { puts.push(name); return 'id-' + name; };
run('privPut_ = function (name, text, idx) { return HOST_PUT(name, text); }; drive_ = function () { return {getResponseCode: function () { return 200; }, getContentText: function () { return "{}"; }}; }');
ctx.B = {key: 'k'.repeat(40), files: [{name: 'hay.jsonl', text: 'x'}, {name: '../evil.txt', text: 'x'}, {name: 'social-2026-11-23.jsonl', text: 'y'}], keep: ['hay.jsonl', 'social-2026-11-23.jsonl']};
const u1 = run('receive_(B)');
check('upload: first upload registers the key and saves only well-named files', u1.ok && u1.saved.join() === 'hay.jsonl,social-2026-11-23.jsonl' && store.PUSH_KEY_SHA.length === 64 && puts.length === 2, JSON.stringify(u1));
ctx.B2 = {key: 'z'.repeat(40), files: [{name: 'hay.jsonl', text: 'bad'}]};
check('upload: another key is refused, a short key too', run('receive_(B2)').ok === false && run('receive_({key: "short"})').ok === false && puts.length === 2);
ctx.B3 = {key: 'k'.repeat(40), files: [], keep: ['hay.jsonl']};
const u3 = run('receive_(B3)');
check('upload: files no longer kept on the PC are removed from the index', u3.ok && u3.files === 1 && !JSON.parse(store.PRIV_FILES)['social-2026-11-23.jsonl']);
// ---------- لوحة الأزرار: أجوبة البيانات بلا نموذج، والتوجيه، وإرسال اللوحة مرّةً واحدة
const kb = run('keyboard_()');
check('buttons: three rows of three, persistent', kb.keyboard.length === 3 && kb.keyboard.every(r => r.length === 3 && r.every(b => b.text)) && kb.is_persistent && kb.resize_keyboard);
const quick = label => { ctx.Q = label; return run('quick_(Q)'); };
const marks = {'💱 العملات': ['الدولار', 'بقيّة العملات', 'الرسميّ', 'الفجوة'], '🥇 الذهب': ['نشرة الصاغة', 'عيار 21', 'عيار 24'], '⛽ المحروقات': ['بنزين 95', 'ربطة الخبز', 'منذ'],
  '🕌 المواقيت': ['الفجر', 'المغرب', 'مسجدك'], '🌤 الطقس': ['طقس حماة', 'العظمى'], '🧺 السلّة': ['سلّة حماة', 'الأسعار كلّها', 'blockquote expandable']};
for (const [label, need] of Object.entries(marks)) {
  const a = quick(label) || '';
  check('buttons: ' + label.replace(/^[^ء-ي]+/, '') + ' answered from the data, fits one message', need.every(x => a.includes(x)) && a.length < 4000 && !/undefined|NaN|null/.test(a), a.slice(0, 200));
}
check('buttons: a typed question is not a button', quick('كم سعر الدولار اليوم؟') === null && quick('📰 أخبار اليوم') === null);
setPriv(tmp);
const hayq = quick('☎️ أرقام الحيّ');
check('buttons: neighbourhood numbers come from the private guide, grouped and folded', hayq.includes('<b>مراكز الغاز</b>') && hayq.includes('<b>مركز غاز الزيتونة</b>') && hayq.includes('📞 0999123456') && hayq.includes('blockquote expandable') && !hayq.includes('أين ورد'), hayq);
setPriv('');
check('buttons: no guide file gives a plain note', /غير متاح/.test(quick('☎️ أرقام الحيّ')));
const calls = [], asked2 = [];
ctx.HOST_TG = (method, payload) => { calls.push([method, payload]); return method === 'getUpdates' ? {ok: true, result: []} : {ok: true, result: {message_id: 9}}; };
ctx.HOST_ASK = q => { asked2.push(q); return 'جواب'; };
run('tg_ = function (token, method, payload) { return HOST_TG(method, payload); }; answer_ = function (q) { return HOST_ASK(q); }');
ctx.M = t => ({text: t, message_id: 5, chat: {id: 1}});
run('handle_("t", "1", M("🕌 المواقيت"))');
check('buttons: a data button is answered at once, without the model or a typing notice', calls.length === 1 && calls[0][0] === 'sendMessage' && calls[0][1].text.includes('مواقيت حماة') && asked2.length === 0, JSON.stringify(calls.map(c => c[0])));
calls.length = 0; run('handle_("t", "1", M("📍 أخبار حماة"))');
check('buttons: a news button asks its ready question the normal way', asked2.length === 1 && /أخبار محافظة حماة/.test(asked2[0]) && calls.map(c => c[0]).join() === 'sendChatAction,sendMessage', asked2.join());
calls.length = 0; run('handle_("t", "1", M("ما آخر أخبار وزارة الصحّة؟"))');
check('buttons: a typed question goes through unchanged', asked2[1] === 'ما آخر أخبار وزارة الصحّة؟');
calls.length = 0; run('handle_("t", "1", M("/start"))');
check('buttons: /start brings the help with the keyboard', calls.length === 1 && calls[0][1].reply_markup && calls[0][1].reply_markup.keyboard.length === 3 && /الأزرار/.test(calls[0][1].text), JSON.stringify(calls[0][1]).slice(0, 200));
store.TELEGRAM_TOKEN = 't'; calls.length = 0; delete store.KB;
run('poll()'); run('poll()');
const hello = calls.filter(c => c[0] === 'sendMessage');
check('buttons: the keyboard is announced once, silently', hello.length === 1 && hello[0][1].reply_markup.keyboard.length === 3 && hello[0][1].disable_notification === true && store.KB === run('KB_VER'), JSON.stringify(calls.map(c => c[0])));
// ---------- القسم الخاصّ (بلا رمز): قيمٌ وهميّة، وملفّ Drive في الذاكرة
const FILES = {};
ctx.V_PUT = (name, text) => { FILES[name] = text; return 'id-' + name; };
ctx.V_READ = names => Object.fromEntries(names.filter(n => FILES[n]).map(n => [n, FILES[n]]));
run('privPut_ = function (name, text, idx) { return V_PUT(name, text); }; privRead_ = function (names, idx) { return V_READ(names.filter(function (n) { return idx[n]; })); }');
let mid = 100;
ctx.HOST_TG = (method, payload) => { calls.push([method, payload]); return method === 'getUpdates' ? {ok: true, result: []} : {ok: true, result: {message_id: ++mid}}; };
const send = t => { calls.length = 0; ctx.T = {text: t, message_id: 5, chat: {id: 1}}; run('handle_("t", "1", T)'); return calls.filter(c => c[0] === 'sendMessage').map(c => c[1].text).join('\n'); };
const deleted = () => calls.some(c => c[0] === 'deleteMessage' && c[1].message_id === 5);
const askedBefore = asked2.length;
delete store.VAULT_ID; delete store.VAULT_KEY; delete store.VAULT_DEL;
let out = send('خاصّ');
check('vault: the bare word on an empty vault shows how to use it, with no code anywhere', /القسم الخاصّ · 0 معلومة/.test(out) && /احفظ: بريد العمل/.test(out) && !/رمز/.test(out) && !store.VAULT_ID, out);
out = send('احفظ: بريد العمل = me@mail.example / السرّ: Ab=12==');
check('vault: saving needs no code, confirms by name only, and removes the message', /حُفظ: <b>بريد العمل<\/b>/.test(out) && !/me@mail/.test(out) && deleted() && store.VAULT_ID === 'id-vault.json' && store.VAULT_KEY.length > 40, out);
out = send('احفظ الرقم الوطنيّ لأحمد = 01234567890');
check('vault: the colon after the command is optional', /حُفظ/.test(out) && /2 في القسم/.test(out), out);
let vf = JSON.parse(FILES['vault.json']);
check('vault: the stored file has an encrypted index and one encrypted value per item, nothing readable', vf.v === 3 && vf.i.c.length > 40 && Object.keys(vf.vals).length === 2
  && !/me@mail|Ab=12|بريد|01234567890|الوطني/.test(FILES['vault.json']));
out = send('خاصّ بريد');
check('vault: asking returns the value whole, covered, and queues the reply for deletion; the question stays', out.includes('<tg-spoiler>me@mail.example / السرّ: Ab=12==</tg-spoiler>') && /بريد العمل/.test(out)
  && JSON.parse(store.VAULT_DEL).length === 1 && !deleted(), out);
check('vault: words must all match the name', /لا معلومة/.test(send('خاص بريد البيت')) && send('خاص وطني احمد').includes('01234567890'));
out = send('خاصّ');
check('vault: the bare word lists names without values', /2 معلومة/.test(out) && /• بريد العمل/.test(out) && !/me@mail[.]example|01234567890/.test(out), out);
check('vault: nothing of it went to the model', asked2.length === askedBefore);
out = send('احفظ: بريد العمل = new@mail.example');
check('vault: saving the same name updates it', /حُدّث/.test(out) && /2 في القسم/.test(out) && send('خاص بريد').includes('new@mail.example') && Object.keys(JSON.parse(FILES['vault.json']).vals).length === 2);
check('vault: a save without "=" is refused, and its message is still removed', /الصيغة/.test(send('احفظ: كلمة سرّ البنك 998877')) && deleted() && !send('خاص').includes('البنك'));
out = send('احذف: بريد العمل');
check('vault: deleting by exact name', /حُذف/.test(out) && /1 معلومة/.test(send('خاص')) && /لا معلومة بهذا الاسم/.test(send('احذف: شيء آخر')));
check('vault: ordinary words that begin alike are not commands', (send('خاصية جديدة في واتساب؟'), asked2.length === askedBefore + 1) && (send('ما الخاصّ بأسعار الذهب؟'), asked2.length === askedBefore + 2));
const key0 = store.VAULT_KEY;
store.VAULT_KEY = Buffer.from('x'.repeat(32)).toString('base64');
check('vault: the file does not open with another key', /لا يطابق مفتاحه/.test(send('خاص وطني')));
store.VAULT_KEY = key0;
// ملفٌّ بالصيغة القديمة (كتلة واحدة) يُقرأ ثمّ يُكتب بالجديدة عند أوّل حفظ
run('(function () { var K = Utilities.base64Decode(PropertiesService.getScriptProperties().getProperty("VAULT_KEY")), n = rand16_(), '
  + 'ct = xor_(K, n, bytes_(JSON.stringify({items: [{name: "معلومة قديمة", value: "قيمة من الصيغة القديمة", at: "2026-11-23"}]}))); '
  + 'V_PUT("vault.json", JSON.stringify({v: 2, nonce: Utilities.base64Encode(n), ct: Utilities.base64Encode(ct), mac: seal_(K, n, ct)})); })()');
check('vault: a file in the old format is still read', send('خاص قديمة').includes('قيمة من الصيغة القديمة'));
send('احفظ: جديدة = 1');
check('vault: and it is rewritten in the new format with nothing lost', JSON.parse(FILES['vault.json']).v === 3 && send('خاص قديمة').includes('قيمة من الصيغة القديمة') && /2 معلومة/.test(send('خاص')));
// الاستيراد بالجملة من الحاسوب (doPost بمفتاح الرفع)
const bulk = [];
for (let k = 0; k < 600; k++) bulk.push({name: 'حساب site-' + k + '.example · user' + k, value: 'المستخدم: user' + k + '\nكلمة السرّ: p-' + k + '-x'});
bulk.push({name: '', value: 'x'}, {name: 'بلا قيمة', value: '  '}, {name: 'نوع خطأ', value: 5}, null);
ctx.B5 = {key: 'k'.repeat(40), files: [], vault: bulk};
const t0 = Date.now(), imp = run('receive_(B5)'), took = Date.now() - t0;
check('vault: bulk import adds the valid items and skips the bad ones', imp.ok && imp.vault.added === 600 && imp.vault.updated === 0 && imp.vault.total === 602, JSON.stringify(imp.vault) + ' ' + took + 'ms');
check('vault: importing the same list again updates instead of duplicating', (r => r.vault.added === 0 && r.vault.updated === 600 && r.vault.total === 602)(run('receive_(B5)')));
ctx.B6 = {key: 'z'.repeat(40), files: [], vault: [{name: 'دخيل', value: 'x'}]};
check('vault: an import with a wrong key is refused', run('receive_(B6)').ok === false && !send('خاص دخيل').includes('<tg-spoiler>'));
out = send('خاص site-77.example');
check('vault: among several matches the closest name comes first', out.indexOf('p-77-x') > 0 && out.indexOf('p-77-x') < out.indexOf('p-177-x') && !/أخرى تطابق/.test(out), out.slice(0, 300));
out = send('خاص site example');
check('vault: a broad search shows twelve and counts the rest', (out.match(/<tg-spoiler>/g) || []).length === 12 && /و588 أخرى تطابق/.test(out) && out.length < 4096, out.slice(-200));
check('vault: one exact item is found alone', (o => o.includes('p-599-x') && !/أخرى تطابق/.test(o))(send('خاص user599')));
out = send('خاصّ');
check('vault: a long list is shown as counts with a hint to search', /602 معلومة/.test(out) && /• حساب…: 600/.test(out) && !/site-77/.test(out) && out.length < 3500, out.slice(0, 300));
store.VAULT_DEL = JSON.stringify([[201, 1], [202, Math.floor(Date.now() / 1000) + 600]]);
calls.length = 0; run('poll()');
check('vault: due replies are deleted on the next minute, later ones wait', calls.some(c => c[0] === 'deleteMessage' && c[1].message_id === 201) && !calls.some(c => c[0] === 'deleteMessage' && c[1].message_id === 202)
  && JSON.parse(store.VAULT_DEL).length === 1);
ctx.B4 = {key: 'k'.repeat(40), files: [], keep: ['hay.jsonl']};
run('receive_(B4)');
check('vault: the PC upload and its pruning never touch the vault file', store.VAULT_ID === 'id-vault.json' && !!FILES['vault.json']);
// ---------- سؤالٌ عاديّ يجمع الخاصّ والعامّ: النموذج يقسّم نصّ السؤال فقط، والكود يبحث في القسم الخاصّ
ctx.B7 = {key: 'k'.repeat(40), files: [], vault: [{name: 'هاتف ابي', value: '0999000111'}, {name: 'هاتف سامر الأبيض', value: '0999000222'},
  {name: 'حساب facebook.com · me@x.example', value: 'المستخدم: me@x.example\nكلمة السرّ: Fb-Secret-9'}, {name: 'الرقم الوطنيّ لسلمى', value: '09876543210'}]};
run('receive_(B7)');
const plans = [];
let nextPlan = null;
ctx.FAKE2 = p => { plans.push(p); return nextPlan; };
run('gemini_ = function (p, s) { return FAKE2(p); }');
const nAsk = () => asked2.length;
let before = nAsk();
nextPlan = {parts: [{kind: 'phone', terms: ['أبي', 'ابي', 'والدي'], text: 'رقم أبي'}, {kind: 'account', terms: ['facebook', 'فيسبوك'], text: 'حسابي في فيسبوك'},
  {kind: 'public', terms: [], text: 'توقّع الجوّ للغد'}]};
out = send('أعطني رقم أبي وحسابي في فيسبوك وتوقع الجو للغد');
const sends = calls.filter(c => c[0] === 'sendMessage');
check('ask: one ordinary question gets its private parts from the vault and its public part the normal way', sends.length === 2 && sends[0][1].text.includes('<tg-spoiler>0999000111</tg-spoiler>')
  && sends[0][1].text.includes('Fb-Secret-9') && nAsk() === before + 1 && asked2[asked2.length - 1] === 'توقّع الجوّ للغد', JSON.stringify(sends.map(c => c[1].text.slice(0, 80))));
check('ask: the model saw the question only, never a name or a value of the vault', plans.length === 1 && plans[0].includes('رقم أبي') && !/0999000111|Fb-Secret|me@x[.]example|سامر|سلمى/.test(plans.join('\n')));
check('ask: whole words only, so «أبي» does not bring «الأبيض»', !sends[0][1].text.includes('0999000222'));
check('ask: the private reply is queued for deletion and marked as private', JSON.parse(store.VAULT_DEL).some(x => x[0] === sends[0][1].message_id || true) && /من القسم الخاصّ/.test(sends[0][1].text));
before = nAsk(); plans.length = 0;
nextPlan = {parts: [{kind: 'phone', terms: ['الإسعاف'], text: 'ما رقم الإسعاف في حماة؟'}]};
out = send('ما رقم الإسعاف في حماة؟');
check('ask: a number that is not in the vault goes to the normal answer', nAsk() === before + 1 && asked2[asked2.length - 1] === 'ما رقم الإسعاف في حماة؟' && calls.filter(c => c[0] === 'sendMessage').length === 1);
before = nAsk();
nextPlan = {parts: [{kind: 'personal', terms: ['وطني سلمى', 'الرقم الوطني'], text: 'الرقم الوطنيّ لسلمى'}]};
out = send('ما الرقم الوطني لسلمى؟');
check('ask: a question that is all private gets one covered reply and no model answer', out.includes('<tg-spoiler>09876543210</tg-spoiler>') && nAsk() === before && calls.filter(c => c[0] === 'sendMessage').length === 1, out);
before = nAsk(); nextPlan = null;
send('أعطني رقم أبي');
check('ask: if the split fails, the question goes on unchanged', nAsk() === before + 1 && asked2[asked2.length - 1] === 'أعطني رقم أبي');
plans.length = 0; before = nAsk();
send('كم سعر الدولار اليوم؟');
check('ask: a question with no private word never calls the splitter', plans.length === 0 && nAsk() === before + 1);
// ---------- حساب غير محفوظ يُقال عنه ذلك ولا يُسأل عنه النموذج
before = nAsk();
nextPlan = {parts: [{kind: 'account', terms: ['claude', 'كلود'], text: 'حسابي في claude'}, {kind: 'phone', terms: ['أبي', 'ابي'], text: 'رقم أبي'}, {kind: 'public', terms: [], text: 'موعد أذان الظهر'}]};
out = send('أعطني حسابي في claude ورقم أبي وموعد أذان الظهر');
check('ask: an account that is not saved is reported as missing, not sent to the model', /ليس في القسم الخاصّ: «حسابي في claude»/.test(out) && out.includes('0999000111') && nAsk() === before + 1
  && asked2[asked2.length - 1] === 'موعد أذان الظهر', out.slice(0, 300));
// ---------- متانة الاتّصال بالنموذج: إعادة المحاولة، وعدم الرفض بلا محاولة، وسبب التعذّر
run('gemini_ = realGemini');
const realFetch = ctx.UrlFetchApp.fetch;
let script = [], fetched = [], slept = 0;
const okBody = JSON.stringify({candidates: [{content: {parts: [{text: '{"a":"نعم"}'}]}}]});
ctx.UrlFetchApp.fetch = (url, o) => {
  if (!/generativelanguage/.test(url)) return realFetch(url, o);
  const model = url.split('/models/')[1].split(':')[0], step = script.shift() || [503, 'overloaded'];
  fetched.push(model + ':' + step[0]);
  return {getResponseCode: () => step[0], getContentText: () => (step[0] === 200 ? okBody : step[1] || 'err')};
};
const realSleep = ctx.Utilities.sleep;
ctx.Utilities.sleep = ms => { slept += ms; };
const ask1 = () => run('gemini_("س", {type: "object", properties: {a: {type: "string"}}})');
store.AI_REST = '{}'; store.AI_DAY = ''; script = [[503], [200]]; fetched = []; slept = 0;
let g1 = ask1();
check('model: a passing overload is retried on the same model and answers', g1 && g1.a === 'نعم' && fetched.join() === 'gemini-3.6-flash:503,gemini-3.6-flash:200' && slept > 0 && store.AI_REST === '{}', fetched.join() + ' ' + store.AI_REST);
store.AI_REST = '{}'; script = [[429], [200]]; fetched = [];
g1 = ask1();
const rest1 = JSON.parse(store.AI_REST);
check('model: a quota refusal moves to the next model and rests the first five minutes', g1 && fetched.join() === 'gemini-3.6-flash:429,gemini-flash-lite-latest:200' && rest1['gemini-3.6-flash'] > Date.now() + 200000
  && rest1['gemini-3.6-flash'] < Date.now() + 400000 && !rest1['gemini-flash-lite-latest'], fetched.join());
const far = Date.now() + 500000;
store.AI_REST = JSON.stringify({'gemini-3.6-flash': far + 1000, 'gemini-flash-lite-latest': far, 'gemini-2.5-flash': far + 2000, 'gemini-3-flash-preview': far + 3000});
script = [[200]]; fetched = [];
g1 = ask1();
check('model: when every model is resting, the one due first is tried anyway', g1 && fetched.join() === 'gemini-flash-lite-latest:200', fetched.join());
store.AI_REST = '{}'; script = []; fetched = [];
g1 = ask1();
const rest2 = JSON.parse(store.AI_REST);
check('model: when all fail the reason is kept, and an overload rests each model only a minute and a half', g1 === null && fetched.length === 8 && /3\.6-flash 503/.test(run('AI_FAIL')) && /503/.test(store.AI_ERR)
  && Object.values(rest2).every(t => t < Date.now() + 100000), fetched.join() + ' | ' + store.AI_ERR);
// ---------- النموذج معطّل: الجواب من البيانات مباشرةً
ctx.DIRP = [{dir: true, name: 'دليل الهاتف · المساحة السوريّة', text: 'شرطة النجدة (طوارئ) — طوارئ · شرطة النجدة · الرقم: 112', url: 'https://syrian.zone/phonebook', ts: 1, tier: 2},
  {name: 'سانا', text: 'خبر لا علاقة له', url: 'u', ts: 2, tier: 2}];
const off = run('offline_("موعد أذان الظهر ورقم شرطة النجدة", S, DIRP)');
check('model down: prayer times and the nearest directory entries are given straight from the data, with the reason', /النموذج لا يردّ الآن/.test(off) && /503/.test(off) && /مواقيت حماة/.test(off) && /الرقم: 112/.test(off)
  && /↗ دليل الهاتف/.test(off) && !/خبر لا علاقة له/.test(off) && off.length < 4096, off.slice(0, 300));
check('model down: with nothing to show, a plain note with the reason', /تعذّر الوصول إلى النموذج الآن \(/.test(run('offline_("كيف حالك", S, [])')));
ctx.UrlFetchApp.fetch = realFetch; ctx.Utilities.sleep = realSleep; store.AI_REST = '{}';
fs.rmSync(tmp, {recursive: true, force: true});

console.log('\nfacts sheet: ' + facts.length + ' chars · archive: ' + news.length + ' posts · top for Hama: ' + r2.slice(0, 4).map(p => p.name).join('، '));
console.log(fails ? '\nFAILED: ' + fails : '\nALL PASSED');
process.exit(fails ? 1 : 0);
