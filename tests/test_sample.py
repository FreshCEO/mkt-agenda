"""예시 데이터 화면(dist/index.html) 시나리오 테스트 58개와 시인성 점검. test_real.py의 시나리오를 예시 데이터(data/data.sample.json) 값으로 옮겼다.
  python build.py sample && python tests/test_sample.py
예시 데이터: 18팀(가팀~러팀), 1사업부 가~라팀, 센터 마~아팀, 2사업부 자~타팀, 3사업부 파~너팀, 더팀과 러팀은 사업부 미지정(확인 담당은 주인팀장).
시작 상태: 지난 주(11월 3주) 미제출 바팀, 타팀, 러팀과 입력 팀(나팀)을 뺀 14팀이 제출. 화면 동작을 바꾸면 이 테스트도 함께 고친다."""
import asyncio, re, json, os, tempfile
from playwright.async_api import async_playwright
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = (ROOT / 'dist/index.html').as_uri()   # 예시 데이터 화면 기준 시나리오 테스트 (python build.py sample 먼저)
R = []
def ck(name, cond, info=''):
    R.append((name, bool(cond))); print(('PASS ' if cond else 'FAIL ') + name + ((' | ' + str(info)) if info != '' and not cond else ''))
AUDIT = (ROOT / 'tests/audit.js').read_text(encoding='utf-8')
async def main():
    async with async_playwright() as p:
        import os, shutil
        exe = os.environ.get('CHROME') or shutil.which('google-chrome') or shutil.which('chrome')   # 없으면 playwright 기본 브라우저
        b = await p.chromium.launch(**({'executable_path': exe} if exe else {}), args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width':1360,'height':900}, accept_downloads=True)
        pg = await ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.add_init_script("window.__href=[]; const _c = HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click = function(){ if ((this.href||'').startsWith('mailto:')){ window.__href.push(this.href); return; } return _c.call(this); };")
        w = lambda ms=150: pg.wait_for_timeout(ms)
        ev = pg.evaluate
        audits = {}
        async def audit(name): audits[name] = await ev(AUDIT)
        async def to(i):
            ui = await pg.locator('[data-act=next]').count() > 0
            while await ev('S.active.stage') < i:
                if ui: await pg.click('[data-act=next]')
                else: await ev('A.next(); render()')
                await w(50)
            while await ev('S.active.stage') > i:
                if ui: await pg.click('[data-act=prev]')
                else: await ev('A.prev(); render()')
                await w(50)
        async def ph(k): await pg.click(f'.ph[data-k={k}]'); await w()
        async def box(tp):
            if not await pg.locator(f'details.mbox[data-tg=mo_{tp}]').evaluate('e => e.open'): await pg.locator(f'details.mbox[data-tg=mo_{tp}] > summary').click(); await w()
        tmp = tempfile.mkdtemp()
        await pg.goto(URL); await w(700)

        # ---- 구조와 일정 ----
        ck('01 제목용 서체 적용', await ev("document.fonts.check('700 20px \"Gmarket Sans\"')"))
        ck('02 사업부장 일정대로 4단계: 안건 기입, 사업부별 점검, 최종 공지, 출력과 본부미팅', await pg.locator('.ph .nm').all_inner_texts() == ['안건 기입', '사업부별 점검', '최종 공지', '출력과 본부미팅'])
        tm = await pg.locator('.ph .tm').all_inner_texts()
        ck('03 단계별 시각과 담당: 금 10시 각 팀장, 12시 사업부장과 센터장, 13시 주인팀장, 월 8시 전 출력', tm == ['금 10:00까지, 각 팀장', '금 12:00까지, 사업부장, 센터장', '금 13:00까지, 주인팀장', '월 08:00 전 출력, 주인팀장'], tm)
        ck('04 처음에는 1단계가 열려 있고 단계마다 한 줄 현황', await pg.locator('.sheet h2').inner_text() == '1. 안건 기입' and '제출 14/18팀, 미제출 4팀' in await pg.locator('.ph').nth(0).inner_text() and '점검 완료 0/4 사업부' in await pg.locator('.ph').nth(1).inner_text() and '출력 전, 미팅 요약 0건' in await pg.locator('.ph').nth(3).inner_text() and '입력 마감 11/20(금) 10:00' in await pg.locator('.flow-h').inner_text())
        await audit('1 안건 기입')

        # ---- 1단계: 현황판과 한 칸 입력, 메일 없음 ----
        ck('05 1단계에는 현황판과 입력만 있고 리마인드 메일은 없음', await pg.locator('.tb').count() == 18 and await pg.locator('.tb.no').count() == 4 and await pg.locator('.mbox').count() == 0 and '1사업부, 가 사업부장' in await pg.locator('.tb', has_text='가팀').inner_text())
        ck('06 입력은 안건마다 한 칸: 현황, 원인, 대응, 상세 칸 없음', await pg.locator('.draft').count() == 1 and await pg.locator('.draft textarea.one').count() == 1 and await pg.locator('[data-in=now],[data-in=cause],[data-in=plan]').count() == 0 and await pg.locator('.draft .f').count() == 0 and await pg.locator('.fbin').count() == 0 and '예시 품목 2' in await pg.locator('.draft textarea.one').input_value())
        # 예시 데이터에서 지난 주(11월 3주) 피드백은 가팀에만 있다. 입력 팀(나팀)에는 피드백이 없어 가팀을 골라 확인하고 나팀으로 돌아온다
        await pg.locator('.tb', has_text='가팀').click(); await w()
        ck('07 지난 주 본부미팅 피드백을 입력 화면 위에 참고로 보여 줌(쓰는 칸은 없음, 피드백이 있는 가팀 기준)', '예시 품목 1: 남은 기간 계획을 일자별로 정리해 다음 주에 보고 (예시)' in await pg.locator('.lastfb').inner_text() and await pg.locator('.lastfb textarea').count() == 0)
        await pg.locator('.tb', has_text='나팀').click(); await w()
        await pg.locator('.draft textarea.one').fill('예시 품목 2 목표 달성 계획 확정\n11/20 예시 홍보 예정, 대상은 예시 거래처 전체'); await pg.click('[data-act=submit]'); await w()
        ck('08 한 칸에 적고 바로 제출(15/18팀)', '제출 완료' in await pg.locator('.state').first.inner_text() and '제출 15/18팀' in await pg.locator('.ph').nth(0).inner_text() and await pg.locator('.err').last.inner_text() == '', await pg.locator('.err').last.inner_text())
        await pg.locator('.tb', has_text='바팀').click(); await w()
        await pg.click('[data-act=add][data-c=kpi]'); await w(); await pg.click('[data-act=submit]'); await w(); e1 = await pg.locator('.err').last.inner_text()
        ck('09 제목이 비었거나 분류를 비워 두면 제출을 막고 알려 줌', '안건을 쓰거나 없음' in e1 or '제목이 빈' in e1, e1)
        await pg.locator('.draft [data-act=del]').click(); await w()

        # ---- 2단계: 미제출 알람과 사업부별 점검 ----
        await to(1); await w()
        ck('10 금 10:00이 되면 기입 마감, 화면이 2단계 사업부별 점검으로 따라감', await ev('S.tab') == 'chk' and await pg.locator('.sheet h2').inner_text() == '2. 사업부별 점검' and await pg.locator('.ph.now .nm').inner_text() == '사업부별 점검')
        cks = await pg.locator('.cks .card').all_inner_texts()
        ck('11 확인 담당별 미제출: 확인담당 1(1사업부, 센터) 1팀, 확인담당 2(2, 3사업부) 1팀, 사업부 미지정 팀은 주인팀장 1팀', len(cks) == 3 and '확인담당 1 확인' in cks[0] and '1사업부, 센터' in cks[0] and '미제출 1팀' in cks[0] and '바팀' in cks[0] and '확인담당 2 확인' in cks[1] and '2사업부, 3사업부' in cks[1] and '미제출 1팀' in cks[1] and '타팀' in cks[1] and '주인팀장 확인' in cks[2] and '미제출 1팀' in cks[2] and '러팀' in cks[2], cks)
        await box('remind'); mr = await ev("mailOf('remind')")
        ck('12 미제출 알람 메일이 2단계에 있고 실제 리마인드 양식(본부미팅알람 명의, 마감 시각)으로 나옴', '금 10:00 미제출 알람' in await pg.locator('details.mbox[data-tg=mo_remind] > summary').inner_text() and mr['subject'] == '[리마인드] 11월 4주차 본부미팅 아젠다 취합 요청 건_11/20(금) 10:00' and mr['body'].startswith('팀장님 안녕하세요.' + chr(10) + '본부미팅알람입니다.') and '(~11/20(금) 10:00 까지)' in mr['body'] and '11/20(금) 10:00 기준으로 미작성자분들께 개별 리마인드' in mr['body'] and mr['body'].rstrip().endswith('본부미팅알람 올림'), mr['subject'])
        await pg.click('[data-act=chk][data-c="확인담당 2"]'); await w(); ms2 = await ev("mailOf('remind')")
        # 예시 팀에는 메일 주소가 없어 받는 사람 칸에 미제출 팀 이름이 들어간다
        ck('13 알람 범위를 확인담당 2 담당으로 좁히면 그 담당 미제출 팀에게만 감(보내는 이름은 본부미팅알람 그대로)', ms2['to'] == '타팀' and '바팀' not in ms2['to'] and '본부미팅알람 올림' in ms2['body'], (ms2['to'], ms2['body'][:120]))
        await pg.click('[data-act=chk][data-c=""]'); await w()
        await pg.locator('details.mbox[data-tg=mo_remind] [data-act=resv]').click(); await w()
        ck('14 예약해 둠으로 표시하면 일정에 예약됨', await pg.locator('.strip .mb.on').inner_text() == '예약됨' and await ev('S.sent[0].how') == '예약해 둠으로 표시, 금 10:00 발송')
        await audit('2 사업부별 점검')
        n_items = await ev("itemsOf(S.active.label).length")
        ck('15 점검 목록은 제출한 안건 수만큼, 사업부를 고르기 전에는 점검 완료 버튼 없음', await pg.locator('.ck').count() == n_items and n_items == 23 and await pg.locator('[data-act=fin]').count() == 0)
        await pg.click('[data-act=hd][data-h="다 사업부장"]'); await w(); bys = await pg.locator('.ck .by').all_inner_texts()
        ck('16 사업부를 고르면 그 사업부 안건만 보이고 점검 완료 버튼이 나옴', len(bys) == 5 and all('다 사업부장' in x for x in bys) and await pg.locator('[data-act=fin]').inner_text() == '2사업부 점검 완료')
        await pg.locator('.ck', has_text='예시 협력사 11').locator('[data-ch=inc]').uncheck(); await w()
        await pg.locator('.ck', has_text='예시 품목 10').locator('[data-in=memo]').fill('목표 2안으로 보고 (예시)'); await w()
        # 예시 데이터는 사업부마다 중점과제가 1건뿐이라 순서 바꾸기는 KPI 묶음(3건)의 첫 안건으로 확인한다
        kp = '.ck[style*="var(--kpi)"]'
        first = await pg.locator(kp + ' .ck-h b').first.inner_text(); await pg.locator(kp + ' [data-act=mv][data-d="1"]').first.click(); await w()
        ck('17 체크 해제, 코멘트, 순서 바꾸기', await pg.locator('.ck.off').count() == 1 and await pg.locator(kp + ' .ck-h b').nth(1).inner_text() == first)
        await pg.locator('.ck', has_text='예시 품목 11').locator('[data-act=open]').click(); await w()
        ck('18 내용 보기로 그 자리에서 원문 확인', len(await pg.locator('.ck', has_text='예시 품목 11').locator('.body').inner_text()) > 30)
        await pg.click('[data-act=fin]'); await w()
        ck('19 2사업부 점검 완료: 그 사업부 안건은 잠기고 단계 현황 1/4', '점검 완료 1/4 사업부' in await pg.locator('.ph').nth(1).inner_text() and await pg.locator('.ck [data-ch=inc]:disabled').count() == len(bys) and await pg.locator('.ck [data-in=memo]').count() == 0 and '사업부장 코멘트: 목표 2안으로 보고 (예시)' in await pg.locator('.ck', has_text='예시 품목 10').inner_text())
        await pg.click('[data-act=hd][data-h=""]'); await w()
        ck('20 다른 사업부 안건은 아직 고칠 수 있음', await pg.locator('.ck [data-ch=inc]:not(:disabled)').count() == n_items - len(bys))
        await pg.select_option('[data-ch=role]', 'owner'); await w()
        ck('21 주인팀장 화면: 점검 목록은 보기만, 알람 메일은 쓸 수 있음', await pg.locator('.ck [data-ch=inc]:not(:disabled)').count() == 0 and await pg.locator('[data-act=fin],[data-act=unfin]').count() == 0 and await pg.locator('.mbox').count() == 1)
        await pg.select_option('[data-ch=role]', 'lead'); await pg.select_option('[data-ch=roleTeam]', '카팀'); await w()
        lr = await pg.locator('.ck .by').all_inner_texts()
        ck('22 팀장 화면: 본인 팀 안건의 포함 여부와 코멘트만, 알람과 설정 없음', len(lr) >= 1 and all('카팀' in x for x in lr) and await pg.locator('.ck.off', has_text='예시 협력사 11').count() == 1 and await pg.locator('.mbox').count() == 0 and await pg.locator('.cks').count() == 0 and await pg.locator('.top .tab').all_inner_texts() == ['이번 주', '히스토리'] and await pg.locator('[data-act=next]').count() == 0)
        await ph('in'); ck('23 팀장 화면 1단계: 본인 입력만', await pg.locator('.tb').count() == 0 and await pg.locator('[data-act=submit]').count() == 1 and await pg.locator('.draft textarea.one').count() >= 1)
        await audit('1 안건 기입(팀장)')
        await pg.select_option('[data-ch=role]', 'head'); await w()

        # ---- 3단계: 최종 공지 ----
        await ph('chk'); await to(2); await w()
        ck('24 금 12:00이 되면 3단계 최종 공지로 따라감', await ev('S.tab') == 'pub' and await pg.locator('.sheet h2').inner_text() == '3. 최종 공지')
        chk = await pg.locator('.chk').inner_text()
        ck('25 공지 전 점검: 점검 안 마친 사업부 3곳, 미제출 3팀', '점검을 마치지 않은 사업부 3곳' in chk and '1사업부 가 사업부장' in chk and '미제출 3팀' in chk and '마감 후 추가 0팀' in chk, chk[:150])
        await audit('3 최종 공지')
        body = (await ev("mailOf('report')"))['body']; lines = body.split('\n')
        heads = ['1. 중점과제', '2. KPI(제품/매출)', '3. 핵심역량(도입/계약/파트너사)', '4. 인재육성(본부 내 인력 이슈)']
        ck('26 최종 공지 메일이 열린 채로 나오고 실제 보고 양식(인사, 회신 기한, 취합링크, 분류 제목, 본부미팅알람 올림)', await pg.locator('details.mbox[data-tg=mo_report]').evaluate('e => e.open') and '금 13:00 최종 공지' in await pg.locator('details.mbox[data-tg=mo_report] > summary').inner_text() and lines[0] == '사업부장님, 센터장님 안녕하세요.' and '11월 4주차 본부 미팅 아젠다 취합 내용을 아래와 같이 보고 드립니다.' in lines and any(l.startswith('검토 후 추가 또는 삭제가 필요한 의제가 있으시면, 월요일(23일) 오전 7시까지') for l in lines) and '[취합링크]' in lines and [l for l in lines if l[:2] in ('1.', '2.', '3.', '4.') and not l.startswith(' ')] == heads and body.rstrip().endswith('이상입니다.' + chr(10) * 3 + '본부미팅알람 올림'), [l for l in lines if l[:2] in ('1.', '2.', '3.', '4.')])
        ck('27 한 칸에 적은 내용이 메일에 그대로(N) 제목 / 사업부장, - 내용), 점검에서 뺀 안건은 빠짐', any(re.match(r'^ \d+\) 예시 품목 2 / 가 사업부장$', l) for l in lines) and '  - 예시 품목 2 목표 달성 계획 확정' in lines and '  - 11/20 예시 홍보 예정, 대상은 예시 거래처 전체' in lines and '예시 협력사 11' not in body and any(re.match(r'^\d\) 과제 A$', l) for l in lines) and '※ 미제출 3팀' in body, [l for l in lines if '예시 품목 2' in l or '예시 홍보' in l or '과제 A' in l])
        html = await ev("mailHtml(mailOf('report').body)")
        bold = await pg.locator('#mPv_report div[style*="font-weight:700"]').count()
        ck('28 서식: 번호 제목, N) 줄, ① 줄은 굵게', 'font-size:12pt;font-weight:700;margin-top:4px">1. 중점과제</div>' in html and any(('font-weight:700">' + x) in html for x in ['1) 과제 A', '2) 과제 A']) and bold >= 20, bold)
        await pg.fill('#mTo_report', 'a@test.example, b@test.example')
        await pg.click('[data-act=send][data-t=report]'); await w(300); href = await ev('window.__href')
        await pg.click('[data-act=mailCopy][data-t=report]'); await w(300)
        ck('29 메일 창 열기와 서식 그대로 복사', len(href) == 1 and href[0].startswith('mailto:a@test.example,b@test.example?') and '복사' in await pg.locator('.toast').inner_text())
        ck('30 취합본 카드(읽기 전용)와 사업부장 코멘트 표시', await pg.locator('.item').count() == n_items and await pg.locator('.item [data-ch=inc]').count() == 0 and '사업부장 코멘트: 목표 2안으로 보고 (예시)' in await pg.locator('.item', has_text='예시 품목 10').inner_text() and '공지 제외' in await pg.locator('.item', has_text='예시 협력사 11').inner_text())
        await to(3)
        await ph('in'); await pg.locator('.tb', has_text='나팀').click(); await w()
        await pg.locator('.draft textarea.one').fill('수정본: 홍보 일정 11/24로 변경'); await pg.click('[data-act=submit]'); await w()
        ck('31 최종 공지 뒤에 고치면 마감 후 제출로 표시되고 수정한 팀으로 기록', '마감 후 제출' in await pg.locator('.state').first.inner_text() and await ev("Object.keys(S.active.fix).join()") == '나팀')

        # ---- 4단계: 출력과 본부미팅 ----
        await ph('pub'); await to(4); await w()
        ck('32 월 08:00이 되면 4단계 출력과 본부미팅으로 따라감', await ev('S.tab') == 'mtg' and await pg.locator('.sheet h2').inner_text() == '4. 출력과 본부미팅' and '주인팀장 주인팀장' in await pg.locator('.sheet').inner_text())   # 예시 데이터는 주인팀장 이름 자리에 '주인팀장'이 들어 있다
        ck('33 수정한 팀 안내: 주인팀장과 소통 후 해당 팀장이 출력', '최종 공지 뒤에 고친 팀: 나팀' in await pg.locator('.sheet').inner_text() and '해당 팀장이 직접 출력' in await pg.locator('.sheet').inner_text())
        await pg.click('[data-act=paper]'); await w(); ptxt = await pg.locator('.paper').inner_text(); await pg.keyboard.press('Escape'); await w()
        ck('34 한 장 보기: 코멘트 반영, 뺀 안건 빠짐, 사업부별 점검 현황 표시', '목표 2안으로 보고 (예시)' in ptxt and '예시 협력사 11' not in ptxt and '사업부별 점검 완료 1 / 4' in ptxt and '수정본: 홍보 일정 11/24로 변경' in ptxt)
        await pg.click('[data-act=printed]'); await w()
        ck('35 출력 완료로 표시', '출력 완료' in await pg.locator('.sheet .state').first.inner_text() and '출력 완료, 미팅 요약 0건' in await pg.locator('.ph').nth(3).inner_text())
        ck('36 4단계에는 연속관리, 재보고, 완료 처리 같은 피드백 관리 칸이 없음', await pg.locator('.fb').count() == 0 and await pg.locator('[data-act=fbMode],[data-act=fbSet],[data-act=fbAll]').count() == 0 and await pg.locator('.mbox').count() == 0 and await pg.locator('text=연속관리').count() == 0)
        await to(5); await pg.click('[data-act=trSample]'); await w()
        nt = await ev("S.active.notes.map(n => [n.team, n.text.slice(0, 12)])")
        ck('37 녹취록을 넣으면 팀별 문장이 아래 요약정리에 올라옴(2건), 이름만 나온 문장 1건은 따로', [x[0] for x in nt] == ['가팀', '다팀'] and await pg.locator('.nt').count() == 2 and await pg.locator('[data-act=candAdd]').count() == 1, nt)
        await audit('4 출력과 본부미팅')
        await pg.locator('.nt textarea').first.fill('예시 품목 1 11월 목표 차이 해소 계획을 일자별로 정리해 다음 주 보고'); await w()
        await pg.locator('.nt [data-act=noteDel]').nth(1).click(); await w()   # 다팀 요약을 지운다
        await pg.click('[data-act=noteAdd]'); await w(); await pg.locator('.nt select').last.select_option('나팀'); await pg.locator('.nt textarea').last.fill('예시 품목 2 예시 메모 문장, 다음 주 다시 확인'); await w()
        await pg.click('[data-act=candAdd]'); await w()   # 마팀 문장
        ck('38 요약은 고치고, 지우고, 직접 추가할 수 있음(3건)', await pg.locator('.nt').count() == 3 and '출력 완료, 미팅 요약 3건' in await pg.locator('.ph').nth(3).inner_text())
        cp = os.path.join(tmp, '메모장_ANSI.txt'); open(cp, 'wb').write('카팀은 예시 품목 11 확보안을 금요일까지 정리해 주세요.'.encode('cp949'))
        await pg.set_input_files('#trFile', cp); await w(500)
        ck('39 메모장 ANSI 파일도 깨지지 않고 반영', await ev("S.active.notes.filter(n => n.src === '메모장_ANSI.txt').map(n => n.team + '/' + n.text.slice(0, 9)).join()") == '카팀/카팀은 예시 품목')
        await pg.select_option('[data-ch=role]', 'lead'); await pg.select_option('[data-ch=roleTeam]', '가팀'); await w()
        ck('40 팀장 화면 4단계: 본인 팀 요약만 읽기 전용, 한 장 보기와 인쇄는 가능', await pg.locator('.nt.ro').count() == 1 and '예시 품목 1 11월 목표 차이' in await pg.locator('.nt.ro').inner_text() and await pg.locator('#tr').count() == 0 and await pg.locator('[data-act=paper]').count() == 1 and await pg.locator('[data-act=printed]').count() == 0)
        await pg.select_option('[data-ch=role]', 'head'); await w()

        # ---- 다음 주차, 히스토리 ----
        async with pg.expect_download() as dl:
            await pg.click('.top .tab[data-k=settings]'); await w(); await pg.click('[data-act=export]')
        path = os.path.join(tmp, 'backup.json'); await (await dl.value).save_as(path)
        ck('41 설정: 사업부와 확인 담당, 데이터 내보내기', json.load(open(path, encoding='utf-8')).get('rev') == 4 and await pg.locator('.orgrow input').count() == 8 and await pg.locator('#s2').input_value() == '주인팀장')
        await audit('설정')
        await pg.click('.top .tab[data-k=now]'); await pg.click('[data-act=rollover]'); await w()
        ck('42 다음 주차 시작: 11월 5주, 1단계로 돌아가고 모든 팀 미제출', '11월 5주' in await pg.locator('.flow-h b').inner_text() and await ev('S.tab') == 'in' and await ev('Object.keys(S.active.subs).length') == 0 and await ev('S.active.notes.length') == 0)
        await pg.locator('.tb', has_text='나팀').click(); await w()
        ck('43 새 주차 입력 칸에 지난 주에 쓴 내용, 위에는 지난 주 미팅 요약', await pg.locator('.draft textarea.one').input_value() == '수정본: 홍보 일정 11/24로 변경' and '예시 품목 2 예시 메모 문장, 다음 주 다시 확인' in await pg.locator('.lastfb').inner_text() and '11월 4주' in await pg.locator('.lastfb').inner_text())
        await pg.click('.top .tab[data-k=history]'); await w()
        c1 = pg.locator('.ht', has=pg.locator('.ht-h b', has_text='가팀')).first
        ck('44 히스토리 11월 4주: 팀 칸 오른쪽에 본부미팅 피드백이 자동으로 들어감', await pg.locator('.wk button').first.inner_text() != '' and '11월 4주' in await pg.locator('.wk button.on').inner_text() and '예시 품목 1 11월 목표 차이 해소 계획을 일자별로 정리해 다음 주 보고' in await c1.locator('.ht-fb').inner_text() and '본부미팅 피드백' in await c1.locator('.ht-fb').inner_text())
        box_ok = await ev("(() => { const c = [...document.querySelectorAll('.ht')].find(x => x.querySelector('.ht-h b').textContent === '가팀'); const l = c.querySelector('.ht-b > div').getBoundingClientRect(), r = c.querySelector('.ht-fb').getBoundingClientRect(); return r.left >= l.right - 1 && r.width >= 280 && Math.abs(r.top - l.top) < 2; })()")
        ck('45 피드백 칸은 내용 오른쪽에 나란히 놓임', box_ok)
        c2 = pg.locator('.ht', has=pg.locator('.ht-h b', has_text='라팀')).first
        ck('46 피드백이 없는 팀은 기록 없음, 지운 요약(다팀)은 들어가지 않음, 따로 넣은 문장(마팀)은 들어감', '기록 없음' in await c2.locator('.ht-fb').inner_text() and '기록 없음' in await pg.locator('.ht', has=pg.locator('.ht-h b', has_text='다팀')).first.locator('.ht-fb').inner_text() and '마팀 자료는 잘 봤습니다' in await pg.locator('.ht', has=pg.locator('.ht-h b', has_text='마팀')).first.locator('.ht-fb').inner_text())
        await audit('히스토리(주차별)')
        hv = await ev("(() => { const a = [...document.querySelectorAll('.hv')]; return {n:a.length, cut:a.filter(e => e.scrollHeight > e.clientHeight + 1 || getComputedStyle(e).overflow === 'hidden').length}; })()")
        ck('47 히스토리 칸은 잘리지 않음', hv['n'] >= 15 and hv['cut'] == 0, hv)
        await pg.click('[data-act=hw][data-w="11월 1주"]'); await w()   # 예시 데이터에서 피드백 기록이 없는 주차
        ck('48 요약 기록이 없던 옛 주차는 피드백 칸 없이 넓게', await pg.locator('.ht-fb').count() == 0 and await pg.locator('.hv').count() > 5)
        # 예시 데이터에서 지난 주차 피드백이 있는 팀은 가팀(11월 3주)과 다팀(11월 2주)뿐이라 가팀으로 확인한다
        await pg.click('[data-act=hmode][data-m=team]'); await pg.click('[data-act=hT][data-t="가팀"]'); await w()
        wk = await pg.locator('.ht .ht-h b').all_inner_texts()
        ck('49 팀별 보기: 가팀의 주차 흐름과 주차별 피드백이 이어짐', wk == ['11월 4주', '11월 3주', '11월 2주', '11월 1주'] and '예시 품목 1 11월 목표 차이' in await pg.locator('.ht').nth(0).locator('.ht-fb').inner_text() and '남은 기간 계획을 일자별로 정리해 다음 주에 보고 (예시)' in await pg.locator('.ht').nth(1).locator('.ht-fb').inner_text() and '기록 없음' in await pg.locator('.ht').nth(2).locator('.ht-fb').inner_text() and await pg.locator('.ht').nth(3).locator('.ht-fb').count() == 0, wk)
        await audit('히스토리(팀별)')
        await pg.click('[data-act=key][data-k="예시 품목 1"]'); await w()
        ck('50 검색', await pg.locator('.hit').count() == 32, await pg.locator('.hit').count())   # 예시 품목 1, 10~18의 KPI 칸: 주차마다 10팀 중 미제출 2팀을 빼면 8칸, 4주치
        await pg.click('[data-act=key][data-k=""]'); await w()

        # ---- 설정 ----
        await pg.click('.top .tab[data-k=settings]'); await w()
        await pg.locator('[data-ch=ttime][data-i="1"]').fill('09:30'); await w()
        await pg.locator('[data-ch=ttime][data-i="3"]').fill('11:00'); await w(); bad = await pg.locator('.toast').inner_text()
        await pg.locator('.orgrow input[data-k=chk]').nth(1).fill('확인담당 2'); await w()
        await pg.click('.top .tab[data-k=now]'); await w()
        ck('51 설정에서 기입 마감을 금 09:30으로 바꾸면 단계와 마감 표시에 반영, 순서가 뒤바뀌는 시각은 거절', '금 09:30까지' in await pg.locator('.ph').nth(0).inner_text() and '입력 마감 11/27(금) 09:30' in await pg.locator('.flow-h').inner_text() and '순서가 맞지 않아' in bad and await ev('stT(3)') == '금 13:00')
        await ph('chk'); cks = await pg.locator('.cks .card').all_inner_texts()
        ck('52 확인 담당을 바꾸면 담당별 묶음이 바뀜(센터를 확인담당 2로)', '1사업부' in cks[0] and '센터' not in cks[0] and '센터' in cks[1], cks)
        await pg.click('.top .tab[data-k=settings]'); await w(); await pg.set_input_files('#imp', path); await w(400)
        ck('53 백업 파일로 복원(11월 4주, 요약 포함)', await ev('S.active.label') == '11월 4주' and await ev('S.active.notes.length') == 4)   # 요약 3건 + 메모장 파일 1건

        # ---- 실제 시계 ----
        await pg.click('[data-act=reset]'); await w()
        await ev("window.__now = '2026-11-20T10:05:00'; S.set.clock = 'real'; beat();"); await w()
        ck('54 실제 시계: 금 10:05면 기입 마감, 2단계로 따라가고 시점 버튼 숨김', await ev('S.active.stage') == 1 and await ev('S.tab') == 'chk' and await pg.locator('[data-act=prev]').count() == 0)
        await ph('in'); await pg.locator('.draft textarea.one').focus(); await pg.locator('.draft textarea.one').type(' 쓰는 중')
        await ev("window.__now = '2026-11-20T12:05:00'; beat();"); await w()
        still = await ev("document.activeElement && document.activeElement.dataset.in"); val = await pg.locator('.draft textarea.one').input_value(); tst = await pg.locator('.toast').inner_text()
        await pg.locator('.sheet h2').click(); await w(400)
        ck('55 글을 쓰는 중에 시점이 넘어가도 화면을 바꾸지 않고, 입력을 마치면 반영', still == 'detail' and '쓰는 중' in val and '입력을 마치면' in tst and await ev('S.active.stage') == 2 and await pg.locator('.ph.now .nm').inner_text() == '최종 공지', (still, tst))
        await ev("window.__now = '2026-11-23T08:10:00'; beat();"); await w(); s4 = await ev('S.active.stage')
        await ev("window.__now = '2026-11-24T09:05:00'; beat();"); await w()
        ck('56 실제 시계: 월 08:10 출력 시점, 화 09:05에 다음 주차가 열림', s4 == 4 and await ev('S.active.label') == '11월 5주' and await ev('S.tab') == 'in')
        await ev("window.__now = null; localStorage.clear()"); await pg.reload(); await w(500)

        # ---- 좁은 화면 ----
        await pg.set_viewport_size({'width':390,'height':800}); await w(300); over = {}
        for k in ['in','chk','pub','mtg']:
            await ph(k)
            if k == 'mtg': await pg.click('[data-act=trSample]'); await w()
            over[k] = await ev('document.documentElement.scrollWidth - window.innerWidth')
        for k in ['history','settings']:
            await pg.click(f'.top .tab[data-k={k}]'); await w(); over[k] = await ev('document.documentElement.scrollWidth - window.innerWidth')
        ck('57 휴대폰 폭(390px)에서 가로 넘침 없음', all(v <= 1 for v in over.values()), over)
        await pg.click('.top .tab[data-k=history]'); await w(); await pg.screenshot(path=str(ROOT / 'tests/mobile_hist.png'))
        ck('58 스크립트 오류 0건', not errs, errs)
        await b.close()
        print('\n== 시인성 점검 =='); tot = 0; allf = {}; mn = 99
        for k, v in audits.items():
            tot += v['n']; mn = min(mn, v['minFont']); print(f"{k}: 글자 요소 {v['n']}개, 최소 {v['minFont']}px, 미달 {len(v['fails'])}건")
            for f in v['fails']: allf[(f['cls'], f['color'])] = f
        for f in allf.values(): print('  미달:', f)
        print(f'\n결과: {sum(1 for r in R if r[1])}/{len(R)} 통과, 글자 요소 {tot}개 점검, 최소 글자 {mn}px, 명암비 미달 유형 {len(allf)}건')
        raise SystemExit(0 if R and all(v for _, v in R) and not allf else 1)   # 실패나 명암비 미달이 있으면 Actions가 멈추게
asyncio.run(main())
