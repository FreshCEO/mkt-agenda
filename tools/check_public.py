"""공개해도 되는 파일인지 점검한다. 실제 데이터의 이름, 링크, 안건 문장이 한 줄이라도 들어 있으면 실패.
  python tools/check_public.py            -> dist/index.html과 저장소에 올라갈 모든 글자 파일을 점검
"""
import json, pathlib, re, subprocess, sys
root = pathlib.Path(__file__).parent.parent
real = json.loads((root / 'data/data.real.json').read_text(encoding='utf-8'))
deny = set()
c = real.get('conf', {})
for o in c.get('org', []): deny.update([o['head'], o['chk']])
deny.update([c.get('owner', ''), c.get('cc', ''), c.get('unit', '')]); deny.update(x.strip() for x in c.get('to', '').split(','))
m = re.search(r'/d/([\w-]{20,})', c.get('link', ''));  deny.add(m.group(1) if m else '')
deny.update(t['name'] for t in real['teams'] if len(t['name']) >= 3 and not t['name'].isascii())   # 영문 약어 팀 이름은 글꼴 데이터와 우연히 겹쳐 제외
deny.update(t.get('head', '') for t in real['teams']); deny.update(t.get('mail', '') for t in real['teams'])
def lines(v):
    for l in str(v).split('\n'):
        l = l.strip(' -*\t')
        if len(l) >= 12: yield l
for w in real['history']:
    for cells in w['cells'].values():
        for v in cells.values(): deny.update(lines(v))
    for it in w.get('items', []):
        for k in ('title', 'text', 'sum', 'raw'): deny.update(lines(it.get(k, '')))
for f in real.get('feedback', []): deny.update(lines(f.get('text', '')))
deny = {d for d in deny if d and len(d) >= 2}
try: files = subprocess.run(['git', 'ls-files', '-z', '-co', '--exclude-standard'], cwd=root, capture_output=True, text=True, encoding='utf-8', check=True).stdout.split('\0')   # -z, utf-8: 윈도우에서 한글 파일 이름이 깨지거나 따옴표로 바뀌지 않게
except Exception: files = [str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and 'data.real' not in p.name and 'index.real' not in p.name and p.name != 'test_real.py' and '.git' not in p.parts]   # git이 아직 없을 때: .gitignore의 커밋 금지 파일을 손으로 뺀다
try: staged = set(subprocess.run(['git', 'diff', '--cached', '--name-only', '-z', '--diff-filter=ACMR'], cwd=root, capture_output=True, text=True, encoding='utf-8', check=True).stdout.split('\0')) - {''}
except Exception: staged = set()
files = list(dict.fromkeys([f for f in files if f] + sorted(staged)))
BIN = ('.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.otf', '.pdf', '.zip')
def versions(f):
    """작업 폴더의 내용과, 스테이지된 경우 실제로 커밋될 내용(git show :경로)을 둘 다 돌려준다"""
    p = root / f
    if p.is_file(): yield p.read_bytes().decode('utf-8', errors='ignore')
    if f in staged:
        r = subprocess.run(['git', 'show', ':' + f], cwd=root, capture_output=True)
        if r.returncode == 0: yield r.stdout.decode('utf-8', errors='ignore')
bad = []
for f in files:
    p = root / f
    if 'data.real' in p.name or 'index.real' in p.name or p.name == 'test_real.py': bad.append((f, '실제 데이터 파일이 올라갈 목록에 있음')); continue
    if p.suffix.lower() in BIN or p.name == 'check_public.py': continue   # 확장자가 없거나 csv 같은 글자 파일도 점검한다
    for txt in versions(f):
        hit = [d for d in deny if d in txt]
        if hit: bad.append((f, hit[:5])); break
print(f'점검 기준 {len(deny)}개, 점검 파일 {len([f for f in files if f])}개')
for b in bad: print('  실패:', b)
sys.exit(1 if bad else 0)
