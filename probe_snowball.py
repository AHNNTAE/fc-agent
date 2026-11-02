"""
상대 유저를 따라가며 넓혀 가는 방식(눈덩이 수집)의 가능성 측정
- 시작 유저 → 최근 경기 → 상대 유저 → 그 유저의 최근 경기 → ...
- API 호출 MAX_CALLS번까지만 하고 멈춤
- 결과는 화면 출력 + probe_snowball_result.json 저장
"""
import os
import time
import json
from collections import Counter, deque
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()
BASE = "https://open.api.nexon.com/fconline/v1"
META = "https://open.api.nexon.com/static/fconline/meta"
HEADERS = {"x-nxopen-api-key": os.getenv("NEXON_API_KEY")}

MATCHTYPE = 50                 # 공식경기
SEED_NICKNAMES = ["우태안"]     # 시작 유저 (상위 랭커 닉네임을 추가해서 테스트 가능)
MAX_CALLS = 200                # 이번 측정에서 쓸 최대 호출 수
MATCHES_PER_USER = 10          # 유저 1명당 가져올 최근 경기 수

calls = 0
errors = Counter()


class BudgetDone(Exception):
    pass


def call(path, params, retry=True):
    global calls
    if calls >= MAX_CALLS:
        raise BudgetDone
    calls += 1
    r = requests.get(f"{BASE}{path}", headers=HEADERS, params=params, timeout=15)
    if r.status_code == 429 and retry:
        errors[429] += 1
        time.sleep(1)
        return call(path, params, retry=False)
    if r.status_code != 200:
        errors[r.status_code] += 1
        return None
    return r.json()


def title(text):
    print("\n" + "=" * 60 + f"\n{text}\n" + "=" * 60)


def parse_date(s):
    return datetime.fromisoformat(str(s)[:19]) if s else None


div_meta = requests.get(f"{META}/division.json", headers=HEADERS, timeout=15).json()
DIV_NAME = {d["divisionId"]: d["divisionName"] for d in div_meta}
# divisionId가 작을수록 높은 등급
DIV_ORDER = {d["divisionId"]: i for i, d in enumerate(sorted(div_meta, key=lambda x: x["divisionId"]))}


def division(ouid):
    data = call("/user/maxdivision", {"ouid": ouid})
    for d in data or []:
        if d.get("matchType") == MATCHTYPE:
            return d.get("division")
    return None


result = {}
try:
    # -----------------------------------------------------------
    title("1. 시작 유저 확인")
    seeds = []
    for nick in SEED_NICKNAMES:
        data = call("/id", {"nickname": nick})
        if data and data.get("ouid"):
            div = division(data["ouid"])
            seeds.append(data["ouid"])
            print(f"  {nick}: 최고 등급 {DIV_NAME.get(div, '알 수 없음')}")
        else:
            print(f"  {nick}: 찾지 못함")
    if not seeds:
        raise SystemExit("시작 유저를 찾지 못했습니다.")

    # -----------------------------------------------------------
    title("2. 한 유저의 경기 기록은 얼마나 과거까지 조회되는가")
    seed = seeds[0]
    depth = []
    for off in [0, 99, 199, 499, 999]:
        ids = call("/user/match", {"ouid": seed, "matchtype": MATCHTYPE, "offset": off, "limit": 1})
        if not ids:
            print(f"  {off + 1}번째 경기: 없음")
            break
        d = call("/match-detail", {"matchid": ids[0]})
        dt = parse_date(d.get("matchDate")) if d else None
        depth.append((off + 1, str(dt)))
        print(f"  {off + 1}번째 경기: {dt}")
    result["seed_history_depth"] = depth

    # -----------------------------------------------------------
    title(f"3. 눈덩이 수집 테스트 (호출 {MAX_CALLS}회 한도)")
    print("1~3분 정도 걸립니다...")
    queue = deque(seeds)
    seen_users = set(seeds)
    seen_matches = set()
    user_div = {}
    records = 0
    duplicate = 0
    start = time.perf_counter()
    start_calls = calls

    while queue:
        ouid = queue.popleft()
        if ouid not in user_div:
            user_div[ouid] = division(ouid)
        mids = call("/user/match", {"ouid": ouid, "matchtype": MATCHTYPE,
                                    "offset": 0, "limit": MATCHES_PER_USER}) or []
        for mid in mids:
            if mid in seen_matches:
                duplicate += 1
                continue
            seen_matches.add(mid)
            d = call("/match-detail", {"matchid": mid})
            if not d:
                continue
            for p in d.get("matchInfo", []):
                o = p.get("ouid")
                if not o:
                    continue
                records += 1
                if o not in seen_users:
                    seen_users.add(o)
                    queue.append(o)

except BudgetDone:
    pass

elapsed = time.perf_counter() - start
used = calls - start_calls

# ---------------------------------------------------------------
title("결과")
per_min = used / elapsed * 60 if elapsed else 0
matches = len(seen_matches)
print(f"측정 구간 호출: {used}회 / {elapsed:.1f}초 → 분당 약 {per_min:.0f}회")
print(f"수집한 경기: {matches}개 (이미 수집한 경기와 겹친 횟수 {duplicate}회)")
print(f"수집한 유저 기록(경기×2명): {records}건")
print(f"발견한 유저: {len(seen_users)}명 / 등급 확인한 유저: {len(user_div)}명")

if matches:
    calls_per_match = used / matches
    per_hour = per_min * 60 / calls_per_match
    print(f"경기 1개당 평균 호출: {calls_per_match:.1f}회")
    print(f"→ 1시간 수집 시 약 {per_hour:,.0f}경기 (유저 기록 약 {per_hour * 2:,.0f}건)")
    result["calls_per_match"] = round(calls_per_match, 2)
    result["matches_per_hour_estimate"] = round(per_hour)

dist = Counter(DIV_NAME.get(v, "알 수 없음") for v in user_div.values())
print("\n등급 확인한 유저의 등급 분포:")
for name, cnt in sorted(dist.items(), key=lambda x: -x[1]):
    print(f"  {name}: {cnt}명")

seed_div = user_div.get(seeds[0])
if seed_div in DIV_ORDER:
    near = sum(1 for v in user_div.values()
               if v in DIV_ORDER and abs(DIV_ORDER[v] - DIV_ORDER[seed_div]) <= 1)
    ratio = near / len(user_div) * 100
    print(f"\n시작 유저와 같은 등급 ±1단계 비율: {ratio:.0f}%")
    result["same_tier_ratio"] = round(ratio)

print(f"\n총 호출: {calls}회 / 오류: {dict(errors) or '없음'}")
result.update({
    "calls_per_minute": round(per_min),
    "matches": matches,
    "records": records,
    "users_found": len(seen_users),
    "division_distribution": dict(dist),
    "errors": {str(k): v for k, v in errors.items()},
})
with open("probe_snowball_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("결과를 probe_snowball_result.json 파일로 저장했습니다.")