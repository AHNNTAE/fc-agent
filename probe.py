"""
FC 온라인 데이터 수집 가능성 조사 스크립트
- 결과는 화면에 출력되고 probe_result.json 파일로도 저장됨
"""
import os
import time
import json
from collections import Counter
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()
BASE = "https://open.api.nexon.com/fconline/v1"
META = "https://open.api.nexon.com/static/fconline/meta"
HEADERS = {"x-nxopen-api-key": os.getenv("NEXON_API_KEY")}
MATCHTYPE = 50          # 50 = 공식경기
SAMPLE_MATCHES = 30     # 속도·등급 분포 측정에 쓸 경기 수

calls = {"total": 0, "errors": Counter()}
result = {}


def call(path, params=None, retry_429=True):
    """API 호출. 실패하면 (None, 응답) 반환. 429(한도 초과)면 1초 쉬고 한 번 재시도"""
    calls["total"] += 1
    r = requests.get(f"{BASE}{path}", headers=HEADERS, params=params, timeout=15)
    if r.status_code == 429 and retry_429:
        calls["errors"][429] += 1
        time.sleep(1)
        return call(path, params, retry_429=False)
    if r.status_code != 200:
        calls["errors"][r.status_code] += 1
        return None, r
    return r.json(), r


def title(text):
    print("\n" + "=" * 60 + f"\n{text}\n" + "=" * 60)


def parse_date(s):
    return datetime.fromisoformat(str(s)[:19]) if s else None


# ---------------------------------------------------------------
title("1. 전체 공식경기 목록 조회")
ids, r = call("/match", {"matchtype": MATCHTYPE, "offset": 0, "limit": 100, "orderby": "desc"})
if ids is None:
    print(f"실패: {r.status_code} {r.text[:300]}")
    print("→ 전체 매치 목록 API를 쓸 수 없습니다. 이 결과를 그대로 보내주세요.")
    raise SystemExit
print(f"한 번에 받은 경기 ID 수: {len(ids)}개 (limit=100 요청)")
result["match_list_ok"] = True
result["match_list_count"] = len(ids)


def match_date(mid):
    d, _ = call("/match-detail", {"matchid": mid})
    return parse_date(d.get("matchDate")) if d else None


print("\n얼마나 과거까지 조회되는지 확인 (offset = 최신 경기로부터 몇 번째인지)")
depth = []
for off in [0, 1_000, 10_000, 100_000, 1_000_000]:
    res, r = call("/match", {"matchtype": MATCHTYPE, "offset": off, "limit": 1, "orderby": "desc"})
    if not res:
        print(f"  offset {off:>9,}: 결과 없음 (상태 {r.status_code if r is not None else '-'})")
        break
    dt = match_date(res[0])
    depth.append((off, dt))
    print(f"  offset {off:>9,}: 경기 시각 {dt}")

if len(depth) >= 2 and depth[0][1] and depth[-1][1]:
    (o1, t1), (o2, t2) = depth[0], depth[-1]
    hours = max((t1 - t2).total_seconds() / 3600, 1e-6)
    per_hour = (o2 - o1) / hours
    print(f"\n→ 조회 가능한 범위: 최소 {t2} ~ {t1} ({hours:.1f}시간)")
    print(f"→ 공식경기는 시간당 약 {per_hour:,.0f}경기가 열리는 것으로 추정")
    result["depth_hours"] = round(hours, 1)
    result["official_matches_per_hour"] = round(per_hour)

# ---------------------------------------------------------------
title("2. 경기 상세 기록에 들어 있는 지표 (레이더 차트 후보)")
detail, _ = call("/match-detail", {"matchid": ids[0]})
info = detail["matchInfo"][0]
fields = {}
for section in ["matchDetail", "shoot", "pass", "defence"]:
    data = info.get(section) or {}
    simple = {k: v for k, v in data.items() if not isinstance(v, (list, dict))}
    fields[section] = list(simple.keys())
    print(f"\n[{section}]")
    for k, v in simple.items():
        print(f"  {k}: {v}")
result["available_fields"] = fields

# ---------------------------------------------------------------
title("3. 유저 등급 조회")
div_meta = requests.get(f"{META}/division.json", headers=HEADERS, timeout=15).json()
div_name = {d["divisionId"]: d["divisionName"] for d in div_meta}
print("등급 목록:", ", ".join(div_name.values()))


def official_division(ouid):
    data, _ = call("/user/maxdivision", {"ouid": ouid})
    if not data:
        return None
    for d in data:
        if d.get("matchType") == MATCHTYPE:
            return d.get("division")
    return None


sample_ouid = info.get("ouid")
raw, _ = call("/user/maxdivision", {"ouid": sample_ouid})
print(f"\n예시 유저의 최고 등급 응답 원본: {raw}")

# ---------------------------------------------------------------
title(f"4. 수집 속도 측정 + 무작위 경기의 등급 분포 ({SAMPLE_MATCHES}경기)")
print("1~2분 정도 걸립니다...")
before_calls = calls["total"]
start = time.perf_counter()
div_counter = Counter()
seen = set()
players = 0

for mid in ids[:SAMPLE_MATCHES]:
    d, _ = call("/match-detail", {"matchid": mid})
    if not d:
        continue
    for p in d.get("matchInfo", []):
        ouid = p.get("ouid")
        if not ouid or ouid in seen:
            continue
        seen.add(ouid)
        players += 1
        div = official_division(ouid)
        div_counter[div_name.get(div, "알 수 없음")] += 1

elapsed = time.perf_counter() - start
used = calls["total"] - before_calls
per_min = used / elapsed * 60
calls_per_match = used / SAMPLE_MATCHES
matches_per_hour = per_min * 60 / calls_per_match

print(f"\n호출 {used}회 / {elapsed:.1f}초 → 분당 약 {per_min:.0f}회 호출 가능")
print(f"경기 1개당 평균 호출 수: {calls_per_match:.1f}회 (상세 1 + 유저 등급 조회)")
print(f"→ 1시간 수집 시 약 {matches_per_hour:,.0f}경기, 유저 약 {matches_per_hour * 2:,.0f}명 (중복 제외 전)")
print(f"\n무작위 {players}명의 등급 분포:")
for name, cnt in div_counter.most_common():
    print(f"  {name}: {cnt}명")

result.update({
    "calls_per_minute": round(per_min),
    "calls_per_match": round(calls_per_match, 1),
    "matches_per_hour_estimate": round(matches_per_hour),
    "division_distribution": dict(div_counter),
})

# ---------------------------------------------------------------
title("요약")
print(f"총 API 호출: {calls['total']}회")
print(f"오류 응답: {dict(calls['errors']) or '없음'}")
result["total_calls"] = calls["total"]
result["errors"] = {str(k): v for k, v in calls["errors"].items()}

with open("probe_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
print("결과를 probe_result.json 파일로 저장했습니다.")