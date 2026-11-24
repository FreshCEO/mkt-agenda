# 본부의제 보드

매주 본부미팅 안건을 모으는 화면이다. 전체 인수인계는 `docs/작업지시서.md`에 있다. 작업 전에 반드시 읽는다.

## 자주 쓰는 명령

```
python build.py sample && python tests/smoke_sample.py && python tools/check_public.py   # 공개용
python build.py real && python tests/test_real.py                                        # 내 PC 전용 (58개)
python build.py sample && python tests/test_sample.py                                    # 공개용 시나리오 (Actions에서도 돈다)
git config core.hooksPath .githooks                                                      # 새로 받은 PC에서 한 번: 커밋 전 공개 점검 훅
```

## 지킬 것

1. 실제 데이터는 올리지 않는다. `data/data.real.json`, `dist/index.real.html`, `tests/test_real.py`는 커밋 금지다. `.gitignore`의 해당 줄을 지우지 않는다.
2. 커밋 전과 배포 전에 `python tools/check_public.py`를 통과시킨다.
3. 사람 이름, 메일 주소, 구글 시트 주소, 키 값을 코드, 문서, 커밋 메시지, PR에 쓰지 않는다. 시트와 스크립트 속성에서만 읽는다.
4. 메일은 시험 모드가 기본이다. 실제 수신자에게 가는 메일은 보내지 않는다. `MAIL_MODE`를 `live`로 바꾸는 일은 하지 않는다.
5. 메일 양식을 만드는 `mailText`, `mailHtml`, `fillTpl`의 출력은 글자 하나도 바꾸지 않는다. 서버로 옮길 때 화면 출력과 대조 테스트를 한다.
6. 화면 디자인과 문구는 이번 범위가 아니다. 연결에 꼭 필요한 곳만 고친다.
7. main에 바로 올리지 않는다. 브랜치, 테스트 결과, 화면 캡처, PR 순서로 한다.
8. 모르는 것은 지어내지 않고 "확인 필요"로 남긴다.

## 구조 한눈에

- `src/template.html`: 화면 전체. `render()`가 `#app`을 다시 그린다. 동작은 `A` 객체, 상태는 `S` 객체.
- `data/*.json`: 화면에 끼워 넣는 데이터. `conf`에 이름, 링크, 예시 문구가 들어 있다.
- `build.py`: 글꼴과 데이터를 `template.html`에 끼워 `dist/`에 한 파일로 만든다.
- `server/`: Apps Script 코드 (clasp).
