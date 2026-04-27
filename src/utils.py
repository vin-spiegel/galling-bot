import logging
import os
import random
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


def load_successful_posts(directory):
    """
    docs/successful_posts/ 같은 폴더에서 .md 파일을 모두 읽어 (title, body) 튜플 리스트로 반환.

    파일 형식:
        # 제목
        본문...

    README.md는 자동 제외.
    """
    if not directory or not os.path.isdir(directory):
        return []

    posts = []
    for name in sorted(os.listdir(directory)):
        if not name.lower().endswith(".md"):
            continue
        if name.lower() == "readme.md":
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
        except OSError as e:
            logging.warning(f"성공 사례 로드 실패 ({path}): {e}")
            continue

        if not raw:
            continue

        title, body = "", raw
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                body = raw.split(line, 1)[1].strip()
                break

        if not title and not body:
            continue
        posts.append((title, body))

    return posts


def sample_successful_posts_section(posts, sample_size):
    """
    성공 사례 리스트에서 sample_size개 무작위 샘플링하여 시스템 프롬프트 섹션 문자열 반환.
    빈 리스트나 sample_size <= 0 이면 빈 문자열.
    """
    if not posts or sample_size <= 0:
        return ""

    sample = random.sample(posts, min(sample_size, len(posts)))
    blocks = []
    for title, body in sample:
        block = ""
        if title:
            block += f"## {title}\n"
        if body:
            block += body
        blocks.append(block.strip())
    return "\n\n---\n\n".join(blocks)
