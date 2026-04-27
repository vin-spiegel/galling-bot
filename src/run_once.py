"""
1회 실행 스크립트 — 글 1개 + 댓글 N개 작성 후 종료.
cron/scheduler에서 호출하는 용도.
"""
import asyncio
import logging
from config import API_KEYS, API_BASE_URL, DEFAULT_BOT_SETTINGS
from database_manager import DatabaseManager
from bot import DcinsideBot
from gpt_api_manager import GptApiManager
from dc_api_manager import DcApiManager
from playwright_comment_manager import PlaywrightCommentManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def run_once():
    api_key = API_KEYS[0]
    settings = DEFAULT_BOT_SETTINGS.copy()

    dc_api_manager = DcApiManager(
        board_id=settings['board_id'],
        username=settings['username'],
        password=settings['password'],
        is_minor=settings.get('is_minor', False),
    )

    playwright_manager = PlaywrightCommentManager(
        board_id=settings['board_id'],
        username=settings['username'],
        password=settings['password'],
        headless=False,
        is_minor=settings.get('is_minor', False),
    )

    db_managers = {
        'crawling': DatabaseManager(f"data/{settings['board_id']}_crawling.db", "crawling"),
        'data': DatabaseManager(f"data/{settings['board_id']}_data.db", "data"),
        'memory': DatabaseManager(f"data/{settings['board_id']}_memory.db", "memory"),
    }

    try:
        await asyncio.gather(*[db.connect() for db in db_managers.values()])

        gpt_api_manager = GptApiManager(api_key=api_key, base_url=API_BASE_URL)
        await playwright_manager.start()

        bot = DcinsideBot(
            api_manager=dc_api_manager,
            db_managers=db_managers,
            gpt_api_manager=gpt_api_manager,
            persona=settings['persona'],
            settings=settings,
            comment_manager=playwright_manager,
        )

        await bot.load_gallery_info()

        # 트렌딩 + 메모리
        trending_topics = await bot.get_trending_topics()
        memory_data = ""
        if settings.get('load_memory_enabled', True):
            memory_data = await bot.memory_db.load_memory(settings['board_id'])

        # 글 1개 작성
        if settings.get('write_article_enabled', True):
            result = await bot.write_article(trending_topics, memory_data)
            if result:
                logging.info(f"[run_once] 글 작성 완료: {result[1]}")
            else:
                logging.warning("[run_once] 글 작성 실패")

        # 댓글 N개 작성
        if settings.get('write_comment_enabled', True):
            comment_count = settings.get('comment_target_count', 5)
            commented = await db_managers['data'].get_commented_doc_ids(settings['board_id'])
            written = await db_managers['data'].get_written_doc_ids(settings['board_id'])
            exclude_ids = commented | written

            for i in range(comment_count):
                doc_info = await dc_api_manager.get_random_document_info(exclude_ids=exclude_ids)
                if doc_info:
                    doc_id, title = doc_info
                    await bot.write_comment(doc_id, title)
                    exclude_ids.add(str(doc_id))
                    await asyncio.sleep(settings.get('comment_interval', 45))
                else:
                    logging.warning("[run_once] 댓글 달 새 글 없음, 중단")
                    break

        logging.info("[run_once] 완료")

    except Exception as e:
        logging.error(f"[run_once] 오류: {e}")

    finally:
        await asyncio.gather(*[db.close() for db in db_managers.values()])
        await dc_api_manager.close()
        await playwright_manager.close()


if __name__ == "__main__":
    asyncio.run(run_once())
