"""실제 데이터(data.real.json)의 틀만 남기고 내용을 전부 예시로 바꿔 data.sample.json을 만든다.
팀 이름, 사람 이름, 안건 내용, 링크가 하나도 넘어가지 않게 한다."""
import json, pathlib
root = pathlib.Path(__file__).parent.parent
real = json.loads((root / 'data/data.real.json').read_text(encoding='utf-8'))
heads = ['가 사업부장', '나 센터장', '다 사업부장', '라 사업부장']
org = [{'head':heads[0], 'div':'1사업부', 'chk':'확인담당 1'}, {'head':heads[1], 'div':'센터', 'chk':'확인담당 1'},
       {'head':heads[2], 'div':'2사업부', 'chk':'확인담당 2'}, {'head':heads[3], 'div':'3사업부', 'chk':'확인담당 2'}]
teams = [{'name':'가나다라마바사아자차카타파하거너더러'[i] + '팀', 'head':heads[i // 4] if i < 16 else '', 'mail':''} for i in range(18)]
names = [t['name'] for t in teams]
cats = [{'id':'cvo', 'name':'중점과제', 'subs':['과제 A', '과제 B', '기타']}, {'id':'kpi', 'name':'KPI', 'subs':['제품', '매출']},
        {'id':'core', 'name':'핵심역량', 'subs':['도입', '계약', '파트너사']}, {'id':'hr', 'name':'인재육성', 'subs':['인력 이슈']}]
def week(label, meeting, k):
    cells, status = {}, {}
    for i, n in enumerate(names):
        if (i + k) % 6 == 5: cells[n] = {}; status[n] = 'none'; continue
        c = {'cvo':'없음', 'core':'없음', 'hr':'없음'}
        c['kpi'] = f'[예시 품목 {i+1}]\n - 이번 달 목표 대비 진행 상황 (예시 문장)\n - 다음 주 계획 (예시 문장)'
        if i % 4 == 0: c['cvo'] = f'* 예시 과제 {i+1} 진행 건 : 일정 확인 중 (예시 문장)'
        if i % 5 == 0: c['core'] = f'[예시 협력사 {i+1}]\n - 계약 검토 진행 (예시 문장)'
        if i % 7 == 3: c.pop('hr'); status[n] = 'partial'
        else: status[n] = 'full'
        cells[n] = c
    return {'label':label, 'meeting':meeting, 'teams':names, 'cells':cells, 'status':status}
history = [week('11월 3주', '2026-11-16', 0), week('11월 2주', '2026-11-09', 1), week('11월 1주', '2026-11-02', 2)]
feedback = [{'id':'f1', 'date':'2026-11-16', 'team':names[0], 'ref':'예시 품목 1', 'kind':'지시', 'text':'남은 기간 계획을 일자별로 정리해 다음 주에 보고 (예시)', 'due':'2026-11-20', 'status':'open', 'demo':True},
            {'id':'f2', 'date':'2026-11-09', 'team':names[2], 'ref':'예시 품목 3', 'kind':'확인 요청', 'text':'주 단위로 숫자 확인 (예시)', 'due':'2026-11-13', 'status':'open', 'demo':True}]
sample = ('(예시 녹취록입니다. 실제 발언이 아닙니다.)\n참석자 1 00:42\n가팀은 이번 달 목표까지 조금 남았네요. 남은 기간 계획을 일자별로 정리해서 다음 주에 보고해 주세요.\n'
          '참석자 1 03:15\n다팀 건은 진행 숫자를 매주 확인해 주세요.\n참석자 2 05:02\n마팀 자료는 잘 봤습니다.\n')
conf = {'unit':'예시 본부', 'link':'https://example.com/board', 'org':org, 'owner':'주인팀장', 'team':names[1], 'to':'사업부장 4명', 'cc':'직책자 전체', 'keys':['예시 품목 1', '예시 과제 1'], 'sample':sample}
out = {'cats':cats, 'teams':teams, 'history':history, 'feedback':feedback, 'conf':conf}
assert set(out) == set(real), (set(out) ^ set(real))
(root / 'data/data.sample.json').write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print('sample ok', len(json.dumps(out, ensure_ascii=False)))
