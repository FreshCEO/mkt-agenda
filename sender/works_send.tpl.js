// 웍스 메일 발송: 붙여넣기 한 번 -> 본문만 14px -> 글자 단위 대조, 서명 그대로, 받는 사람 1명 확인 -> 통과할 때만 보내기
const M = __MAIL__;
const SEND = __SEND__;
const step = [];
for (const t of (await listBrowserTabs()).filter(t => /write\/popup/.test(t.url || ''))) { const x = await attachBrowserTab(t.targetId); x.on('dialog', d => d.accept()); try { await x.evaluate(() => window.close()); } catch (e) {} }
await sleep(800);
// 메일함 열기. 로그인이 풀려 있으면 저장된 값으로 채워진 경우에만 [로그인] 버튼을 누른다 (값을 입력하거나 읽지 않는다)
const pm = await openTab('https://mail.worksmobile.com/'); await sleep(3000);
if (/sr\.daewoong|auth\.worksmobile/.test(pm.url())) {
  const ls = await snapshot(pm, { interactive: true });
  const filled = /textbox "아이디 입력"[^\n]*: "/.test(ls.tree) && /textbox "비밀번호 입력"[^\n]*: "/.test(ls.tree);
  if (!filled) throw new Error('로그인 필요: 자동 채움 안 됨');
  await pm.getByRole('button', { name: '로그인', exact: true }).click(); await sleep(5000);
  if (!/mail\.worksmobile\.com\/w\//.test(pm.url())) throw new Error('로그인 실패');
}
await pm.getByRole('link', { name: '메일쓰기', exact: true }).first().click(); await sleep(2000);
const ws = (await listBrowserTabs()).filter(t => /write\/popup/.test(t.url || ''));
if (ws.length !== 1) throw new Error('메일쓰기 창 개수 ' + ws.length);
const pw = await attachBrowserTab(ws[0].targetId);
// 보내는 주소 고르기 (M.from이 있을 때)
if (M.from) {
  await pw.getByRole('textbox', { name: '보내는 주소' }).click(); await sleep(800);
  await pw.getByRole('link', { name: M.from, exact: true }).first().click(); await sleep(1000);
}
const fromNow = await pw.getByRole('textbox', { name: '보내는 주소' }).inputValue();
const nameNow = await pw.getByRole('textbox', { name: '보내는 이름' }).inputValue();
const body = pw.frameLocator('iframe').first().locator('body');
const signBefore = await body.evaluate(b => { const s = b.querySelector('[data-workseditor=sign-content]'); return s ? s.textContent : null; });
const toBox = pw.getByRole('combobox', { name: '받는사람' });
await toBox.click(); await toBox.fill(M.to); await toBox.press('Enter');
await pw.getByRole('textbox', { name: '제목' }).fill(M.subject);
await body.click({ position: { x: 5, y: 5 } }); await pw.keyboard.press('Control+Home');
const handled = await body.evaluate((b, text) => { const dt = new DataTransfer(); dt.setData('text/plain', text); const ev = new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }); const n = b.ownerDocument.getSelection().anchorNode; (n && n.nodeType === 3 ? n.parentElement : (n || b)).dispatchEvent(ev); return ev.defaultPrevented; }, M.text);
await sleep(800);
// 본문 줄만 선택해서 14px
await body.evaluate(b => { const s = b.querySelector('[data-workseditor=sign-content]'); const kids = [...s.parentElement.children]; const si = kids.indexOf(s); let last = si - 1; while (last > 0 && !kids[last].textContent.trim()) last--; const r = b.ownerDocument.createRange(); r.setStartBefore(kids[0].firstChild || kids[0]); r.setEndAfter(kids[last].lastChild || kids[last]); const sel = b.ownerDocument.getSelection(); sel.removeAllRanges(); sel.addRange(r); });
await pw.getByRole('button', { name: /^크기/ }).click();
await pw.getByRole('link', { name: '가나다(14px)', exact: true }).click();
await sleep(500);
// 확인
const r = await body.evaluate(b => { const sign = b.querySelector('[data-workseditor=sign-content]'); if (!sign) return { err: '서명 없음' }; const kids = [...sign.parentElement.children]; const si = kids.indexOf(sign); const els = kids.slice(0, si).flatMap(k => [k, ...k.querySelectorAll('*')]).filter(e => [...e.childNodes].some(c => c.nodeType === 3 && c.textContent.trim())); return { lines: kids.slice(0, si).map(k => k.textContent), signText: sign.textContent, sizes: [...new Set(els.map(e => getComputedStyle(e).fontSize))], fonts: [...new Set(els.map(e => getComputedStyle(e).fontFamily.split(',')[0]))] }; });
const clean = a => { a = a.map(x => x.replace(/ /g, ' ').replace(/​/g, '').replace(/\s+$/, '')); while (a.length && !a[a.length - 1]) a.pop(); while (a.length && !a[0]) a.shift(); return a; };
const got = clean(r.lines || []), exp = clean(M.text.split('\n'));
let diff = -1; for (let i = 0; i < Math.max(got.length, exp.length); i++) if (got[i] !== exp[i]) { diff = i; break; }
const snap = await snapshot(pw, { interactive: true });
const chips = (snap.tree.match(/link "수정"/g) || []).length;
const subjOK = (await pw.getByRole('textbox', { name: '제목' }).inputValue()) === M.subject;
const toOK = snap.tree.includes('text: "' + M.to + '"');
const checks = { 붙여넣기처리: handled, 본문일치: diff < 0, 본문줄: got.length + '/' + exp.length, 서명그대로: r.signText === signBefore, 글자크기14: r.sizes && r.sizes.length === 1 && r.sizes[0] === '14px', 글꼴: r.fonts, 받는사람1명: chips === 1 && toOK, 제목일치: subjOK, 보내는주소: fromNow, 보내는이름: nameNow, 보내는주소일치: !M.from || fromNow === M.from };
console.log(JSON.stringify(checks));
if (diff >= 0) console.log('첫 차이 줄', diff, JSON.stringify(String(got[diff]).slice(0, 50)), '/', JSON.stringify(String(exp[diff]).slice(0, 50)));
const pass = handled && diff < 0 && checks.서명그대로 && checks.글자크기14 && checks.받는사람1명 && subjOK && checks.보내는주소일치;
if (!pass) { console.log('확인 실패: 보내지 않음'); }
else if (!SEND) { console.log('확인 통과 (보내지 않는 시험 실행)'); }
else {
  await pw.getByRole('button', { name: '임시저장', exact: true }).click(); await sleep(1200);
  await pw.getByRole('button', { name: '보내기', exact: true }).first().click(); await sleep(2500);
  // 메일링리스트 주소로 보낼 때 웍스가 띄우는 경고 창: 그 문구일 때만 [확인]
  if (M.from && (await listBrowserTabs()).some(t => /write\/popup/.test(t.url || ''))) {
    const ds = await snapshot(pw, { interactive: true });
    if (ds.tree.includes('메일링리스트 주소로 하여 발송하시겠습니까')) { await pw.getByRole('button', { name: '확인', exact: true }).last().click(); await sleep(3000); }
  }
  const left = (await listBrowserTabs()).some(t => /write\/popup/.test(t.url || ''));
  console.log(left ? '보내기 실패: 메일쓰기 창이 남아 있음' : '보냄');
}
