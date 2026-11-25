/* 본부의제 보드 저장 서버 (구글 시트에 붙은 Apps Script 웹 앱)
 * 화면은 POST {op, key, who, args} 를 보내고 {ok, data | error} 를 받는다.
 * 키는 코드에 두지 않는다. 스크립트 속성 ADMIN_KEY(관리), INPUT_KEY(팀장 입력)에만 둔다.
 * 저장 단위(조각): core = 공통 상태, team:<팀> = 이번 주 그 팀의 안건과 제출 상태.
 * 조각마다 버전이 있어, 다른 사람이 먼저 고친 조각은 덮어쓰지 않고 최신 내용을 돌려준다.
 */
const SH_STORE = 'store', SH_LOG = 'log', SH_VIEW = '안건';
const CHUNK = 45000; // 셀 하나에 5만 자까지라 나눠 담는다
const PROPS = PropertiesService.getScriptProperties();

function doGet() { return out({ ok: true, data: 'hq-agenda' }); }

function doPost(e) {
  let res;
  try {
    const q = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const role = roleOf(q.key);
    const who = String(q.who || '').slice(0, 60);
    const args = q.args || {};
    if (q.op === 'get') res = { ok: true, data: opGet(role, args) };
    else if (q.op === 'put') res = { ok: true, data: withLock(() => opPut(role, who, args)) };
    else throw new Error('알 수 없는 요청');
  } catch (err) {
    res = { ok: false, error: String((err && err.message) || err) };
  }
  return out(res);
}

function out(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

function roleOf(key) {
  const a = PROPS.getProperty('ADMIN_KEY'), i = PROPS.getProperty('INPUT_KEY');
  if (!a && !i) throw new Error('서버에 키가 아직 설정되지 않았습니다');
  if (!key) throw new Error('키가 필요합니다');
  if (a && key === a) return 'admin';
  if (i && key === i) return 'input';
  throw new Error('키가 맞지 않습니다');
}

function withLock(fn) {
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try { return fn(); } finally { lock.releaseLock(); }
}

/* ---------- 시트 ---------- */
function book() { return SpreadsheetApp.getActiveSpreadsheet(); }
function sheet(name, head) {
  const b = book();
  let s = b.getSheetByName(name);
  if (!s) { s = b.insertSheet(name); s.appendRow(head); s.setFrozenRows(1); }
  return s;
}
const storeSheet = () => sheet(SH_STORE, ['key', 'ver', 'at', 'who', 'json']);
const logSheet = () => sheet(SH_LOG, ['at', 'who', 'role', 'op', 'msg']);

/* store 시트: 한 줄에 조각 하나. json은 E열부터 나눠 담는다 */
function readStore() {
  const s = storeSheet(), n = s.getLastRow() - 1, map = {};
  if (n < 1) return map;
  const w = s.getLastColumn(), v = s.getRange(2, 1, n, w).getValues();
  v.forEach((r, i) => { if (r[0]) map[r[0]] = { row: i + 2, ver: Number(r[1]) || 0, json: r.slice(4).join('') }; });
  return map;
}
function writeSlice(map, k, json, who) {
  const s = storeSheet(), cur = map[k], ver = (cur ? cur.ver : 0) + 1;
  const parts = []; for (let i = 0; i < json.length; i += CHUNK) parts.push(json.slice(i, i + CHUNK));
  const row = cur ? cur.row : s.getLastRow() + 1;
  if (cur) s.getRange(row, 5, 1, Math.max(1, s.getLastColumn() - 4)).clearContent();
  const vals = [k, ver, new Date(), who].concat(parts.length ? parts : ['']);
  s.getRange(row, 1, 1, vals.length).setNumberFormat('@').setValues([vals.map(String)]);
  s.getRange(row, 2).setNumberFormat('0').setValue(ver);
  s.getRange(row, 3).setNumberFormat('yyyy-mm-dd hh:mm:ss').setValue(new Date());
  map[k] = { row, ver, json };
  return ver;
}

/* ---------- 요청 ---------- */
function opGet(role, args) {
  const map = readStore(), have = args.have || {}, slices = [];
  Object.keys(map).forEach(k => { if (map[k].ver !== Number(have[k])) slices.push({ k, ver: map[k].ver, json: map[k].json }); });
  return { role, slices, keys: Object.keys(map), log: recentLog(150) };
}

function opPut(role, who, args) {
  let map = readStore(), teamTouched = false;
  const vers = {}, conflicts = [], denied = [], dropped = [];
  // 관리 키만: 화면에 더는 없는 팀 조각을 먼저 지운다 (데이터를 통째로 바꿨을 때). 아래쪽 줄부터 지워 줄 번호가 밀리지 않게 한다
  if (role === 'admin') {
    const sent = new Set((args.slices || []).map(x => String(x.k || '')));
    const gone = (args.drop || []).map(String).filter(k => /^team:.+/.test(k) && map[k] && !sent.has(k));
    gone.sort((x, y) => map[y].row - map[x].row).forEach(k => { storeSheet().deleteRow(map[k].row); dropped.push(k); });
    if (dropped.length) { map = readStore(); teamTouched = true; }
  }
  (args.slices || []).forEach(x => {
    const k = String(x.k || '');
    if (!/^(core|team:.+)$/.test(k)) return;
    if (role !== 'admin' && k === 'core') { denied.push(k); return; }
    const cur = map[k], have = Number(x.ver) || 0;
    if ((cur ? cur.ver : 0) !== have) { conflicts.push({ k, ver: cur ? cur.ver : 0, json: cur ? cur.json : '' }); return; }
    JSON.parse(x.json); // 깨진 내용은 저장하지 않는다
    vers[k] = writeSlice(map, k, String(x.json), who);
    if (k.indexOf('team:') === 0) teamTouched = true;
  });
  const ls = logSheet(), now = new Date(), rows = [];
  dropped.forEach(k => rows.push([now, who, role, 'drop', k]));
  (args.logs || []).slice(0, 50).forEach(l => rows.push([now, who, role, 'log', String(l.msg || '').slice(0, 500)]));
  Object.keys(vers).forEach(k => rows.push([now, who, role, 'save', k + ' v' + vers[k]]));
  conflicts.forEach(c => rows.push([now, who, role, 'conflict', c.k]));
  denied.forEach(k => rows.push([now, who, role, 'denied', k]));
  if (rows.length) ls.getRange(ls.getLastRow() + 1, 1, rows.length, 5).setValues(rows);
  if (teamTouched || vers.core) { try { rebuildView(map); } catch (e) { ls.appendRow([now, who, role, 'view-error', String(e)]); } }
  return { vers, conflicts, denied, dropped, log: recentLog(150) };
}

function recentLog(n) {
  const s = logSheet(), last = s.getLastRow();
  if (last < 2) return [];
  const from = Math.max(2, last - n * 3), v = s.getRange(from, 1, last - from + 1, 5).getValues();
  return v.filter(r => r[3] === 'log').slice(-n).reverse()
    .map(r => ({ ts: Utilities.formatDate(new Date(r[0]), 'Asia/Seoul', 'M/d HH:mm'), at: r[1], msg: r[4] }));
}

/* ---------- 사람이 보는 안건 시트 (저장할 때마다 다시 만든다) ---------- */
function rebuildView(map) {
  if (!map.core) return;
  const core = JSON.parse(map.core.json), a = core.active || {};
  const cats = {}; (core.cats || []).forEach(c => { cats[c.id] = c.name; });
  const order = (core.teams || []).map(t => t.name);
  const head = ['주차', '팀', '제출', '분류', '소분류', '유형', '제목', '현황', '원인', '계획', '내용'];
  const rows = [];
  const teams = Object.keys(map).filter(k => k.indexOf('team:') === 0).map(k => k.slice(5));
  teams.sort((x, y) => (order.indexOf(x) + 1 || 999) - (order.indexOf(y) + 1 || 999));
  teams.forEach(t => {
    const s = JSON.parse(map['team:' + t].json), sub = s.subs ? '제출 ' + s.subs + (s.late ? ' (마감 후)' : '') : '미제출';
    const items = s.items || [];
    if (!items.length) rows.push([a.label || '', t, sub, '', '', '', '(안건 없음)', '', '', '', '']);
    items.forEach(i => rows.push([a.label || '', t, sub, cats[i.cat] || i.cat || '', i.sub || '', i.type || '', i.title || '', i.now || '', i.cause || '', i.plan || '', i.detail || '']));
  });
  const s = book().getSheetByName(SH_VIEW) || book().insertSheet(SH_VIEW, 0);
  s.clearContents();
  s.getRange(1, 1, 1, head.length).setValues([head]).setFontWeight('bold');
  if (rows.length) s.getRange(2, 1, rows.length, head.length).setNumberFormat('@').setValues(rows);
  s.setFrozenRows(1);
}

/* 처음 한 번 편집기에서 실행: 권한 승인과 시트 만들기. 키는 프로젝트 설정의 스크립트 속성에 직접 넣는다 */
function setup() {
  storeSheet(); logSheet();
  if (!book().getSheetByName(SH_VIEW)) book().insertSheet(SH_VIEW, 0);
  const has = !!(PROPS.getProperty('ADMIN_KEY') || PROPS.getProperty('INPUT_KEY'));
  Logger.log(has ? '키 설정됨' : '키가 없습니다: 프로젝트 설정 > 스크립트 속성에 ADMIN_KEY, INPUT_KEY를 넣어 주세요');
}
