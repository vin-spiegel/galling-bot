"""
Playwright + stealth로 DC 댓글 작성 테스트 (headless)

사전 설치:
  pip install playwright playwright-stealth
  playwright install chromium

실행:
  python3 tests/test_playwright_comment.py
"""
import asyncio
import re
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

BOARD_ID = "yjrs"
USERNAME = "여갤러"
PASSWORD = "1234"
COMMENT = "테스트 댓글"
HEADLESS = True


async def write_comment(board_id, doc_id, memo, username, password, headless=True):
    """Playwright로 DC 댓글 작성"""
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="ko-KR",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        # 댓글 작성 응답 캡처
        response_data = {}
        async def handle_response(response):
            if "comment_submit" in response.url:
                try:
                    response_data["status"] = response.status
                    response_data["text"] = await response.text()
                except Exception:
                    pass
        page.on("response", handle_response)

        # 글 상세 페이지 이동
        view_url = f"https://gall.dcinside.com/board/view/?id={board_id}&no={doc_id}"
        await page.goto(view_url, wait_until="domcontentloaded")

        # 사람처럼 천천히 스크롤
        await page.wait_for_timeout(2000)
        await page.evaluate("window.scrollBy({top: 500, behavior: 'smooth'})")
        await page.wait_for_timeout(1500)
        await page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
        await page.wait_for_timeout(2000)

        # 한 글자씩 타이핑 (사람처럼)
        await page.locator(f"input[id='name_{doc_id}']").type(username, delay=80)
        await page.wait_for_timeout(500)
        await page.locator(f"input[id='password_{doc_id}']").type(password, delay=80)
        await page.wait_for_timeout(500)
        await page.locator(f"textarea[id='memo_{doc_id}']").type(memo, delay=50)
        await page.wait_for_timeout(1500)

        # 등록 버튼 클릭
        await page.locator("button.repley_add").first.click(force=True)

        # 응답 대기
        await page.wait_for_timeout(3000)
        await browser.close()

        return response_data


async def get_latest_doc_id(board_id):
    """목록 페이지에서 최신 글 doc_id 추출"""
    import aiohttp
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession(headers=headers) as session:
        url = f"https://gall.dcinside.com/board/lists/?id={board_id}"
        async with session.get(url) as res:
            html = await res.text()
    matches = re.findall(r'no=(\d{5,})', html)
    return matches[0] if matches else None


async def main():
    doc_id = await get_latest_doc_id(BOARD_ID)
    if not doc_id:
        print("글을 찾을 수 없습니다.")
        return

    print(f"대상 글: {doc_id}")
    result = await write_comment(BOARD_ID, doc_id, COMMENT, USERNAME, PASSWORD, HEADLESS)

    print(f"\n=== 결과 ===")
    print(f"상태: {result.get('status', 'N/A')}")
    print(f"응답: {result.get('text', 'N/A')[:300]}")


if __name__ == "__main__":
    asyncio.run(main())
