import asyncio
import logging
import re
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

    def __init__(self, board_id, username, password, headless=True, is_minor=False):
        self.board_id = board_id
        self.username = username
        self.password = password
        self.headless = headless
        self.is_minor = is_minor

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
            permissions=["clipboard-read", "clipboard-write"],
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

                prefix = "mgallery/board" if self.is_minor else "board"
                view_url = f"https://gall.dcinside.com/{prefix}/view/?id={self.board_id}&no={document_id}"
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

    async def write_article(self, title, content):
        """
        Playwright로 글 작성. URL은 paste로 넣어서 OG 카드 자동 생성.
        성공 시 doc_id(str) 반환, 실패 시 None.
        """
        async with self._lock:
            await self._ensure_started()

            page = None
            try:
                page = await self._context.new_page()

                prefix = "mgallery/board" if self.is_minor else "board"
                write_url = f"https://gall.dcinside.com/{prefix}/write/?id={self.board_id}"
                await page.goto(write_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)

                # 닉네임 입력 (display:none이면 보이게)
                name_input = page.locator("input#name")
                await name_input.evaluate(
                    "el => el.style.display = 'block'"
                )
                await name_input.fill("")
                await name_input.type(self.username, delay=80)
                await page.wait_for_timeout(300)

                # 비밀번호 입력
                await page.locator("input#password").type(
                    self.password, delay=80
                )
                await page.wait_for_timeout(300)

                # 제목 입력
                await page.locator("input#subject").type(title, delay=50)
                await page.wait_for_timeout(500)

                # 에디터에 본문 입력 (URL은 paste로)
                editor = page.locator("div.note-editable")
                await editor.click()
                await page.wait_for_timeout(300)

                lines = content.split("\n")
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if re.match(r'^https?://\S+$', stripped):
                        # URL 줄: paste 이벤트로 OG 카드 트리거
                        await page.evaluate("""(url) => {
                            const editor = document.querySelector('div.note-editable');
                            editor.focus();
                            const dt = new DataTransfer();
                            dt.setData('text/plain', url);
                            const evt = new ClipboardEvent('paste', {
                                clipboardData: dt,
                                bubbles: true,
                                cancelable: true,
                            });
                            editor.dispatchEvent(evt);
                        }""", stripped)
                        await page.wait_for_timeout(3000)  # OG 카드 생성 대기
                    elif stripped:
                        await editor.press_sequentially(stripped, delay=30)

                    # 줄바꿈 (마지막 줄 제외)
                    if i < len(lines) - 1:
                        await page.keyboard.press("Enter")
                        await page.wait_for_timeout(200)

                await page.wait_for_timeout(1000)

                # 등록 버튼 클릭
                await page.locator("button.btn_blue.btn_svc.write").click()

                # 페이지 이동 대기 (글 작성 성공 시 view 페이지로 리다이렉트)
                try:
                    await page.wait_for_url(
                        re.compile(r"view/\?id="), timeout=10000
                    )
                    # URL에서 doc_id 추출
                    url = page.url
                    match = re.search(r"[&?]no=(\d+)", url)
                    doc_id = match.group(1) if match else None
                    return doc_id
                except Exception:
                    # alert 처리
                    logging.error("[Playwright] 글 작성 후 리다이렉트 실패")
                    return None

            except Exception as e:
                logging.error(f"[Playwright] 글 작성 예외: {type(e).__name__}: {e}")
                return None
            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
