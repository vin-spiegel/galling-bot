import asyncio
import logging
from playwright.async_api import async_playwright
from playwright_stealth import Stealth


class PlaywrightCommentManager:
    """
    Playwright 기반 DC 댓글 작성 매니저.
    브라우저/컨텍스트를 재사용하고 댓글마다 새 페이지를 띄운다.
    """

    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    def __init__(self, board_id, username, password, headless=True):
        self.board_id = board_id
        self.username = username
        self.password = password
        self.headless = headless

        self._stealth_ctx = None
        self._playwright = None
        self._browser = None
        self._context = None
        self._started = False
        self._lock = asyncio.Lock()

    async def start(self):
        """브라우저/컨텍스트 초기화 (봇 시작 시 1회)"""
        if self._started:
            return

        self._stealth_ctx = Stealth().use_async(async_playwright())
        self._playwright = await self._stealth_ctx.__aenter__()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            user_agent=self.USER_AGENT,
            locale="ko-KR",
            viewport={"width": 1280, "height": 800},
        )
        self._started = True
        logging.info("[Playwright] 브라우저 초기화 완료")

    async def close(self):
        """종료 시 호출"""
        if not self._started:
            return

        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._stealth_ctx:
                await self._stealth_ctx.__aexit__(None, None, None)
        except Exception as e:
            logging.error(f"[Playwright] 종료 실패: {e}")
        finally:
            self._started = False
            logging.info("[Playwright] 브라우저 종료")

    async def _ensure_started(self):
        if not self._started:
            await self.start()

    async def write_comment(self, document_id, content):
        """
        댓글 작성. 성공 시 comment_id 반환, 실패 시 None.
        """
        async with self._lock:
            await self._ensure_started()

            page = None
            try:
                page = await self._context.new_page()

                response_data = {}

                async def handle_response(response):
                    if "comment_submit" in response.url:
                        try:
                            response_data["status"] = response.status
                            response_data["text"] = await response.text()
                        except Exception:
                            pass

                page.on("response", handle_response)

                view_url = f"https://gall.dcinside.com/board/view/?id={self.board_id}&no={document_id}"
                await page.goto(view_url, wait_until="domcontentloaded", timeout=20000)

                # 사람처럼 스크롤
                await page.wait_for_timeout(1500)
                await page.evaluate("window.scrollBy({top: 500, behavior: 'smooth'})")
                await page.wait_for_timeout(1000)
                await page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
                await page.wait_for_timeout(1500)

                # 입력 (한 글자씩)
                await page.locator(f"input[id='name_{document_id}']").type(
                    self.username, delay=80
                )
                await page.wait_for_timeout(300)
                await page.locator(f"input[id='password_{document_id}']").type(
                    self.password, delay=80
                )
                await page.wait_for_timeout(300)
                await page.locator(f"textarea[id='memo_{document_id}']").type(
                    content, delay=30
                )
                await page.wait_for_timeout(1000)

                # 등록 버튼
                await page.locator("button.repley_add").first.click(force=True)

                # 응답 대기 (최대 8초)
                for _ in range(16):
                    if "text" in response_data:
                        break
                    await page.wait_for_timeout(500)

                text = response_data.get("text", "")
                if not text:
                    logging.error(f"[Playwright] 댓글 응답 없음 (doc_id: {document_id})")
                    return None

                # 성공 응답: "숫자" (comment_id만)
                # 실패 응답: "false||사유" 형태
                if text.startswith("false"):
                    logging.error(f"[Playwright] 댓글 실패: {text[:200]}")
                    return None

                # 성공
                comment_id = text.strip().split("||")[0]
                return comment_id

            except Exception as e:
                logging.error(f"[Playwright] 댓글 작성 예외: {type(e).__name__}: {e}")
                return None
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
