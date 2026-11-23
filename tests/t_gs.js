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
const ctx = {
  UrlFetchApp: {fetch, fetchAll: reqs => reqs.map(q => fetch(q.url, q))},
  PropertiesService: {getScriptProperties: () => ({getProperty: k => store[k] || null, setProperty: (k, v) => { store[k] = v; }})},
  Utilities: {formatDate: (d, tz, f) => { const s = new Date(d.getTime() + 3 * 3600e3).toISOString(); return f.length > 10 ? s.slice(0, 16).replace('T', ' ') : s.slice(0, 10); }},
  LockService: {getScriptLock: () => ({tryLock: () => true, releaseLock: () => {}})},
  ScriptApp: {getProjectTriggers: () => [], newTrigger: () => ({timeBased: () => ({everyMinutes: () => ({create: () => {}})})})},
  Logger: {log: console.log}, console, Date, JSON, Math, Number, String, Object, Array, RegExp, Error,
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'apps-script', 'Code.gs'), 'utf8'), ctx);
const run = code => vm.runInContext(code, ctx);

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
check('facts sheet: market, official, gold, fuel, weather, prayer, basket', ['سعر السوق', 'الدولار الأمريكيّ USD', 'السعر الرسميّ', 'جمعيّة الصاغة', 'بنزين 95', 'ربطة الخبز', 'طقس حماة', 'المغرب', 'مسجدك', 'سلّة حماة', 'سكّر [KG]'].every(x => facts.includes(x)), facts.slice(0, 300));
check('facts sheet is compact', facts.length < 9000, facts.length);
const news = run('loadNews_(3)');
check('news archive loads from the repository', news.length > 300 && news[0].name && news[0].ts, news.length);
ctx.N = news;
const r2 = run('rank_("ماذا نشرت محافظة حماة؟", N, 28)');
check('rank on the real archive: Hama governorate posts found', r2.length > 0 && r2.some(p => /حماة|حماه/.test(p.name)), r2.slice(0, 5).map(p => p.name).join(' | '));
console.log('\nfacts sheet: ' + facts.length + ' chars · archive: ' + news.length + ' posts · top for Hama: ' + r2.slice(0, 4).map(p => p.name).join('، '));
console.log(fails ? '\nFAILED: ' + fails : '\nALL PASSED');
process.exit(fails ? 1 : 0);
