from nexon import get_ouid, get_match_ids, get_match_detail
from db import init_db, match_exists, save_match


def collect_matches(ouid, limit=50):
    """ouid의 최근 공식경기를 불러와 DB에 저장 (이미 있는 경기는 건너뜀)"""
    init_db()
    saved, skipped = 0, 0
    for mid in get_match_ids(ouid, limit=limit):
        if match_exists(mid, ouid):
            skipped += 1
            continue
        if save_match(get_match_detail(mid), ouid):
            saved += 1
    return {"saved": saved, "skipped": skipped}


if __name__ == "__main__":
    nickname = input("닉네임 입력: ")
    result = collect_matches(get_ouid(nickname))
    print(f"새로 저장: {result['saved']}경기 / 이미 있음: {result['skipped']}경기")