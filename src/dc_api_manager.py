import logging
import random
import aiohttp
import lxml.html
import dc_api

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

    async def get_articles(self, num=20, recommend=False, with_contents=False):
        """
        글 목록을 가져옵니다.

        :param num: 가져올 글 수
        :param recommend: True면 개념글만
        :param with_contents: True면 본문까지 함께 조회 (느림)
        :return: list of dict {id, title, author, contents?}
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
            if with_contents:
                try:
                    doc = await self.api.document(board_id=self.board_id, document_id=idx.id)
                    item["contents"] = doc.contents if doc and doc.contents else ""
                except Exception as e:
                    logging.error(f"본문 조회 실패 ({idx.id}): {e}")
                    item["contents"] = ""
            results.append(item)
        return results

    async def get_random_document_info(self):
        """
        무작위로 문서 정보를 가져옵니다.

        :return: (문서 ID, 문서 제목) 튜플 또는 None
        """
        try:
            articles = [article async for article in self.api.board(board_id=self.board_id, num=10)]
            if articles:
                random_article = random.choice(articles)
                return random_article.id, random_article.title
            else:
                logging.warning("게시물이 없습니다.")
                return None
        except Exception as e:
            logging.error(f"문서 정보 가져오기 실패 : {e}")
            return None
