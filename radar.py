"""
"내 등급 기준" 레이더 차트 계산 (서버용, 텐서플로우·numpy 없이 동작)
- static/tier_stats.json (build_tier_stats.py 결과)을 읽어서
  내 지표가 내 등급 안에서 상위 몇 %인지, 바로 위 등급 평균과 얼마나 차이 나는지 계산
"""
import os
import json
import math

import requests

from nexon import BASE, HEADERS
from db import get_conn

STATS_PATH = os.path.join("static", "tier_stats.json")
_stats = None
_division_cache = {}


def load_stats():
    global _stats
    if _stats is None and os.path.exists(STATS_PATH):
        with open(STATS_PATH, encoding="utf-8") as f:
            _stats = json.load(f)
    return _stats


def get_division(ouid):
    """공식경기 역대 최고 등급 (같은 유저는 서버가 켜져 있는 동안 다시 조회하지 않음)"""
    if ouid not in _division_cache:
        res = requests.get(f"{BASE}/user/maxdivision", headers=HEADERS,
                           params={"ouid": ouid}, timeout=15)
        res.raise_for_status()
        div = next((d.get("division") for d in res.json() if d.get("matchType") == 50), None)
        _division_cache[ouid] = div
    return _division_cache[ouid]


def percentile(value, q):
    """5% 단위 분위수 목록 q에서 value가 몇 % 위치인지 (0~100)"""
    if value is None or not q:
        return None
    if value <= q[0]:
        return 0.0
    if value >= q[-1]:
        return 100.0
    for i in range(len(q) - 1):
        lo, hi = q[i], q[i + 1]
        if lo <= value <= hi:
            if hi == lo:
                return i * 5 + 2.5
            return i * 5 + 5 * (value - lo) / (hi - lo)
    return None


def shot_xg(shot, lookup):
    d = math.sqrt((1 - (shot.get("x") or 0)) ** 2 + (0.5 - (shot.get("y") or 0.5)) ** 2)
    bins = lookup["bins"]
    i = next((k for k in range(len(bins) - 1) if d <= bins[k + 1]), len(bins) - 2)
    table = lookup["by_type"].get(str(shot.get("type")), lookup["overall"])
    return table[i]


def user_metrics(ouid, lookup, limit=50):
    """앱 DB에 저장된 최근 경기(몰수 제외)로 레이더 지표 계산"""
    with get_conn() as conn:
        rows = conn.execute("""SELECT raw_json FROM matches WHERE ouid=? AND is_forfeit=0
                               ORDER BY match_date DESC LIMIT ?""", (ouid, limit)).fetchall()
    sums = {k: [] for k in ("shoot_effective", "opp_shoot_effective", "effective_shot_rate",
                            "possession", "pass_rate", "tackle_rate")}
    shots, goals, xg_sum = 0, 0, 0.0
    for (raw,) in rows:
        d = json.loads(raw)
        info = d.get("matchInfo", [])
        me = next((p for p in info if p.get("ouid") == ouid), None)
        opp = next((p for p in info if p.get("ouid") != ouid), None)
        if not me or not opp:
            continue
        sh, osh = me.get("shoot") or {}, opp.get("shoot") or {}
        ps, df, md = me.get("pass") or {}, me.get("defence") or {}, me.get("matchDetail") or {}
        sums["shoot_effective"].append(sh.get("effectiveShootTotal") or 0)
        sums["opp_shoot_effective"].append(osh.get("effectiveShootTotal") or 0)
        if sh.get("shootTotal"):
            sums["effective_shot_rate"].append((sh.get("effectiveShootTotal") or 0) / sh["shootTotal"])
        if md.get("possession") is not None:
            sums["possession"].append(md["possession"])
        if ps.get("passTry"):
            sums["pass_rate"].append((ps.get("passSuccess") or 0) / ps["passTry"])
        if df.get("tackleTry"):
            sums["tackle_rate"].append((df.get("tackleSuccess") or 0) / df["tackleTry"])
        for s in me.get("shootDetail") or []:
            if s.get("result") in (1, 2, 3):
                shots += 1
                goals += 1 if s["result"] == 3 else 0
                xg_sum += shot_xg(s, lookup)
    metrics = {k: (sum(v) / len(v) if v else None) for k, v in sums.items()}
    metrics["finishing"] = (goals - xg_sum) / shots * 100 if shots else None
    return metrics, len(rows), shots


def compute_radar(ouid):
    stats = load_stats()
    if not stats:
        return {"available": False, "reason": "등급별 기준값 파일(static/tier_stats.json)이 없습니다."}

    div = get_division(ouid)
    group = stats["division_to_group"].get(str(div)) if div is not None else None
    if group not in stats["tiers"]:
        return {"available": False, "tier": group,
                "reason": f"'{group or '알 수 없음'}' 등급은 아직 비교할 표본이 부족합니다."}

    metrics, n_matches, n_shots = user_metrics(ouid, stats["xg_lookup"])
    if n_matches < stats["min_matches"]:
        return {"available": False, "tier": group,
                "reason": f"비교하려면 몰수 제외 공식경기 {stats['min_matches']}경기 이상이 필요합니다."}

    order = stats["tier_order"]
    idx = order.index(group)
    next_tier = order[idx - 1] if idx > 0 else None
    tier, nxt = stats["tiers"][group], stats["tiers"].get(next_tier) if next_tier else None

    axes, gaps = [], []
    for a in stats["axes"]:
        k, hib, scale = a["key"], a["higher_is_better"], a["scale"]
        dist = tier["axes"].get(k)
        val = metrics.get(k)
        if k == "finishing" and n_shots < stats["min_shots"]:
            val = None
        if not dist:
            continue

        def score(v):
            p = percentile(v, dist["q"])
            return None if p is None else round(p if hib else 100 - p, 1)

        nmean = nxt["axes"][k]["mean"] if nxt and k in nxt["axes"] else None
        item = {
            "key": k, "label": a["label"], "desc": a["desc"], "unit": a["unit"],
            "higher_is_better": hib,
            "me": None if val is None else round(val * scale, 2),
            "tier_mean": round(dist["mean"] * scale, 2),
            "next_mean": None if nmean is None else round(nmean * scale, 2),
            "me_score": score(val),
            "tier_score": score(dist["mean"]),
            "next_score": score(nmean),
        }
        axes.append(item)
        if item["me_score"] is not None and item["next_score"] is not None:
            gap = item["next_score"] - item["me_score"]
            if gap > 5:
                gaps.append({**item, "gap": round(gap, 1)})

    gaps.sort(key=lambda g: g["gap"], reverse=True)
    return {
        "available": True, "tier": group, "next_tier": next_tier,
        "tier_users": tier["users"], "matches": n_matches, "shots": n_shots,
        "axes": axes, "gaps": gaps[:3], "generated_at": stats["generated_at"],
    }