import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("NEXON_API_KEY")
BASE = "https://open.api.nexon.com/fconline/v1"
HEADERS = {"x-nxopen-api-key": API_KEY}

nickname = input("닉네임 입력: ")

# 1) 닉네임으로 유저 고유 ID(ouid) 조회
res = requests.get(f"{BASE}/id", headers=HEADERS, params={"nickname": nickname})
print("유저 조회:", res.status_code, res.json())
ouid = res.json().get("ouid")
if not ouid:
    raise SystemExit("유저를 찾지 못했습니다.")

# 2) 최근 공식경기(matchtype=50) 10개 ID 조회
res = requests.get(f"{BASE}/user/match", headers=HEADERS,
                   params={"ouid": ouid, "matchtype": 50, "offset": 0, "limit": 10})
match_ids = res.json()
print(f"최근 경기 {len(match_ids)}개")

# 3) 각 경기 결과 출력
for mid in match_ids:
    detail = requests.get(f"{BASE}/match-detail", headers=HEADERS,
                          params={"matchid": mid}).json()
    players = detail.get("matchInfo", [])
    me = next((p for p in players if p.get("ouid") == ouid), None)
    opp = next((p for p in players if p.get("ouid") != ouid), None)
    if not me or not opp:
        continue
    my_goal = me.get("shoot", {}).get("goalTotal")
    opp_goal = opp.get("shoot", {}).get("goalTotal")
    result = me.get("matchDetail", {}).get("matchResult")
    print(f"{detail.get('matchDate')} | {result} | {my_goal} : {opp_goal} | vs {opp.get('nickname')}")