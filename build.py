"""화면 한 파일 만들기.
  python build.py sample   -> dist/index.html        (예시 데이터, 공개 저장소에 올려도 되는 파일)
  python build.py real     -> dist/index.real.html   (실제 데이터, 내 PC에서만 연다. 커밋 금지)
"""
import sys, pathlib
root = pathlib.Path(__file__).parent
kind = sys.argv[1] if len(sys.argv) > 1 else 'sample'
assert kind in ('sample', 'real'), 'sample 또는 real'
t = (root / 'src/template.html').read_text(encoding='utf-8')
font = (root / 'src/font_face.css').read_text(encoding='utf-8')
data = (root / f'data/data.{kind}.json').read_text(encoding='utf-8')
assert t.count('/*__FONT__*/') == 1 and t.count('/*__DATA__*/null') == 1
out = t.replace('/*__FONT__*/', font).replace('/*__DATA__*/null', data)
dst = root / ('dist/index.html' if kind == 'sample' else 'dist/index.real.html')
dst.parent.mkdir(exist_ok=True); dst.write_text(out, encoding='utf-8')
print(dst, len(out))
