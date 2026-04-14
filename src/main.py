import asyncio
import logging
import time
from config import API_KEYS, API_BASE_URL, MODEL_NAME, GENERATION_CONFIG, DEFAULT_BOT_SETTINGS
from database_manager import DatabaseManager
from bot import DcinsideBot
from gpt_api_manager import GptApiManager
from dc_api_manager import DcApiManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def run_gallery_bot(api_key, bot_settings):
    """
    갤러리 봇을 실행합니다.

    :param api_key: API 키
    :param bot_settings: 봇 설정
    """
    bot_settings.update({'api_key': api_key})

    # DcApiManager 객체 생성
    dc_api_manager = DcApiManager(
        board_id=bot_settings['board_id'],
        username=bot_settings['username'],
        password=bot_settings['password']
    )

    # DatabaseManager 객체 생성
    db_managers = {
        'crawling': DatabaseManager(f"data/{bot_settings['board_id']}_crawling.db", "crawling"),
        'data': DatabaseManager(f"data/{bot_settings['board_id']}_data.db", "data"),
        'memory': DatabaseManager(f"data/{bot_settings['board_id']}_memory.db", "memory"),
    }

    try:
        # 데이터베이스 연결
        await asyncio.gather(*[db_manager.connect() for db_manager in db_managers.values()])

        # GptApiManager 객체 생성 (ChatGPT 사용)
        gpt_api_manager = GptApiManager(api_key=api_key, base_url=API_BASE_URL)

        # DcinsideBot 객체 생성
        bot = DcinsideBot(
            api_manager=dc_api_manager,
            db_managers=db_managers,
            gpt_api_manager=gpt_api_manager,
            persona=bot_settings['persona'],
            settings=bot_settings
        )

        await bot.get_trending_topics()
        await bot.record_gallery_information()

        start_time = time.time()

        async def article_task():
            while True:
                trending_topics = await bot.get_trending_topics()
                memory_data = await bot.memory_db.load_memory(bot.settings['board_id']) if bot.settings.get('load_memory_enabled', True) else ""
                await bot.write_article(trending_topics, memory_data)
                await asyncio.sleep(bot.settings['article_interval'])

        async def comment_task():
            while True:
                doc_info = await dc_api_manager.get_random_document_info()
                if doc_info:
                    doc_id, document_title = doc_info
                    await bot.write_comment(doc_id, document_title)
                else:
                    logging.error("문서 ID나 제목을 가져오지 못했습니다.")
                await asyncio.sleep(bot.settings['comment_interval'])

        await asyncio.gather(article_task(), comment_task())

        if bot.settings.get('use_time_limit', False) and (time.time() - start_time) > bot.settings['max_run_time']:
            return

    except Exception as e:
        logging.error(f"봇 실행 중 오류 발생: {e}")

    finally:
        await asyncio.gather(*[db_manager.close() for db_manager in db_managers.values()])
        await dc_api_manager.close()  # 세션 명시적으로 종료

async def main():
    current_api_key_index = 0
    bot_settings = DEFAULT_BOT_SETTINGS.copy()

    while True:
        current_api_key = API_KEYS[current_api_key_index]
        await run_gallery_bot(current_api_key, bot_settings)
        await asyncio.sleep(900)  # 15분 대기
        current_api_key_index = (current_api_key_index + 1) % len(API_KEYS)

if __name__ == "__main__":
    asyncio.run(main())