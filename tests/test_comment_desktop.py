"""
데스크탑 API 댓글 작성 테스트
IP 차단 해제 후 실행: python3 tests/test_comment_desktop.py
"""
import asyncio
import aiohttp
import lxml.html
import re
import time

BOARD_ID = "yjrs"
PASSWORD = "1111"

async def get_tokens(session, board_id, doc_id):
    """글 페이지에서 댓글 작성에 필요한 토큰을 파싱"""
    view_url = f"https://gall.dcinside.com/board/view/?id={board_id}&no={doc_id}"
    async with session.get(view_url) as res:
        html = await res.text()
        parsed = lxml.html.fromstring(html)

    token_map = {}
    for inp in parsed.xpath("//input[@type='hidden']"):
        name = inp.get("name", "") or inp.get("id", "")
        value = inp.get("value", "")
        if name and value and name not in token_map:
            token_map[name] = value

    return token_map, view_url

async def write_comment(session, board_id, doc_id, memo, name, password):
    """데스크탑 API로 댓글 작성"""
    token_map, view_url = await get_tokens(session, board_id, doc_id)

    payload = {
        "id": board_id,
        "no": doc_id,
        "reply_no": "undefined",
        "name": "",
        "password": password,
        "memo": memo,
        "cur_t": token_map.get("cur_t", str(int(time.time()))),
        "check_6": token_map.get("check_6", ""),
        "check_7": token_map.get("check_7", ""),
        "check_8": token_map.get("check_8", ""),
        "check_9": token_map.get("check_9", ""),
        "check_10": token_map.get("check_10", ""),
        "recommend": "0",
        "c_r_k_x_z": token_map.get("c_r_k_x_z", ""),
        "t_vch2": "",
        "t_vch2_chk": "",
        "c_gall_id": board_id,
        "c_gall_no": doc_id,
        "service_code": token_map.get("service_code", ""),
        "g-recaptcha-response": "",
        "_GALLTYPE_": token_map.get("_GALLTYPE_", "G"),
        "headTail": '""',
        "gall_nick_name": name,
        "use_gall_nick": "Y",
    }

    headers = {
        "Referer": view_url,
        "Origin": "https://gall.dcinside.com",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "text/html, */*; q=0.01",
    }

    url = "https://gall.dcinside.com/board/forms/comment_submit"
    async with session.post(url, data=payload, headers=headers) as res:
        raw = await res.text()
        return raw

async def main():
    jar = aiohttp.CookieJar()
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    session = aiohttp.ClientSession(headers=headers, cookie_jar=jar)

    try:
        # 쿠키 세팅
        await session.get("https://gall.dcinside.com")

        # 최신 글 가져오기
        list_url = f"https://gall.dcinside.com/board/lists/?id={BOARD_ID}"
        async with session.get(list_url) as res:
            html = await res.text()
        doc_id = re.findall(r'no=(\d{5,})', html)[0]
        print(f"갤러리: {BOARD_ID}, 대상 글: {doc_id}")

        # 댓글 작성
        result = await write_comment(session, BOARD_ID, doc_id, "테스트 댓글", "여갤러", PASSWORD)
        print(f"결과: {result[:300]}")

    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())
