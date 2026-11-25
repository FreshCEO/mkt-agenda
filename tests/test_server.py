"""서버 저장 모드 확인. 진짜 구글 서버 대신 Code.gs와 같은 규칙의 가짜 서버를 붙여 돌린다.
  python build.py sample && python tests/test_server.py"""
import asyncio, json, os, pathlib, shutil
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
ADMIN, INPUT = 'admin-test', 'input-test'
store, logs = {}, []   # key -> {ver, json}

def handle(body):
    q = json.loads(body or '{}')
    role = 'admin' if q.get('key') == ADMIN else 'input' if q.get('key') == INPUT else None
    if not role: return {'ok': False, 'error': '키가 맞지 않습니다'}
    a = q.get('args') or {}
    if q['op'] == 'get':
        have = a.get('have') or {}
        return {'ok': True, 'data': {'role': role, 'slices': [{'k': k, 'ver': v['ver'], 'json': v['json']} for k, v in store.items() if v['ver'] != have.get(k)], 'log': []}}
    vers, conf, den = {}, [], []
    sent = {x['k'] for x in a.get('slices') or []}
    # 지우기 먼저, 화면이 본 버전과 같을 때만 (Code.gs와 같은 규칙)
    dropped = [d['k'] for d in (a.get('drop') or []) if role == 'admin' and str(d.get('k', '')).startswith('team:') and d['k'] in store and d['k'] not in sent and store[d['k']]['ver'] == (d.get('ver') or 0)]
    for k in dropped: del store[k]
    for x in a.get('slices') or []:
        k = x['k']
        if role != 'admin' and k == 'core': den.append(k); continue
        cur = store.get(k)
        if (cur['ver'] if cur else 0) != (x.get('ver') or 0): conf.append({'k': k, 'ver': cur['ver'] if cur else 0, 'json': cur['json'] if cur else ''}); continue
        json.loads(x['json'])
        store[k] = {'ver': (cur['ver'] if cur else 0) + 1, 'json': x['json']}; vers[k] = store[k]['ver']
    logs.extend((q.get('who'), l.get('msg')) for l in a.get('logs') or [])
    return {'ok': True, 'data': {'vers': vers, 'conflicts': conf, 'denied': den, 'dropped': dropped, 'log': []}}

async def route(r):
    await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(handle(r.request.post_data)))

async def open_page(b, key):
    ctx = await b.new_context(viewport={'width': 1360, 'height': 900})
    await ctx.route('https://script.google.com/**', route)
    pg = await ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.dialogs = []
    async def on_dialog(d): pg.dialogs.append(d.message); await d.accept()
    pg.on('dialog', lambda d: asyncio.ensure_future(on_dialog(d)))
    await pg.goto((ROOT / 'dist/index.html').as_uri() + f'#k={key}&s=TESTID'); await pg.wait_for_timeout(800)
    return pg, errs

def team_item(n):
    return json.loads(store['team:' + n]['json'])['items']

async def main():
    ok = []
    async with async_playwright() as p:
        exe = os.environ.get('CHROME') or shutil.which('google-chrome') or shutil.which('chrome')
        b = await p.chromium.launch(**({'executable_path': exe} if exe else {}), args=['--no-sandbox'])
        # 1. 팀장 키로 빈 서버를 열면 막힌다
        pg0, _ = await open_page(b, INPUT)
        ok.append(('빈 서버는 팀장 키로 시작 못 함', '관리 키로 먼저' in await pg0.inner_text('#app')))
        # 2. 관리 키 첫 연결: 예시 데이터로 시작해 조각이 모두 저장됨
        pa, ea = await open_page(b, ADMIN); await pa.wait_for_timeout(2000)
        ok.append(('관리 첫 연결: core 저장', 'core' in store))
        ok.append(('관리 첫 연결: 팀 조각 저장', sum(k.startswith('team:') for k in store) >= 18))
        ok.append(('저장 표시', '저장됨' in await pa.inner_text('#sync')))
        ok.append(('주소의 키가 지워짐', '#k=' not in pa.url))
        team = await pa.evaluate('S.inTeam')
        # 3. 관리 화면에서 안건 제목 고치기 -> 그 팀 조각만 버전이 오름
        v_core = store['core']['ver']; v_t = store['team:' + team]['ver']
        await pa.evaluate("t => { const i = S.active.items.find(x => x.team === t); i.title = '서버 저장 시험 제목'; render(); }", team)
        await pa.wait_for_timeout(2000)
        ok.append(('제목 고침이 팀 조각에 저장', any(i['title'] == '서버 저장 시험 제목' for i in team_item(team)) and store['team:' + team]['ver'] == v_t + 1))
        ok.append(('core는 그대로', store['core']['ver'] == v_core))
        # 4. 새로 열면 서버 내용이 보임 (이 브라우저 저장이 아니라)
        pb, eb = await open_page(b, INPUT)
        ok.append(('팀장 키: 역할 팀장 고정', await pb.evaluate('S.role') == 'lead' and await pb.locator('select[data-ch=role]').is_disabled()))
        ok.append(('팀장 키: 설정 탭 없음', await pb.locator('.top .tab[data-k=settings]').count() == 0))
        ok.append(('팀장 키: 서버 내용 보임', await pb.evaluate("t => S.active.items.some(x => x.team === t && x.title === '서버 저장 시험 제목')", team)))
        # 5. 팀장 키 첫 화면은 내 팀부터 고르게 하고, 고른 팀을 기억함
        ok.append(('팀장 키: 처음엔 내 팀 고르기', await pb.evaluate('S.roleTeam') == '' and '내 팀' in await pb.inner_text('.sheet')))
        names = await pb.evaluate('S.teams.map(t => t.name)')
        rt = names[1]
        await pb.select_option('select[data-ch=roleTeam]', rt); await pb.wait_for_timeout(300)
        ok.append(('팀장 키: 고른 팀 기억', await pb.evaluate("localStorage.getItem('hq-agenda-myteam')") == rt and await pb.evaluate('S.roleTeam') == rt and not pb.dialogs))
        ok.append(('팀장 키: 단계 카드 대신 내 팀 한 줄', await pb.locator('.leadbar').count() == 1 and await pb.locator('.flow').count() == 0))
        # 팀장이 자기 팀 제출 -> 팀 조각만 저장, core는 거절 없이 안 보냄
        await pb.evaluate("t => { S.active.items.filter(x => x.team === t).forEach(x => x.title = x.title || '제목'); S.cats.forEach(c => { if (!S.active.items.some(i => i.team === t && i.cat === c.id)) (S.active.none[t] = S.active.none[t] || {})[c.id] = true; }); A.submit({t}); render(); }", rt)
        await pb.wait_for_timeout(2000)
        ok.append(('팀장 제출이 서버에 저장', bool(json.loads(store['team:' + rt]['json']).get('subs'))))
        ok.append(('제출 완료 안내는 저장 뒤에', '저장되었습니다' in await pb.locator('.toast').inner_text()))
        ok.append(('팀장은 core를 보내지 않음', store['core']['ver'] == v_core))
        ok.append(('제출 기록이 서버 로그로 감', any(rt + ' 제출' in (m or '') for _, m in logs)))
        # 6. 관리 화면이 1분 갱신으로 제출을 받음
        await pa.evaluate('srvPoll()'); await pa.wait_for_timeout(800)
        ok.append(('관리 화면 갱신으로 제출 보임', await pa.evaluate('t => !!S.active.subs[t]', rt)))
        # 7. 같은 팀을 둘이 고치면 늦은 쪽은 최신 내용으로 바뀌고 안내
        await pb.evaluate("t => { const i = S.active.items.find(x => x.team === t); i.title = '팀장 고침'; render(); }", rt); await pb.wait_for_timeout(2000)
        await pa.evaluate("t => { const i = S.active.items.find(x => x.team === t); i.title = '관리 고침'; render(); }", rt); await pa.wait_for_timeout(2000)
        ok.append(('충돌: 먼저 저장한 내용 유지', any(i['title'] == '팀장 고침' for i in team_item(rt)) and not any(i['title'] == '관리 고침' for i in team_item(rt))))
        ok.append(('충돌: 늦은 쪽 화면이 최신으로 바뀜', await pa.evaluate("t => S.active.items.some(x => x.team === t && x.title === '팀장 고침')", rt)))
        ok.append(('충돌 안내', '먼저 고친' in (await pa.locator('.toast').inner_text())))
        ok.append(('충돌: 내가 쓴 내용 보관', '관리 고침' in (await pa.evaluate("t => ((S.ui.lost || {})[t] || {}).text || ''", rt))))
        # 8. 저장 실패 -> 표시, 다시 저장
        await pa.context.unroute('https://script.google.com/**')
        await pa.context.route('https://script.google.com/**', lambda r: r.abort())
        await pa.evaluate("t => { const i = S.active.items.find(x => x.team === t); i.title = '실패 뒤 다시'; render(); }", team); await pa.wait_for_timeout(2000)
        ok.append(('실패 표시', '저장 못 함' in await pa.inner_text('#sync')))
        await pa.context.unroute('https://script.google.com/**'); await pa.context.route('https://script.google.com/**', route)
        await pa.click('#sync button[data-sy=retry]'); await pa.wait_for_timeout(1500)
        ok.append(('다시 저장 성공', any(i['title'] == '실패 뒤 다시' for i in team_item(team)) and '저장됨' in await pa.inner_text('#sync')))
        # 9. 관리 화면에서 데이터를 통째로 바꾸면(팀 하나가 빠지면) 그 팀 조각이 서버에서 지워짐
        gone = await pa.evaluate("() => { const n = S.teams[S.teams.length - 1].name; S.teams.pop(); S.active.items = S.active.items.filter(i => i.team !== n); ['none','subs','late','fix'].forEach(f => delete (S.active[f] || {})[n]); render(); return n; }")
        await pa.wait_for_timeout(2000)
        ok.append(('빠진 팀 조각 삭제', 'team:' + gone not in store and await pa.evaluate("n => !('team:' + n in R.last)", gone)))
        # 9-2. 지우기는 버전이 같을 때만: 팀장이 막 저장한 팀을 관리 화면(옛 버전)이 빼도 서버에는 남음
        other = names[2]
        await pb.select_option('select[data-ch=roleTeam]', other); await pb.wait_for_timeout(300)
        ok.append(('다른 팀으로 바꾸면 한 번 물음', any('내 팀' in m for m in pb.dialogs)))
        await pb.evaluate("t => { const i = S.active.items.find(x => x.team === t); if (i) i.title = '팀장 새 저장'; else S.active.items.push(mk(t, S.cats[0].id, {title:'팀장 새 저장'})); render(); }", other); await pb.wait_for_timeout(2000)
        await pa.evaluate("n => { S.teams = S.teams.filter(t => t.name !== n); S.active.items = S.active.items.filter(i => i.team !== n); ['none','subs','late','fix'].forEach(f => delete (S.active[f] || {})[n]); render(); }", other)
        await pa.wait_for_timeout(2000)
        ok.append(('옛 버전으로는 못 지움', 'team:' + other in store and any(i['title'] == '팀장 새 저장' for i in team_item(other))))
        # 9-3. 실제 시계 모드라도 팀장 화면은 시점을 넘기거나 새 주차를 열지 않음
        ok.append(('팀장 화면은 주차를 넘기지 않음', await pb.evaluate("(() => { S.set.clock = 'real'; window.__now = '2030-01-01T10:00:00'; const r = tick(); window.__now = null; S.set.clock = 'sim'; return r; })()") is False))
        # 10. #off 로 연결 해제 -> 예시 모드
        pc = await pa.context.new_page(); await pc.goto((ROOT / 'dist/index.html').as_uri() + '#off'); await pc.wait_for_timeout(600)
        ok.append(('#off 로 예시 모드', await pc.locator('#sync').count() == 0 and await pc.locator('[data-act=reset]').count() == 1))
        ok.append(('스크립트 오류 없음', not ea and not eb))
        await b.close()
    for n, v in ok: print(('PASS ' if v else 'FAIL ') + n)
    print('오류:', ea + eb if (ea or eb) else '없음')
    raise SystemExit(0 if all(v for _, v in ok) else 1)
asyncio.run(main())
