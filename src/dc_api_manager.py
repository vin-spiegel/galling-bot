import logging
import random
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
