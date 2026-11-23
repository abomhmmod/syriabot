# يستعمله tests/t_gs.js: طلب HTTP واحد يُقرأ وصفه من الدخل ويُطبع جوابه JSON.
import json, sys, urllib.error, urllib.request
q = json.loads(sys.stdin.buffer.read().decode('utf-8'))
data = q['payload'].encode('utf-8') if q.get('payload') is not None else None
req = urllib.request.Request(q['url'], data=data, headers=dict({'User-Agent': 'Mozilla/5.0'}, **(q.get('headers') or {})), method=q.get('method', 'GET').upper())
try:
    with urllib.request.urlopen(req, timeout=90) as r:
        out = {'code': r.status, 'text': r.read().decode('utf-8', 'replace')}
except urllib.error.HTTPError as e:
    out = {'code': e.code, 'text': e.read().decode('utf-8', 'replace')}
except Exception as e:
    out = {'code': 0, 'text': type(e).__name__}
sys.stdout.buffer.write(json.dumps(out).encode('utf-8'))
