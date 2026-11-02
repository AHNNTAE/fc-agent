import os
import requests
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("NEXON_API_KEY")

print("키가 읽혔는지:", "예" if key else "아니요 (.env 확인 필요)")
if key:
    print("키 앞부분:", key[:8] + "...", "/ 길이:", len(key))

r = requests.get(
    "https://open.api.nexon.com/fconline/v1/id",
    headers={"x-nxopen-api-key": key or ""},
    params={"nickname": "우태안"},
    timeout=15,
)
print("응답 코드:", r.status_code)
print("응답 내용:", r.text[:300])