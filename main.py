import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nexon import get_ouid
from db import init_db, add_tactic_change, list_tactic_changes, delete_tactic_change
from collect import collect_matches
from analysis import analyze, load_matches, compare
from coach import Coach

app = FastAPI(title="FC 에이전트")
app.mount("/static", StaticFiles(directory="static"), name="static")
init_db()

coaches = {}     # 닉네임별 AI 코치 대화 (서버를 끄면 초기화됨)
ouid_cache = {}  # 닉네임 → ouid (넥슨 API 호출 줄이기)


class NicknameIn(BaseModel):
    nickname: str


class ChatIn(BaseModel):
    nickname: str
    message: str


class TacticIn(BaseModel):
    nickname: str
    change_date: str
    memo: str


def find_ouid(nickname):
    if nickname in ouid_cache:
        return ouid_cache[nickname]
    try:
        ouid = get_ouid(nickname)
    except requests.HTTPError:
        raise HTTPException(404, "해당 닉네임의 유저를 찾지 못했습니다.")
    except requests.RequestException:
        raise HTTPException(502, "넥슨 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.")
    ouid_cache[nickname] = ouid
    return ouid


def tactics_with_compare(ouid):
    """전술 변경 기록마다 전후 비교 결과를 붙여서 반환"""
    items = list_tactic_changes(ouid)
    for t in items:
        t["compare"] = compare(ouid, t["change_date"])
    return items


def refresh_coach(nickname):
    """진행 중인 코치 대화가 있으면, 대화는 유지하고 참고 데이터만 갱신"""
    coach = coaches.get(nickname)
    if coach is None:
        return
    ouid = find_ouid(nickname)
    report = analyze(ouid)
    if report:
        coach.update_context(report, tactics_with_compare(ouid))


@app.get("/")
def index():
    return FileResponse("static/index.html")


# ---------- 경기 기록 / 분석 ----------

@app.post("/api/collect")
def api_collect(body: NicknameIn):
    nickname = body.nickname.strip()
    ouid = find_ouid(nickname)
    try:
        result = collect_matches(ouid, limit=50)
    except requests.RequestException:
        raise HTTPException(502, "경기 기록을 불러오는 중 오류가 났습니다. 잠시 후 다시 시도해 주세요.")
    coaches.pop(nickname, None)  # 화면의 대화창도 새로 시작하므로 코치도 새로 만듦
    return result


@app.get("/api/report")
def api_report(nickname: str):
    nickname = nickname.strip()
    ouid = find_ouid(nickname)
    report = analyze(ouid)
    if report is None:
        raise HTTPException(404, "저장된 경기가 없습니다. 먼저 경기 기록을 불러오세요.")

    keys = ("match_date", "result", "my_goal", "opp_goal", "opp_nickname",
            "possession", "shoot_total", "shoot_effective")
    recent = [{k: m[k] for k in keys} for m in load_matches(ouid, limit=15)]
    return {"nickname": nickname, "stats": report["stats"],
            "insights": report["insights"], "recent": recent}


# ---------- AI 코치 ----------

@app.post("/api/chat")
def api_chat(body: ChatIn):
    nickname = body.nickname.strip()
    coach = coaches.get(nickname)
    if coach is None:
        ouid = find_ouid(nickname)
        report = analyze(ouid)
        if report is None:
            raise HTTPException(404, "저장된 경기가 없습니다. 먼저 경기 기록을 불러오세요.")
        coach = Coach(nickname, report, tactics_with_compare(ouid))
        coaches[nickname] = coach
    answer, model = coach.ask(body.message)
    return {"answer": answer, "model": model}


# ---------- 전술 변경 전후 비교 ----------

@app.get("/api/tactics")
def api_tactics(nickname: str):
    return {"items": tactics_with_compare(find_ouid(nickname.strip()))}


@app.post("/api/tactics")
def api_add_tactic(body: TacticIn):
    nickname = body.nickname.strip()
    memo = body.memo.strip()
    if not body.change_date or not memo:
        raise HTTPException(400, "변경 시점과 변경 내용을 모두 입력해 주세요.")
    ouid = find_ouid(nickname)
    new_id = add_tactic_change(ouid, body.change_date, memo[:100])
    refresh_coach(nickname)
    return {"id": new_id}


@app.delete("/api/tactics/{change_id}")
def api_delete_tactic(change_id: int, nickname: str):
    nickname = nickname.strip()
    if not delete_tactic_change(change_id, find_ouid(nickname)):
        raise HTTPException(404, "해당 기록을 찾지 못했습니다.")
    refresh_coach(nickname)
    return {"ok": True}