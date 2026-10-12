import json
from db import get_conn


def load_matches(ouid, limit=50, before=None, after=None):
    """몰수 경기를 뺀 경기 불러오기. before/after로 날짜 범위를 자를 수 있음"""
    sql = "SELECT * FROM matches WHERE ouid=? AND is_forfeit=0"
    params = [ouid]
    if before:
        sql += " AND match_date < ?"
        params.append(before)
    if after:
        sql += " AND match_date >= ?"
        params.append(after)
    # 변경 후 경기는 변경 시점에 가까운 경기부터, 그 외에는 최신 경기부터
    sql += " ORDER BY match_date " + ("ASC" if after else "DESC") + " LIMIT ?"
    params.append(limit)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def opp_shoot(raw_json, ouid):
    """저장해 둔 원본 데이터에서 상대 슈팅 기록 꺼내기"""
    d = json.loads(raw_json)
    opp = next((p for p in d.get("matchInfo", []) if p.get("ouid") != ouid), {})
    s = opp.get("shoot", {}) or {}
    return s.get("shootTotal") or 0, s.get("effectiveShootTotal") or 0


def pct(a, b):
    return round(a / b * 100, 1) if b else 0


def compute_stats(ms, ouid):
    """경기 목록으로 지표 계산"""
    n = len(ms)
    if n == 0:
        return None

    win = sum(m["result"] == "승" for m in ms)
    draw = sum(m["result"] == "무" for m in ms)
    lose = sum(m["result"] == "패" for m in ms)

    gf = sum(m["my_goal"] or 0 for m in ms)
    ga = sum(m["opp_goal"] or 0 for m in ms)
    shots = sum(m["shoot_total"] or 0 for m in ms)
    eff = sum(m["shoot_effective"] or 0 for m in ms)
    out_shots = sum(m["shoot_out_box"] or 0 for m in ms)
    out_goals = sum(m["goal_out_box"] or 0 for m in ms)

    opp_shots, opp_eff = 0, 0
    for m in ms:
        s, e = opp_shoot(m["raw_json"], ouid)
        opp_shots += s
        opp_eff += e

    high = [m for m in ms if (m["possession"] or 0) >= 50]
    low = [m for m in ms if (m["possession"] or 0) < 50]

    return {
        "경기 수": n, "승": win, "무": draw, "패": lose,
        "승률": pct(win, n),
        "경기당 득점": round(gf / n, 2),
        "경기당 실점": round(ga / n, 2),
        "내 유효슈팅 대비 득점률": pct(gf, eff),
        "상대 유효슈팅 대비 실점률": pct(ga, opp_eff),
        "경기당 상대 유효슈팅": round(opp_eff / n, 2),
        "박스 밖 슈팅 비율": pct(out_shots, shots),
        "박스 밖 슈팅 성공률": pct(out_goals, out_shots),
        "점유율 50% 이상 경기 수": len(high),
        "점유율 50% 이상 승률": pct(sum(m["result"] == "승" for m in high), len(high)),
        "점유율 50% 미만 경기 수": len(low),
        "점유율 50% 미만 승률": pct(sum(m["result"] == "승" for m in low), len(low)),
        "3골 이상 넣고 못 이긴 경기": sum(1 for m in ms
                                   if m["result"] in ("무", "패") and (m["my_goal"] or 0) >= 3),
    }


def find_insights(s):
    """지표를 보고 규칙 기반으로 약점 찾기"""
    insights = []
    if s["경기당 실점"] >= 2.5:
        insights.append(f"경기당 평균 {s['경기당 실점']:.1f}골을 실점합니다. "
                        f"득점({s['경기당 득점']:.1f}골)에 비해 실점이 많아 수비 개선이 가장 시급합니다.")
    if s["상대 유효슈팅 대비 실점률"] >= 60:
        insights.append(f"상대 유효슈팅의 {s['상대 유효슈팅 대비 실점률']}%가 골로 연결됩니다. "
                        f"상대에게 1:1이나 빈 골대 같은 결정적인 기회를 자주 내주고 있습니다.")
    if s["3골 이상 넣고 못 이긴 경기"] >= 3:
        insights.append(f"3골 이상 넣고도 비기거나 진 경기가 {s['3골 이상 넣고 못 이긴 경기']}경기입니다. "
                        f"공격력은 충분하지만 실점 때문에 승점을 놓치고 있습니다.")
    if s["박스 밖 슈팅 비율"] >= 40 and s["박스 밖 슈팅 성공률"] < 15:
        insights.append(f"슈팅의 {s['박스 밖 슈팅 비율']}%가 박스 밖에서 나오지만 성공률은 "
                        f"{s['박스 밖 슈팅 성공률']}%에 그칩니다. 박스 안까지 침투한 뒤 슈팅하는 편이 좋습니다.")

    hi, lo = s["점유율 50% 이상 승률"], s["점유율 50% 미만 승률"]
    if s["점유율 50% 이상 경기 수"] and s["점유율 50% 미만 경기 수"]:
        if hi - lo >= 20:
            insights.append(f"점유율 50% 이상일 때 승률 {hi}%, 미만일 때 {lo}%입니다. "
                            f"공을 오래 소유하는 운영이 잘 맞습니다.")
        elif lo - hi >= 20:
            insights.append(f"점유율이 낮을 때 승률({lo}%)이 오히려 높습니다. "
                            f"역습 위주 전술이 더 잘 맞을 수 있습니다.")

    if not insights:
        insights.append("뚜렷한 약점이 보이지 않습니다. 경기 기록을 더 쌓으면 정확도가 올라갑니다.")
    return insights


def analyze(ouid):
    s = compute_stats(load_matches(ouid), ouid)
    if s is None:
        return None
    return {"stats": s, "insights": find_insights(s)}


# ---------- 전술 변경 전후 비교 ----------

COMPARE_KEYS = ["승률", "경기당 득점", "경기당 실점",
                "내 유효슈팅 대비 득점률", "상대 유효슈팅 대비 실점률", "경기당 상대 유효슈팅"]
LOWER_IS_BETTER = {"경기당 실점", "상대 유효슈팅 대비 실점률", "경기당 상대 유효슈팅"}
MIN_GAMES = 5


def compare(ouid, change_date, window=20):
    before_ms = load_matches(ouid, window, before=change_date)
    after_ms = load_matches(ouid, window, after=change_date)
    b = compute_stats(before_ms, ouid)
    a = compute_stats(after_ms, ouid)

    rows = []
    for k in COMPARE_KEYS:
        bv = b[k] if b else None
        av = a[k] if a else None
        diff = round(av - bv, 2) if (b and a) else None
        better = None
        if diff not in (None, 0):
            better = diff < 0 if k in LOWER_IS_BETTER else diff > 0
        rows.append({"key": k, "before": bv, "after": av, "diff": diff, "better": better})

    return {
        "before_n": len(before_ms),
        "after_n": len(after_ms),
        "enough": len(before_ms) >= MIN_GAMES and len(after_ms) >= MIN_GAMES,
        "min_games": MIN_GAMES,
        "rows": rows,
    }


if __name__ == "__main__":
    from nexon import get_ouid
    nickname = input("닉네임 입력: ")
    report = analyze(get_ouid(nickname))
    if report is None:
        print("저장된 경기가 없습니다. collect.py를 먼저 실행하세요.")
    else:
        print("\n===== 경기 분석 리포트 =====")
        for k, v in report["stats"].items():
            print(f"{k}: {v}")
        print("\n===== 발견된 약점 =====")
        for i, s in enumerate(report["insights"], 1):
            print(f"{i}. {s}")