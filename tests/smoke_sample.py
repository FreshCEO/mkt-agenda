"""예시 데이터 화면(dist/index.html) 기본 동작 확인. 공개 배포 전에 돌린다.
  python build.py sample && python tests/smoke_sample.py"""
import asyncio, os, pathlib, shutil
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
async def main():
    async with async_playwright() as p:
        exe = os.environ.get('CHROME') or shutil.which('google-chrome') or shutil.which('chrome')
        b = await p.chromium.launch(**({'executable_path': exe} if exe else {}), args=['--no-sandbox'])
        pg = await (await b.new_context(viewport={'width':1360,'height':900})).new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto((ROOT / 'dist/index.html').as_uri()); await pg.wait_for_timeout(600)
        ok = []
        ok.append(('4단계가 보임', await pg.locator('.ph').count() == 4))
        ok.append(('현황판 18팀', await pg.locator('.tb').count() == 18))
        for k in ['chk', 'pub', 'mtg']:
            await pg.click(f'.ph[data-k={k}]'); await pg.wait_for_timeout(150)
        await pg.click('[data-act=trSample]'); await pg.wait_for_timeout(200)
        ok.append(('예시 녹취록에서 요약이 올라옴', await pg.locator('.nt').count() >= 1))
        while await pg.evaluate('S.active.stage') < 5: await pg.click('[data-act=next]'); await pg.wait_for_timeout(40)
        await pg.click('[data-act=rollover]'); await pg.wait_for_timeout(200)
        await pg.click('.top .tab[data-k=history]'); await pg.wait_for_timeout(200)
        ok.append(('주차를 넘기면 히스토리에 피드백 칸이 생김', await pg.locator('.ht-fb').count() >= 1))
        await pg.click('.top .tab[data-k=settings]'); await pg.wait_for_timeout(150)
        ok.append(('스크립트 오류 없음', not errs))
        await b.close()
        for n, v in ok: print(('PASS ' if v else 'FAIL ') + n)
        print(errs if errs else '')
        raise SystemExit(0 if all(v for _, v in ok) else 1)
asyncio.run(main())
