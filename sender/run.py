"""본부의제 자동 발송기. 작업 스케줄러가 몇 분마다 실행한다.

하는 일
  1. 보드 화면을 머리 없는 크롬으로 열어(관리 키) 서버의 이번 주 상태를 읽는다.
  2. 메일이 붙은 단계(기입 마감 알람, 최종 공지) 가운데
     - 화면에서 '예약'을 눌러 둔 것만,
     - 그 단계 시각이 지났고 늦어도 late_limit_min 안이며,
     - 이번 주에 아직 자동 발송하지 않은 것만 보낸다.
  3. 웍스 메일쓰기는 Aside가 사용자의 크롬에서 한다(sender/works_send.tpl.js: 붙여넣기 한 번, 14px, 글자 대조, 서명 그대로 확인 뒤에만 보냄).
  4. 보낸 결과는 화면의 '메일 발송, 예약 이력'과 활동 기록(서버)에, 그리고 내 PC의 sender/ledger.real.json에 남긴다.

안전장치
  - mode는 test만 지원한다. test는 받는 사람을 test_to 한 곳으로 바꾸고 제목 앞에 [시험]을 붙인다. live는 염팀장님이 직접 바꾼다(지금은 막혀 있음).
  - 같은 주차·같은 메일은 서버 이력과 내 PC 장부 둘 다 확인해 한 번만 보낸다. 하루 최대 cap_per_day 통.
  - 시각을 놓친 메일(PC가 꺼져 있었음)은 보내지 않고 '놓침'으로 기록한다.

실행
  python sender/run.py              # 보낼 것이 있으면 보낸다
  python sender/run.py --dry        # 무엇을 보낼지 보여 주기만 한다
  python sender/run.py --now 2026-11-27T10:05   # 지금 시각을 바꿔서 판단(시험용)
  python sender/run.py --page dist/index.html   # 깃허브 대신 내 PC의 화면 파일로(시험용)
"""
import argparse, asyncio, datetime as dtm, json, os, pathlib, shutil, subprocess, sys, tempfile
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONF = json.loads((ROOT / 'secrets' / 'sender.json').read_text(encoding='utf-8'))
LEDGER = ROOT / 'sender' / 'ledger.real.json'
LOGF = ROOT / 'sender' / 'run.real.log'
TPL = (ROOT / 'sender' / 'works_send.tpl.js').read_text(encoding='utf-8')
CHROME = os.environ.get('CHROME') or r'C:\Program Files\Google\Chrome\Application\chrome.exe'
ASIDE = shutil.which('aside') or str(pathlib.Path(os.environ.get('LOCALAPPDATA', '')) / 'Aside' / 'CLI' / 'current' / 'aside.exe')


def say(*a):
    line = dtm.datetime.now().strftime('%m-%d %H:%M:%S ') + ' '.join(str(x) for x in a)
    print(line)
    with open(LOGF, 'a', encoding='utf-8') as f: f.write(line + '\n')


def ledger():
    try: return json.loads(LEDGER.read_text(encoding='utf-8'))
    except Exception: return {'sent': {}, 'days': {}}


def save_ledger(L): LEDGER.write_text(json.dumps(L, ensure_ascii=False, indent=1), encoding='utf-8')


# 화면 안에서: 예약된 메일 중 보낼 때가 된 것을 고른다
PICK = """(now) => {
  const a = S.active, out = [];
  STAGES.forEach((st, i) => {
    if (!st.mail) return;
    const at = addDays(a.meeting, stAt(i).o) + 'T' + stAt(i).h + ':00';
    const done = (S.sent || []).some(x => x.week === a.label && x.type === st.mail && /자동 발송/.test(x.how || ''));
    S.ui.chk = '';
    const m = mailOf(st.mail);
    const none = st.mail === 'remind' && !scopeTeams('').some(n => !a.subs[n]);
    out.push({i, type: st.mail, name: MAILS[st.mail], week: a.label, at, resv: !!(a.resv || {})[i], done, none, subject: m.subject, body: m.body, to: m.to, cc: m.cc || '', edited: !!m.dirty});
  });
  return out;
}"""


def run_aside(M, send):
    js = TPL.replace('__MAIL__', json.dumps(M, ensure_ascii=False)).replace('__SEND__', 'true' if send else 'false')
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f: f.write(js); p = f.name
    try:
        r = subprocess.run([ASIDE, 'repl', '--file', p], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=240)
        out = (r.stdout or '') + (r.stderr or '')
    except Exception as e:
        out = 'aside 실행 실패: ' + str(e)
    finally:
        os.unlink(p)
    return out


LOCK = ROOT / 'sender' / 'run.real.lock'
# 웍스 쪽 결과: 이 문구가 나오면 확실히 '보내지 않음'이다. '보냄'도 아니고 이것도 아니면 '보냈는지 모름'으로 본다
NOT_SENT = ['확인 실패: 보내지 않음', '로그인 필요', '로그인 실패', 'Could not connect', '메일쓰기 창 개수', 'aside 실행 실패']


def take_lock():
    """작업 스케줄러가 겹쳐 실행해도 한 번에 하나만 돈다. 20분 넘은 잠금은 죽은 것으로 본다."""
    try:
        if LOCK.exists() and (dtm.datetime.now().timestamp() - LOCK.stat().st_mtime) < 1200: return False
        LOCK.write_text(str(os.getpid()), encoding='utf-8'); return True
    except Exception:
        return False


async def main():
    if not take_lock(): say('건너뜀: 다른 발송기가 실행 중'); return 0
    try: return await _main()
    finally:
        try: LOCK.unlink()
        except Exception: pass


async def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--now'); ap.add_argument('--page')
    A = ap.parse_args()
    if CONF.get('mode') != 'test':
        say('멈춤: mode가 test가 아닙니다. live 발송은 아직 지원하지 않습니다.'); return 2
    now = dtm.datetime.fromisoformat(A.now) if A.now else dtm.datetime.now()
    page = (ROOT / A.page).resolve().as_uri() if A.page else CONF['page']
    L = ledger(); today = now.strftime('%Y-%m-%d'); sent_today = L['days'].get(today, 0)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME)
        pg = await (await b.new_context()).new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(page + '#k=' + CONF['key'] + '&s=' + CONF['sid'])
        try:
            await pg.wait_for_function('typeof R !== "undefined" && (R.ready || R.state === "boot")', timeout=90000)
        except Exception:
            say('실패: 보드를 열지 못함'); await b.close(); return 1
        if not await pg.evaluate('R.ready'):
            say('실패: 서버 연결 안 됨', await pg.evaluate('R.err')); await b.close(); return 1
        cands = await pg.evaluate(PICK)

        async def note(msg, rec=None):
            await pg.evaluate("([m, r]) => { if (r) { S.sent.unshift(Object.assign({ts: stamp()}, r)); if (S.sent.length > 100) S.sent.length = 100; } log(m); render(); }", [msg, rec])
            await pg.wait_for_timeout(1500)
            try: await pg.wait_for_function('!R.busy && R.state === "saved"', timeout=60000)
            except Exception: say('주의: 기록을 서버에 저장하지 못함', await pg.evaluate('R.err'))

        rc = 0
        for c in cands:
            key = c['week'] + '|' + c['type']
            at = dtm.datetime.fromisoformat(c['at'])
            late = (now - at).total_seconds() / 60
            tag = f"{c['week']} {c['name']} (예정 {c['at'][5:16].replace('T', ' ')})"
            if not c['resv']: say('건너뜀(예약 안 됨):', tag); continue
            if late < 0: say('아직 시각 전:', tag); continue
            if c['done'] or key in L['sent']: say('이미 보냄:', tag); continue
            if L['sent'].get(key + '|uncertain') or L['sent'].get(key + '|pending'):
                say('건너뜀(지난번 결과를 모름, 사람 확인 필요):', tag)
                if not L['sent'].get(key + '|uncertain'):
                    L['sent'][key + '|uncertain'] = now.isoformat(timespec='minutes'); save_ledger(L)
                    await note('자동 발송 결과 확인 필요: ' + c['name'] + '. 지난 실행이 중간에 끝났습니다. 받은 메일함을 확인해 주세요. 다시 보내지 않습니다.')
                continue
            if late > CONF.get('late_limit_min', 180):
                if L['sent'].get(key + '|missed'): continue
                say('놓침(시각이 너무 지남, 보내지 않음):', tag)
                if not A.dry:
                    L['sent'][key + '|missed'] = now.isoformat(timespec='minutes'); save_ledger(L)
                    await note('자동 발송 놓침: ' + c['name'] + ' (PC가 꺼져 있었거나 실행이 늦음). 필요하면 직접 보내 주세요.')
                continue
            if c['none']: say('보낼 대상 없음(모두 제출):', tag); continue
            if sent_today >= CONF.get('cap_per_day', 4): say('멈춤: 오늘 발송 상한', sent_today); rc = 1; break
            subject = '[시험] ' + c['subject']
            text = '[시험 발송] 실제 받는 사람: ' + (c['to'] or '-') + ' / 참조: ' + (c['cc'] or '-') + '\n\n' + c['body']
            M = {'to': CONF['test_to'], 'from': CONF['from'], 'subject': subject, 'text': text, 'bold': '■'}
            say('보낼 것:', tag, '| 고친 초안' if c['edited'] else '| 자동 초안', '| 받는 사람(시험) 1곳')
            if A.dry: continue
            # 보내기 전에 '진행 중'을 먼저 적는다. 실행이 중간에 죽어도 다음 실행이 다시 보내지 않게
            L['sent'][key + '|pending'] = now.isoformat(timespec='minutes'); save_ledger(L)
            out = run_aside(M, True)
            ok = '보냄' in out and '보내기 실패' not in out and '확인 실패' not in out
            not_sent = not ok and any(s in out for s in NOT_SENT) and '보내기 실패' not in out
            checks = next((l for l in out.splitlines() if l.startswith('{"붙여넣기처리"')), '')
            L['sent'].pop(key + '|pending', None)
            if ok:
                L['sent'][key] = now.isoformat(timespec='minutes'); L['days'][today] = sent_today = sent_today + 1; save_ledger(L)
                say('보냄:', tag)
                rec = {'type': c['type'], 'week': c['week'], 'how': '자동 발송(시험), 실제 받는 사람 대신 시험 주소', 'to': c['to']}
                await note('자동 발송(시험): ' + c['name'] + ' → 시험 주소 1곳', rec)
                # 서버에 이력이 실제로 남았는지 확인 (충돌로 빠졌으면 한 번 더)
                if not await pg.evaluate("([w, t]) => (S.sent || []).some(x => x.week === w && x.type === t && /자동 발송/.test(x.how || ''))", [c['week'], c['type']]):
                    say('주의: 발송 이력이 서버에서 빠져 다시 적음'); await note('자동 발송 이력 다시 기록: ' + c['name'], rec)
            elif not_sent:
                save_ledger(L); rc = 1
                say('보내지 않음(다음 실행 때 다시):', tag, '|', checks[:300] or out.strip().splitlines()[-1:])
                await note('자동 발송 실패(보내지 않음): ' + c['name'] + '. 웍스 로그인이나 메일쓰기 확인이 필요합니다. 다음 실행 때 다시 시도합니다.')
            else:
                L['sent'][key + '|uncertain'] = now.isoformat(timespec='minutes'); save_ledger(L); rc = 1
                say('결과 모름(다시 보내지 않음):', tag, '|', checks[:300] or out.strip().splitlines()[-2:])
                await note('자동 발송 결과 확인 필요: ' + c['name'] + '. 보내졌는지 확실하지 않습니다. 받은 메일함을 확인해 주세요. 다시 보내지 않습니다.')
        if errs: say('화면 오류:', errs[:3])
        await b.close()
    return rc

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
