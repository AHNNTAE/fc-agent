import os
import requests
from dotenv import load_dotenv

load_dotenv()
BASE = "https://open.api.nexon.com/fconline/v1"
HEADERS = {"x-nxopen-api-key": os.getenv("NEXON_API_KEY")}


def get_ouid(nickname):
    res = requests.get(f"{BASE}/id", headers=HEADERS, params={"nickname": nickname})
    res.raise_for_status()
    return res.json()["ouid"]


def get_match_ids(ouid, limit=20, matchtype=50):
    res = requests.get(f"{BASE}/user/match", headers=HEADERS,
                       params={"ouid": ouid, "matchtype": matchtype, "offset": 0, "limit": limit})
    res.raise_for_status()
    return res.json()


def get_match_detail(match_id):
    res = requests.get(f"{BASE}/match-detail", headers=HEADERS, params={"matchid": match_id})
    res.raise_for_status()
    return res.json()