"""
넥슨 Open API 일일 한도 확인
- 가벼운 호출 1회를 보내서 지금 한도가 남아 있는지 확인
- 응답 헤더에 한도 관련 정보가 있으면 같이 출력
- 주의: 확인할 때마다 한도 1회를 씀
"""
import os
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("NEXON_API_KEY")
if not key:
    raise SystemExit(".env에서 NEXON_API_KEY를 읽지 못했습니다.")

r = requests.get(
    "https://open.api.nexon.com/fconline/v1/id",
    headers={"x-nxopen-api-key": key},
    params={"nickname": "우태안"},
    timeout=15,
)

print(f"확인 시각: {datetime.now():%Y-%m-%d %H:%M:%S}")
print(f"키 앞부분: {key[:8]}...")
print(f"응답 코드: {r.status_code}")

if r.status_code == 200:
    print("→ 한도가 남아 있습니다. collect_bulk.py를 실행해도 됩니다.")
elif r.status_code == 429:
    print("→ 오늘 한도를 다 썼습니다. 자정 이후 다시 확인하세요.")
    print("   응답 내용:", r.text[:200])
else:
    print("→ 한도 문제가 아닌 다른 오류입니다:", r.text[:200])

# 한도·호출 수 관련 헤더가 있으면 출력
limit_headers = {k: v for k, v in r.headers.items()
                 if any(w in k.lower() for w in ("limit", "remain", "rate", "quota", "reset"))}
print("\n한도 관련 응답 헤더:", limit_headers or "없음")