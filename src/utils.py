import logging
import re

def handle_exceptions(func):
    """
    비동기 함수에서 발생하는 예외를 처리합니다.
    
    :param func: 예외를 처리할 비동기 함수.
    :return: 예외를 처리한 비동기 래퍼 함수.
    """
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logging.error(f"{func.__name__} 함수에서 오류 발생: {e}", exc_info=True)
    return wrapper

def sanitize_text(text):
    """
    텍스트를 정리합니다. 줄바꿈은 보존하고 연속된 공백/탭만 정리합니다.

    :param text: 원본 텍스트.
    :return: 정리된 텍스트.
    """
    if not text:
        return ""

    # 연속된 공백/탭은 단일 공백으로 (줄바꿈은 건드리지 않음)
    text = re.sub(r'[ \t]+', ' ', text)

    # 3개 이상 연속된 줄바꿈은 2개로 압축 (문단 구분만 유지)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 각 줄 끝의 공백 제거
    text = '\n'.join(line.rstrip() for line in text.split('\n'))

    return text.strip()

def clean_title(title):
    """
    제목에서 '제목'이라는 단어를 제거합니다.
    
    :param title: 원본 제목.
    :return: '제목'이라는 단어가 제거된 제목.
    """
    # "제목 "으로 시작하면 이를 제거
    if title.startswith("제목 "):
        title = title[len("제목 "):]
    
    return title
