"""
전체 매치 목록 API(/match)에 어떤 파라미터 조합이 통하는지 확인
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
URL = "https://open.api.nexon.com/fconline/v1/match"
HEADERS = {"x-nxopen-api-key": os.getenv("NEXON_API_KEY")}

tests = [
    {"matchtype": 50},
    {"matchtype": 50, "offset": 0, "limit": 10},
    {"matchtype": 50, "offset": 0, "limit": 10, "orderby": "desc"},
    {"matchtype": 50, "offset": 0, "limit": 10, "orderby": "asc"},
    {"matchtype": 50, "offset": 0, "limit": 100},
    {"matchtype": 50, "offset": 0, "limit": 100, "orderby": "desc"},
    {"matchtype": 50, "offset": 0, "limit": 1000},
    {"matchtype": 50, "offset": 1000, "limit": 10},
    {"matchtype": 50, "offset": 100000, "limit": 10},
    {"matchtype": 52, "offset": 0, "limit": 10},
]

for params in tests:
    r = requests.get(URL, headers=HEADERS, params=params, timeout=15)
    if r.status_code == 200:
        data = r.json()
        n = len(data) if isinstance(data, list) else "?"
        print(f"[성공] {params} → {n}개")
    else:
        print(f"[실패 {r.status_code}] {params} → {r.text[:120]}")