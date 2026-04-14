import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수에서 API 키를 불러오고, 쉼표로 구분된 값을 리스트로 변환
API_KEYS = os.getenv('API_KEYS').split(',') if os.getenv('API_KEYS') else None

# API Base URL (OpenRouter 등 다른 프로바이더 사용 시 설정)
API_BASE_URL = os.getenv('API_BASE_URL') or None

# 모델 설정
MODEL_NAME = os.getenv('MODEL_NAME', 'gpt-4')  # 기본값을 'gpt-4'로 설정
GEN_TEMPERATURE = float(os.getenv('GEN_TEMPERATURE', '0.7'))
GEN_MAX_OUTPUT_TOKENS = int(os.getenv('GEN_MAX_OUTPUT_TOKENS', '300'))

# Generation Config
GENERATION_CONFIG = {
    "temperature": GEN_TEMPERATURE,
    "max_tokens": GEN_MAX_OUTPUT_TOKENS,
    # 'top_p'와 'frequency_penalty' 등 다른 설정을 추가로 정의할 수 있음
}

# 기본 봇 설정 (공통 설정)
DEFAULT_BOT_SETTINGS = {
    'max_run_time': int(os.getenv('BOT_MAX_RUN_TIME', '1800')),
    'article_interval': int(os.getenv('BOT_ARTICLE_INTERVAL', '90')),
    'comment_interval': int(os.getenv('BOT_COMMENT_INTERVAL', '45')),
    'crawl_article_count': int(os.getenv('BOT_CRAWL_ARTICLE_COUNT', '20')),
    'comment_target_count': int(os.getenv('BOT_COMMENT_TARGET_COUNT', '20')),
    'write_article_enabled': os.getenv('BOT_WRITE_ARTICLE_ENABLED', 'True') == 'True',
    'write_comment_enabled': os.getenv('BOT_WRITE_COMMENT_ENABLED', 'True') == 'True',
    'record_memory_enabled': os.getenv('BOT_RECORD_MEMORY_ENABLED', 'True') == 'True',
    'record_data_enabled': os.getenv('BOT_RECORD_DATA_ENABLED', 'True') == 'True',
    'use_time_limit': os.getenv('BOT_USE_TIME_LIMIT', 'False') == 'True',
    'load_memory_enabled': os.getenv('BOT_LOAD_MEMORY_ENABLED', 'True') == 'True',
    'load_data_enabled': os.getenv('BOT_LOAD_DATA_ENABLED', 'True') == 'True',
    'gallery_record_interval': int(os.getenv('BOT_GALLERY_RECORD_INTERVAL', '600')),
    'username': os.getenv('BOT_USERNAME'),
    'password': os.getenv('BOT_PASSWORD'),
    'persona': os.getenv('BOT_PERSONA')
}
