import logging
import asyncio
import time
import uuid
from collections import Counter
from utils import handle_exceptions, sanitize_text, clean_title
from dc_style_guide import get_style_section


def _new_task_id():
    """짧은 추적용 작업 ID (8자)"""
    return uuid.uuid4().hex[:8]

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
        self.gallery_info = None  # lazy load

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

    async def load_gallery_info(self):
        """갤러리 메타데이터(이름/설명/키워드)를 로드합니다. 봇 시작 시 1회 호출."""
        self.gallery_info = await self.api_manager.get_gallery_info()
        logging.info(f"[갤러리] {self.gallery_info.get('name', self.board_id)} 정보 로드 완료")

    @handle_exceptions
    async def record_gallery_information(self):
        """
        갤러리 정보를 메모리에 기록합니다 (개념글 + 본문 기반).
        """
        if not self.settings.get('record_memory_enabled', True):
            return

        articles = await self.api_manager.get_articles(
            num=self.settings['crawl_article_count'],
            recommend=True,
            with_contents=True,
            with_comments=True,
            max_comments=10,
        )
        if not articles:
            logging.warning("[메모리] 개념글 크롤링 결과가 비어있어 메모리 기록을 건너뜁니다.")
            return

        memory_content = await self.generate_memory_from_crawling(articles)
        await self.memory_db.save_data(
            board_id=self.board_id,
            memory_content=memory_content
        )
            
    def _build_gallery_section(self):
        """갤러리 섹션 마크다운 생성"""
        info = self.gallery_info or {"id": self.board_id, "name": "", "description": "", "keywords": ""}
        lines = [f"- ID: {info['id']}"]
        if info.get("name"):
            lines.append(f"- 이름: {info['name']}")
        if info.get("description"):
            lines.append(f"- 설명: {info['description']}")
        if info.get("keywords"):
            lines.append(f"- 키워드: {info['keywords']}")
        return "\n".join(lines)

    def _build_system_prompt(self, trending_topics=None, memory_data=None, recent_my_articles=None):
        """system 메시지 구성: 페르소나 + 갤러리 컨텍스트 + 말투 가이드"""
        parts = [
            f"# 페르소나\n{self.persona}",
            f"\n# 갤러리\n{self._build_gallery_section()}",
            f"\n{get_style_section()}",
        ]

        if trending_topics:
            top_titles = "\n".join(
                f"- {title} (×{count})" for title, count in trending_topics.most_common(10)
            )
            parts.append(f"\n# 최근 트렌딩 토픽\n{top_titles}")

        if memory_data:
            parts.append(f"\n# 갤러리 메모리\n{memory_data}")

        if recent_my_articles:
            recent_lines = "\n".join(f"- {t}" for t in recent_my_articles)
            parts.append(
                f"\n# 내가 최근에 쓴 글 (절대 비슷한 주제/표현 반복 금지)\n{recent_lines}"
            )

        return "\n".join(parts)

    async def generate_memory_from_crawling(self, articles):
        # articles: list of dict {id, title, author, contents, comments?}
        blocks = []
        for a in articles:
            block = f"## {a.get('title', '')} (by {a.get('author', '')})"
            body = (a.get('contents') or '').strip()
            if body:
                if len(body) > 500:
                    body = body[:500] + "..."
                block += f"\n{body}"
            comments = a.get('comments') or []
            if comments:
                comment_lines = "\n".join(
                    f"  - {c['author']}: {c['contents']}" for c in comments
                )
                block += f"\n[댓글]\n{comment_lines}"
            blocks.append(block)
        crawling_info = "\n\n".join(blocks)

        system = (
            f"# 페르소나\n{self.persona}\n\n"
            f"# 갤러리\n{self._build_gallery_section()}\n\n"
            f"{get_style_section()}"
        )
        prompt = f"""아래는 갤러리의 최근 개념글(추천 많이 받은 글)과 거기 달린 댓글이야.
이 정보를 바탕으로 다음을 한 단락으로 요약해줘:
- 갤러리 관심사/주요 토픽
- 갤러리 특유의 말투/추임새/유행어
- 댓글들이 보여주는 상호작용 방식 (빈정거림, 동조, 어그로 등)

이 요약은 네가 나중에 글/댓글 쓸 때 참고할 메모야.

# 개념글 + 댓글
{crawling_info}"""
        content = await self.gpt_api_manager.generate_content(prompt, system=system)

        if content is None:
            logging.error("GPT API returned None content")
            return ""

        return sanitize_text(content)

    async def write_article(self, trending_topics, memory_data=None, max_retries=3):
        if not self.write_article_enabled:
            return None

        tid = _new_task_id()
        tag = f"[글:{tid}]"
        logging.info(f"{tag} 작업 시작")

        # 내가 최근에 쓴 글 목록 (중복 회피)
        recent_my_articles = await self.data_db.load_recent_contents(
            board_id=self.board_id, content_type="article", limit=10
        )

        system = self._build_system_prompt(
            trending_topics=trending_topics,
            memory_data=memory_data,
            recent_my_articles=recent_my_articles,
        )

        # 1단계: 제목 생성
        title_prompt = "갤러리 분위기/트렌딩 토픽에 어울리는 흥미로운 글 제목을 하나만 작성해줘.\n제목 텍스트만 출력해. 다른 설명/접두어/따옴표 없이 제목만."

        for attempt in range(max_retries):
            try:
                logging.info(f"{tag} 제목 생성 요청 (시도 {attempt + 1}/{max_retries})")
                title_raw = await self.gpt_api_manager.generate_content(title_prompt, system=system)

                if not title_raw:
                    raise ValueError("제목 생성 결과가 비어있습니다.")

                title = sanitize_text(title_raw).strip()
                logging.info(f"{tag} 제목 생성 완료: {title}")

                # 2단계: 내용 생성
                content_prompt = f"""아래 제목으로 글 본문을 작성해줘.
본문 텍스트만 출력해. 다른 설명/접두어 없이 본문만.

# 제목
{title}"""

                logging.info(f"{tag} 내용 생성 요청")
                content_raw = await self.gpt_api_manager.generate_content(content_prompt, system=system)

                if not content_raw:
                    raise ValueError("내용 생성 결과가 비어있습니다.")

                content = sanitize_text(content_raw).strip()
                logging.info(f"{tag} 내용 생성 완료 ({len(content)}자)")

                # 3단계: DC에 글 작성
                logging.info(f"{tag} DC 업로드 중... 제목: {title}")
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

                logging.info(f"{tag} 성공 https://gall.dcinside.com/board/view/?id={self.board_id}&no={doc_id}")
                return doc_id, title
            except Exception as e:
                logging.error(f"{tag} 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(self.settings['article_interval'])
        return None

    async def write_comment(self, document_id, article_title, max_retries=3):
        if not self.write_comment_enabled:
            return None

        tid = _new_task_id()
        tag = f"[댓글:{tid}]"
        logging.info(f"{tag} 작업 시작 - doc_id={document_id} 제목={article_title}")

        memory_data = await self.memory_db.load_memory(self.board_id) if self.settings.get('load_memory_enabled', True) else ""
        system = self._build_system_prompt(memory_data=memory_data)

        # 본문 + 기존 댓글 조회 (실패해도 제목만으로 진행)
        article_body, existing_comments = await self.api_manager.get_document_with_comments(document_id)

        prompt_parts = [
            "아래 글에 댓글을 달아줘.",
            "댓글 텍스트만 출력해. 다른 설명/접두어 없이 댓글만.",
            "",
            f"# 글 제목\n{article_title}",
        ]
        if article_body:
            prompt_parts.append(f"\n# 글 본문\n{article_body}")
        if existing_comments:
            comment_lines = "\n".join(
                f"- {c['author']}: {c['contents']}" for c in existing_comments
            )
            prompt_parts.append(f"\n# 기존 댓글 (분위기 참고용, 중복 X)\n{comment_lines}")
        prompt = "\n".join(prompt_parts)
        for attempt in range(max_retries):
            try:
                logging.info(f"{tag} 생성 요청 (시도 {attempt + 1}/{max_retries})")
                content = await self.gpt_api_manager.generate_content(prompt, system=system)

                if not content:
                    raise ValueError("생성된 콘텐츠가 비어있습니다.")

                comment_content = sanitize_text(content).strip()

                if not comment_content:
                    raise ValueError("댓글 내용이 비어있습니다.")

                logging.info(f"{tag} 생성 완료 ({len(comment_content)}자): {comment_content[:50]}...")
                logging.info(f"{tag} DC 업로드 중...")

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

                logging.info(f"{tag} 성공 https://gall.dcinside.com/board/view/?id={self.board_id}&no={document_id}")
                return True
            except Exception as e:
                logging.error(f"{tag} 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
        return False