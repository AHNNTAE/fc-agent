"""
FC 온라인 공식경기 대량 수집 (눈덩이 방식)
- 시작 유저 → 최근 경기 → 상대 유저 → 그 유저의 최근 경기 → ...
- 결과는 data/fc_dataset.db (SQLite)에 저장. 중간에 멈춰도 다시 실행하면 이어서 수집
- 경기 원본(JSON)은 압축해서 저장 → 전처리 단계에서 필요한 항목을 꺼내 씀
"""
import os
import time
import json
import zlib
import sqlite3
from datetime import datetime

import requests
from dotenv import load_dotenv

# ---------------- 설정 ----------------
SEED_NICKNAMES = ["우태안"]   # 시작 유저. 다른 등급 닉네임을 추가하면 등급 분포가 넓어짐
TARGET_MATCHES = 14000        # 목표 경기 수 (경기 1개 = 유저 기록 2건 → 약 28,000건)
MATCHES_PER_USER = 20         # 유저 1명당 가져올 최근 공식경기 수
MAX_PER_SEC = 4.5             # 초당 최대 호출 수 (한도 초과 방지)
MATCHTYPE = 50                # 공식경기
DB_PATH = os.path.join("data", "fc_dataset.db")
# --------------------------------------

load_dotenv()
BASE = "https://open.api.nexon.com/fconline/v1"
HEADERS = {"x-nxopen-api-key": os.getenv("NEXON_API_KEY")}

_last_call = 0.0
stats = {"calls": 0, "429": 0, "errors": 0}


class DailyLimit(Exception):
    pass


def call(path, params):
    """초당 호출 수를 지키며 API 호출. 429가 계속되면 일일 한도로 보고 멈춤"""
    global _last_call
    for attempt in range(6):
        wait = (1.0 / MAX_PER_SEC) - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        stats["calls"] += 1
        try:
            r = requests.get(f"{BASE}{path}", headers=HEADERS, params=params, timeout=15)
        except requests.RequestException:
            stats["errors"] += 1
            time.sleep(2)
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429:
            stats["429"] += 1
            time.sleep(2 * (attempt + 1))
            continue
        stats["errors"] += 1
        return None
    raise DailyLimit(f"{path} 호출이 계속 실패했습니다 (429 누적 {stats['429']}회)")


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS matches (
        match_id TEXT PRIMARY KEY, match_date TEXT, collected_at TEXT, raw BLOB)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        ouid TEXT PRIMARY KEY, division INTEGER, achievement_date TEXT,
        processed INTEGER DEFAULT 0, added_at TEXT)""")
    conn.commit()


def add_user(conn, ouid):
    conn.execute("INSERT OR IGNORE INTO users (ouid, added_at) VALUES (?, ?)",
                 (ouid, datetime.now().isoformat(timespec="seconds")))


def fetch_division(ouid):
    data = call("/user/maxdivision", {"ouid": ouid}) or []
    for d in data:
        if d.get("matchType") == MATCHTYPE:
            return d.get("division"), d.get("achievementDate")
    return None, None


def main():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    for nick in SEED_NICKNAMES:
        data = call("/id", {"nickname": nick})
        if data and data.get("ouid"):
            add_user(conn, data["ouid"])
            print(f"시작 유저 추가: {nick}")
        else:
            print(f"시작 유저를 찾지 못함: {nick}")
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    print(f"이미 저장된 경기: {count}개 / 목표 {TARGET_MATCHES}개\n")
    start, start_count = time.time(), count

    try:
        while count < TARGET_MATCHES:
            row = conn.execute("SELECT ouid FROM users WHERE processed = 0 "
                               "ORDER BY rowid LIMIT 1").fetchone()
            if not row:
                print("더 따라갈 유저가 없습니다. 시작 유저를 추가해 주세요.")
                break
            ouid = row[0]

            div, ach = fetch_division(ouid)
            mids = call("/user/match", {"ouid": ouid, "matchtype": MATCHTYPE,
                                        "offset": 0, "limit": MATCHES_PER_USER}) or []
            for mid in mids:
                if count >= TARGET_MATCHES:
                    break
                if conn.execute("SELECT 1 FROM matches WHERE match_id = ?", (mid,)).fetchone():
                    continue
                d = call("/match-detail", {"matchid": mid})
                if not d:
                    continue
                raw = zlib.compress(json.dumps(d, ensure_ascii=False).encode("utf-8"))
                conn.execute("INSERT OR IGNORE INTO matches VALUES (?, ?, ?, ?)",
                             (mid, d.get("matchDate"), datetime.now().isoformat(timespec="seconds"), raw))
                for p in d.get("matchInfo", []):
                    if p.get("ouid"):
                        add_user(conn, p["ouid"])
                count += 1

                if count % 100 == 0:
                    conn.commit()
                    done = count - start_count
                    rate = done / max(time.time() - start, 1)
                    eta = (TARGET_MATCHES - count) / rate / 60 if rate else 0
                    print(f"[{datetime.now():%H:%M:%S}] 경기 {count:,}/{TARGET_MATCHES:,} "
                          f"| 호출 {stats['calls']:,} | 429 {stats['429']} "
                          f"| 남은 시간 약 {eta:.0f}분")

            conn.execute("UPDATE users SET processed = 1, division = ?, achievement_date = ? "
                         "WHERE ouid = ?", (div, ach, ouid))
            conn.commit()

    except DailyLimit as e:
        print(f"\n수집 중단: {e}")
        print("호출 한도에 걸린 것 같습니다. 나중에 다시 실행하면 이어서 수집합니다.")
    except KeyboardInterrupt:
        print("\n사용자가 중단했습니다. 다시 실행하면 이어서 수집합니다.")
    finally:
        conn.commit()
        users = conn.execute("SELECT COUNT(*), SUM(processed) FROM users").fetchone()
        print(f"\n저장된 경기: {count:,}개 (유저 기록 약 {count * 2:,}건)")
        print(f"발견한 유저: {users[0]:,}명 / 등급 확인: {users[1] or 0:,}명")
        print(f"총 호출: {stats['calls']:,}회 / 429: {stats['429']}회 / 기타 오류: {stats['errors']}회")
        conn.close()


if __name__ == "__main__":
    main()