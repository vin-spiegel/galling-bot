import logging
import asyncio
import time
from collections import Counter
from utils import handle_exceptions, sanitize_text, clean_title

class DcinsideBot:
    def __init__(self, api_manager, db_managers, gpt_api_manager, persona, settings, comment_manager=None):
        """
        DcinsideBot 클래스를 초기화합니다.

        :param api_manager: DCInside API 관리 객체
        :param db_managers: 데이터베이스 관리 객체들
        :param gpt_api_manager: GPT API 관리 객체
        :param persona: 봇의 페르소나
        :param settings: 봇 설정
        :param comment_manager: Playwright 기반 댓글 매니저 (있으면 우선 사용)
        """
        self.api_manager = api_manager
        self.comment_manager = comment_manager
        self.crawling_db = db_managers['crawling']
        self.data_db = db_managers['data']
        self.memory_db = db_managers['memory']
        self.gpt_api_manager = gpt_api_manager
        self.persona = persona
        self.settings = settings
        self.write_article_enabled = settings.get('write_article_enabled', True)
        self.write_comment_enabled = settings.get('write_comment_enabled', True)
        self.board_id = settings['board_id']
        self.username = settings['username']
        self.password = settings['password']

    @handle_exceptions
    async def get_trending_topics(self):
        """
        최신 트렌딩 토픽을 가져옵니다.

        :return: 최신 토픽의 카운터 객체
        """
        articles = [article async for article in self.api_manager.api.board(
            board_id=self.board_id,
            num=self.settings['crawl_article_count']
        )]
        title_list = [article.title for article in articles]
        return Counter(title_list)

    @handle_exceptions
    async def record_gallery_information(self):
        """
        갤러리 정보를 메모리에 기록합니다.
        """
        if not self.settings.get('record_memory_enabled', True):
            return

        articles = [article async for article in self.api_manager.api.board(
            board_id=self.board_id,
            num=self.settings['crawl_article_count']
        )]
        memory_content = await self.generate_memory_from_crawling(articles)
        await self.memory_db.save_data(
            board_id=self.board_id,
            memory_content=memory_content
        )
            
    async def generate_memory_from_crawling(self, articles):
        crawling_info = "\n".join([f"제목: {article.title}, 저자: {article.author}" for article in articles])
        prompt = f"""
        {self.persona}

        디시인사이드 갤러리에서 크롤링한 정보를 바탕으로, {self.persona} 페르소나에 맞춰서 메모리를 작성해줘.

        크롤링 정보:
        {crawling_info}
        """
        content = await self.gpt_api_manager.generate_content(prompt)
        
        if content is None:
            logging.error("GPT API returned None content")
            return ""

        return sanitize_text(content)

    async def write_article(self, trending_topics, memory_data=None, max_retries=3):
        if not self.write_article_enabled:
            return None

        top_trending_topics = [topic[0] for topic in trending_topics.most_common(3)]

        # 1단계: 제목 생성
        title_prompt = f"""
        {self.persona} 페르소나 규칙 꼭 지키기.

        {self.board_id} 갤러리에 어울리는 흥미로운 글 제목을 하나만 작성해줘.
        제목 텍스트만 출력해. 다른 설명이나 형식 없이 제목만 작성해.

        최근 {self.board_id} 갤러리에서 유행하는 토픽:
        {trending_topics}

        특히 다음 토픽들을 참고해줘:
        {', '.join(top_trending_topics)}
        """

        for attempt in range(max_retries):
            try:
                logging.info(f"[글 작성] 제목 생성 요청 (시도 {attempt + 1}/{max_retries})")
                title_raw = await self.gpt_api_manager.generate_content(title_prompt)

                if not title_raw:
                    raise ValueError("제목 생성 결과가 비어있습니다.")

                title = sanitize_text(title_raw).strip()
                logging.info(f"[글 작성] 제목 생성 완료: {title}")

                # 2단계: 내용 생성
                content_prompt = f"""
                {self.persona} 페르소나 규칙 꼭 지키기.

                다음 제목으로 {self.board_id} 갤러리에 올릴 글 내용을 작성해줘.
                글 내용 텍스트만 출력해. 다른 설명이나 형식 없이 본문만 작성해.

                제목: {title}

                갤러리의 최근 정보를 참고해줘:
                {memory_data}
                """

                logging.info(f"[글 작성] 내용 생성 요청 (시도 {attempt + 1}/{max_retries})")
                content_raw = await self.gpt_api_manager.generate_content(content_prompt)

                if not content_raw:
                    raise ValueError("내용 생성 결과가 비어있습니다.")

                content = sanitize_text(content_raw).strip()
                logging.info(f"[글 작성] 내용 생성 완료 ({len(content)}자)")

                # 3단계: DC에 글 작성
                logging.info(f"[글 작성] DC 업로드 중... 제목: {title}")
                doc_id = await self.api_manager.write_document(
                    title=title,
                    content=content
                )

                await self.data_db.save_data(
                    content_type="article",
                    doc_id=doc_id,
                    content=title,
                    board_id=self.board_id
                )

                logging.info(f"[글 작성] 성공 https://gall.dcinside.com/board/view/?id={self.board_id}&no={doc_id}")
                return doc_id, title
            except Exception as e:
                logging.error(f"[글 작성] 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(self.settings['article_interval'])
        return None

    async def write_comment(self, document_id, article_title, max_retries=3):
        if not self.write_comment_enabled:
            return None

        prompt = f"""
        {self.persona}

        다음 글에 대한 댓글을 페르소나에 충실하게 작성해줘.
        댓글 텍스트만 출력해. 다른 설명이나 형식 없이 댓글 내용만 작성해.

        글 제목: {article_title}
        """
        for attempt in range(max_retries):
            try:
                logging.info(f"[댓글] 생성 요청 (시도 {attempt + 1}/{max_retries}) - 대상 글: {article_title}")
                content = await self.gpt_api_manager.generate_content(prompt)

                if not content:
                    raise ValueError("생성된 콘텐츠가 비어있습니다.")

                comment_content = sanitize_text(content).strip()

                if not comment_content:
                    raise ValueError("댓글 내용이 비어있습니다.")

                logging.info(f"[댓글] 생성 완료 ({len(comment_content)}자): {comment_content[:50]}...")
                logging.info(f"[댓글] DC 업로드 중... (doc_id: {document_id})")

                # Playwright 매니저가 있으면 사용, 없으면 dc_api로 폴백
                if self.comment_manager:
                    comm_id = await self.comment_manager.write_comment(
                        document_id=document_id,
                        content=comment_content
                    )
                else:
                    comm_id = await self.api_manager.write_comment(
                        document_id=document_id,
                        content=comment_content
                    )

                if comm_id is None:
                    raise ValueError("DC 댓글 업로드 실패 (comm_id: None)")

                first_sentence = comment_content.split('\n')[0]

                await self.data_db.save_data(
                    content_type="comment",
                    doc_id=document_id,
                    content=first_sentence,
                    board_id=self.board_id
                )

                logging.info(f"[댓글] 성공 https://gall.dcinside.com/board/view/?id={self.board_id}&no={document_id}")
                return True
            except Exception as e:
                logging.error(f"[댓글] 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
        return False