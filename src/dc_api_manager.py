import logging
import random
import base64
import aiohttp
import lxml.html
import dc_api

DESKTOP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
}

class DcApiManager:
    def __init__(self, board_id, username, password):
        """
        DcApiManager 클래스를 초기화합니다.

        :param board_id: 게시판 ID
        :param username: 사용자 이름
        :param password: 사용자 비밀번호
        """
        self.board_id = board_id
        self.username = username
        self.password = password
        self.api = dc_api.API()

    async def start(self):
        """
        인스턴스를 시작합니다.
        """
        # 필요 시 초기화 작업을 여기에 추가합니다.
        pass

    async def close(self):
        """
        API 세션을 명시적으로 종료합니다.
        """
        try:
            await self.api.close()
            logging.info("API 세션이 종료되었습니다.")
        except Exception as e:
            logging.error(f"API 세션 종료 실패: {e}")

    async def write_document(self, title, content, is_minor=False):
        """
        문서를 게시합니다.

        :param title: 문서 제목
        :param content: 문서 내용
        :param is_minor: 부가적인 설정 (기본값: False)
        :return: None
        """
        try:
            await self.api.write_document(
                board_id=self.board_id,
                title=title,
                contents=content,
                name=self.username,
                password=self.password,
                is_minor=is_minor
            )
            # dc_api가 doc_id를 반환하지 않으므로 최신 글에서 조회
            doc_id = await self._find_recent_doc_id(title)
            logging.info(f"문서 작성 성공 : {title}")
            return doc_id
        except Exception as e:
            logging.error(f"문서 작성 실패 : {e}")
            return None

    async def _find_recent_doc_id(self, title):
        """최근 글 목록에서 제목이 일치하는 글의 ID를 찾습니다."""
        try:
            articles = [article async for article in self.api.board(board_id=self.board_id, num=5)]
            for article in articles:
                if article.title == title:
                    return article.id
        except Exception as e:
            logging.error(f"doc_id 조회 실패: {e}")
        return None

    async def write_comment(self, document_id, content):
        """
        문서에 댓글을 게시합니다.

        :param document_id: 문서 ID
        :param content: 댓글 내용
        :return: 댓글 ID 또는 None
        """
        try:
            comment_id = await self.api.write_comment(
                board_id=self.board_id,
                document_id=document_id,
                name=self.username,
                password=self.password,
                contents=content
            )
            logging.info(f"댓글 작성 성공 ({document_id}) : {content}")
            return comment_id
        except Exception as e:
            logging.error(f"댓글 작성 실패 ({document_id}): {type(e).__name__}: {e}")
            return None

    async def get_document_contents(self, document_id):
        """문서 본문 텍스트를 가져옵니다."""
        try:
            doc = await self.api.document(board_id=self.board_id, document_id=document_id)
            if doc and doc.contents:
                return doc.contents
        except Exception as e:
            logging.error(f"문서 본문 조회 실패 ({document_id}): {e}")
        return None

    async def get_document_full(self, document_id, max_images=3):
        """
        데스크탑 페이지에서 본문 텍스트 + 이미지 URL 리스트 조회.
        dc_api로는 일부 글이 안 잡혀서 직접 파싱.

        :return: dict {contents: str, images: [url, ...]}
        """
        url = f"https://gall.dcinside.com/board/view/?id={self.board_id}&no={document_id}"
        try:
            async with aiohttp.ClientSession(headers=DESKTOP_HEADERS) as session:
                async with session.get(url) as res:
                    html = await res.text()
            parsed = lxml.html.fromstring(html)

            content_div = parsed.xpath("//div[contains(@class, 'write_div')]")
            if not content_div:
                return {"contents": "", "images": []}

            div = content_div[0]
            text = div.text_content().strip()
            # 광고 텍스트 제거
            text = text.replace("- dc official App", "").strip()

            images = div.xpath(".//img/@src")
            return {"contents": text, "images": images[:max_images]}
        except Exception as e:
            logging.error(f"문서 전체 조회 실패 ({document_id}): {e}")
            return {"contents": "", "images": []}

    async def fetch_image_as_data_url(self, image_url):
        """
        이미지를 받아서 data URL로 인코딩.
        멀티모달 모델에 직접 전달 가능.

        :return: "data:image/...;base64,..." 또는 None
        """
        try:
            headers = dict(DESKTOP_HEADERS)
            headers["Referer"] = "https://gall.dcinside.com"
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(image_url) as res:
                    if res.status != 200:
                        return None
                    content = await res.read()
                    # 디시는 Content-Type을 octet-stream으로 주는 경우가 있어서 시그니처로 추정
                    mime = self._guess_image_mime(content)
                    if not mime:
                        return None
                    b64 = base64.b64encode(content).decode("ascii")
                    return f"data:{mime};base64,{b64}"
        except Exception as e:
            logging.error(f"이미지 다운로드 실패 ({image_url[:80]}): {e}")
            return None

    @staticmethod
    def _guess_image_mime(content):
        """파일 시그니처로 이미지 MIME 타입 추정."""
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"GIF8"):
            return "image/gif"
        if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return "image/webp"
        return None

    async def get_document_with_comments(self, document_id, max_comments=20):
        """본문 + 기존 댓글 목록을 가져옵니다."""
        try:
            doc = await self.api.document(board_id=self.board_id, document_id=document_id)
            if not doc:
                return None, []

            comments = []
            try:
                async for c in doc.comments():
                    if c.contents:
                        comments.append({"author": c.author or "ㅇㅇ", "contents": c.contents})
                    if len(comments) >= max_comments:
                        break
            except Exception as e:
                logging.error(f"댓글 목록 조회 실패 ({document_id}): {e}")

            return doc.contents or "", comments
        except Exception as e:
            logging.error(f"문서 조회 실패 ({document_id}): {e}")
            return None, []

    async def get_gallery_info(self):
        """갤러리 이름/설명/키워드 메타데이터 조회"""
        url = f"https://gall.dcinside.com/board/lists/?id={self.board_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url) as res:
                    html = await res.text()
            parsed = lxml.html.fromstring(html)

            def get(xpath):
                r = parsed.xpath(xpath)
                return r[0].strip() if r else ""

            title = get("//meta[@property='og:title']/@content") or get("//title/text()")
            # "여장 갤러리 - 커뮤니티 포털 디시인사이드" → "여장 갤러리"
            if " - " in title:
                title = title.split(" - ")[0].strip()

            return {
                "id": self.board_id,
                "name": title,
                "description": get("//meta[@name='description']/@content"),
                "keywords": get("//meta[@name='keywords']/@content"),
            }
        except Exception as e:
            logging.error(f"갤러리 정보 조회 실패: {e}")
            return {"id": self.board_id, "name": "", "description": "", "keywords": ""}

    async def get_articles(self, num=20, recommend=False, with_contents=False, with_comments=False, with_images=False, max_comments=10, max_images=2):
        """
        글 목록을 가져옵니다.

        :param num: 가져올 글 수
        :param recommend: True면 개념글만
        :param with_contents: True면 본문까지 함께 조회 (느림)
        :param with_comments: True면 댓글 목록도 함께 조회
        :param with_images: True면 이미지 URL도 함께 조회 (data URL 변환은 별도)
        :param max_comments: 글당 최대 댓글 수
        :param max_images: 글당 최대 이미지 수
        :return: list of dict {id, title, author, contents?, comments?, image_urls?}
        """
        try:
            indexes = [a async for a in self.api.board(
                board_id=self.board_id, num=num, recommend=recommend
            )]
        except Exception as e:
            logging.error(f"글 목록 조회 실패: {e}")
            return []

        results = []
        for idx in indexes:
            item = {"id": idx.id, "title": idx.title, "author": idx.author}

            # 본문/이미지: 데스크탑 파싱 사용 (dc_api가 못 읽는 글도 잡힘)
            if with_contents or with_images:
                full = await self.get_document_full(idx.id, max_images=max_images)
                if with_contents:
                    item["contents"] = full.get("contents", "")
                if with_images:
                    item["image_urls"] = full.get("images", [])

            # 댓글: dc_api 사용
            if with_comments:
                comments = []
                try:
                    doc = await self.api.document(board_id=self.board_id, document_id=idx.id)
                    if doc:
                        async for c in doc.comments():
                            if c.contents:
                                comments.append({"author": c.author or "ㅇㅇ", "contents": c.contents})
                            if len(comments) >= max_comments:
                                break
                except Exception as e:
                    logging.error(f"댓글 목록 조회 실패 ({idx.id}): {e}")
                item["comments"] = comments

            results.append(item)
        return results

    async def get_random_document_info(self, exclude_ids=None, num=20):
        """
        무작위로 문서 정보를 가져옵니다. exclude_ids에 포함된 글은 제외.

        :param exclude_ids: 제외할 doc_id set (이미 댓글 단 글, 봇이 쓴 글 등)
        :param num: 후보군 크기 (크면 중복 회피 확률 높음)
        :return: (문서 ID, 문서 제목) 튜플 또는 None
        """
        exclude_ids = exclude_ids or set()
        try:
            articles = [article async for article in self.api.board(board_id=self.board_id, num=num)]
            # 제외 대상 걸러내기
            candidates = [a for a in articles if str(a.id) not in exclude_ids]
            if candidates:
                chosen = random.choice(candidates)
                return chosen.id, chosen.title
            if articles:
                logging.warning(f"[댓글 대상] 후보 {len(articles)}개가 모두 제외됨 (이미 처리한 글)")
            else:
                logging.warning("게시물이 없습니다.")
            return None
        except Exception as e:
            logging.error(f"문서 정보 가져오기 실패 : {e}")
            return None
