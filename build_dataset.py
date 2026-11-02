"""
전처리 + 라벨링 → 학습 데이터셋 구축
입력: data/fc_dataset.db (collect_bulk.py 결과)
출력:
  data/records_raw.csv        경기 1개 × 유저 2명 = 유저 기록 (원본 그대로 펼친 것)
  data/records_clean.csv      전처리 후 유저 기록 (분석용)
  data/dataset_win.csv        승패 라벨링 학습 데이터셋 (무승부 제외, 결과 누수 항목 제외)
  data/shots_raw.csv          슈팅 1회 = 1건 원본
  data/dataset_shots.csv      골 여부 라벨링 학습 데이터셋
  docs/preprocess_report.json 단계별 건수 기록 (README에 사용)
"""
import os
import json
import zlib
import sqlite3
import hashlib

import pandas as pd
import requests

DB_PATH = os.path.join("data", "fc_dataset.db")
os.makedirs("docs", exist_ok=True)


def h(ouid):
    """유저 ID는 공개 저장소에 올리지 않도록 짧은 해시로 바꿈"""
    return hashlib.sha1(ouid.encode()).hexdigest()[:12]


def load_division_names():
    try:
        meta = requests.get("https://open.api.nexon.com/static/fconline/meta/division.json",
                            timeout=15).json()
        return {d["divisionId"]: d["divisionName"] for d in meta}
    except Exception:
        return {}


def g(d, *keys):
    for k in keys:
        d = (d or {}).get(k)
    return d


# ---------------- 1. 원본 펼치기 ----------------
conn = sqlite3.connect(DB_PATH)
users = dict(conn.execute("SELECT ouid, division FROM users WHERE processed = 1").fetchall())
div_name = load_division_names()

rows = []
shots = []
for mid, mdate, raw in conn.execute("SELECT match_id, match_date, raw FROM matches"):
    d = json.loads(zlib.decompress(raw).decode("utf-8"))
    info = d.get("matchInfo", [])
    for i, p in enumerate(info):
        opp = info[1 - i] if len(info) == 2 else {}
        md, sh, ps, df = p.get("matchDetail"), p.get("shoot"), p.get("pass"), p.get("defence")
        div = users.get(p.get("ouid"))
        # 슈팅 1회 = 1건 (같은 경기의 슈팅 상세 기록)
        for k, sd in enumerate(p.get("shootDetail") or []):
            shots.append({
                "match_id": mid,
                "user": h(p.get("ouid", "")),
                "division": div,
                "match_end_type": g(md, "matchEndType"),
                "user_goal_total": g(sh, "goalTotal"),
                "shot_no": k,
                "x": sd.get("x"),
                "y": sd.get("y"),
                "type": sd.get("type"),
                "result": sd.get("result"),
                "in_penalty": sd.get("inPenalty"),
                "assist": sd.get("assist"),
                "hit_post": sd.get("hitPost"),
                "sp_grade": sd.get("spGrade"),
                "sp_level": sd.get("spLevel"),
                "goal_time": sd.get("goalTime"),
            })
        rows.append({
            "match_id": mid,
            "match_date": mdate,
            "user": h(p.get("ouid", "")),
            "division": div,
            "division_name": div_name.get(div, str(div)) if div is not None else None,
            "result": g(md, "matchResult"),
            "match_end_type": g(md, "matchEndType"),
            "controller": g(md, "controller"),
            "goals_for": g(sh, "goalTotal"),
            "goals_against": g(opp, "shoot", "goalTotal"),
            "possession": g(md, "possession"),
            "average_rating": g(md, "averageRating"),
            "foul": g(md, "foul"),
            "yellow_cards": g(md, "yellowCards"),
            "red_cards": g(md, "redCards"),
            "corner_kick": g(md, "cornerKick"),
            "offside": g(md, "offsideCount"),
            "dribble": g(md, "dribble"),
            "shoot_total": g(sh, "shootTotal"),
            "shoot_effective": g(sh, "effectiveShootTotal"),
            "shoot_in_penalty": g(sh, "shootInPenalty"),
            "shoot_out_penalty": g(sh, "shootOutPenalty"),
            "shoot_heading": g(sh, "shootHeading"),
            "pass_try": g(ps, "passTry"),
            "pass_success": g(ps, "passSuccess"),
            "short_pass_try": g(ps, "shortPassTry"),
            "short_pass_success": g(ps, "shortPassSuccess"),
            "long_pass_try": g(ps, "longPassTry"),
            "long_pass_success": g(ps, "longPassSuccess"),
            "through_pass_try": g(ps, "throughPassTry"),
            "through_pass_success": g(ps, "throughPassSuccess"),
            "tackle_try": g(df, "tackleTry"),
            "tackle_success": g(df, "tackleSuccess"),
            "block_try": g(df, "blockTry"),
            "block_success": g(df, "blockSuccess"),
            "opp_shoot_total": g(opp, "shoot", "shootTotal"),
            "opp_shoot_effective": g(opp, "shoot", "effectiveShootTotal"),
        })
conn.close()

raw_df = pd.DataFrame(rows)
raw_df.to_csv("data/records_raw.csv", index=False, encoding="utf-8-sig")
report = {"matches": int(raw_df["match_id"].nunique()), "records_raw": len(raw_df)}
print(f"[1] 원본 유저 기록: {len(raw_df):,}건 (경기 {report['matches']:,}개)")

# ---------------- 2. 전처리 ----------------
df = raw_df.copy()
steps = []


def step(name, mask):
    global df
    before = len(df)
    df = df[mask]
    steps.append({"step": name, "removed": before - len(df), "remaining": len(df)})
    print(f"[2] {name}: -{before - len(df):,}건 → {len(df):,}건")


step("중복 기록 제거", ~df.duplicated(["match_id", "user"]))
step("몰수·비정상 종료 경기 제거 (matchEndType != 0)", df["match_end_type"].fillna(-1) == 0)
step("상대 기록이 없는 경기 제거", df["goals_against"].notna() & df["opp_shoot_total"].notna())
step("결과 값이 없거나 이상한 기록 제거", df["result"].isin(["승", "무", "패"]))
step("패스 시도 0회 기록 제거 (사실상 경기 미진행)", df["pass_try"].fillna(0) > 0)

# 비율 지표 (0으로 나누면 0)
def rate(a, b):
    return (df[a] / df[b].where(df[b] > 0)).fillna(0).round(4)

df["pass_rate"] = rate("pass_success", "pass_try")
df["short_pass_rate"] = rate("short_pass_success", "short_pass_try")
df["long_pass_rate"] = rate("long_pass_success", "long_pass_try")
df["through_pass_rate"] = rate("through_pass_success", "through_pass_try")
df["effective_shot_rate"] = rate("shoot_effective", "shoot_total")
df["in_box_shot_ratio"] = rate("shoot_in_penalty", "shoot_total")
df["tackle_rate"] = rate("tackle_success", "tackle_try")
df["block_rate"] = rate("block_success", "block_try")
df["tier_group"] = df["division_name"].astype("string").str.replace(r"\d+$", "", regex=True)

df.to_csv("data/records_clean.csv", index=False, encoding="utf-8-sig")
report.update({"records_clean": len(df), "preprocess_steps": steps})
print(f"[2] 전처리 후 유저 기록: {len(df):,}건")

# ---------------- 3. 라벨링 ----------------
# 라벨: win (승=1, 패=0). 무승부는 승패 어느 쪽도 아니므로 제외
# 피처: 경기 중 플레이 지표만 사용. 득점·실점·평점은 결과를 직접 반영하므로 제외 (정보 누수 방지)
FEATURES = [
    "possession", "shoot_total", "shoot_effective", "effective_shot_rate",
    "in_box_shot_ratio", "shoot_heading", "pass_try", "pass_rate",
    "short_pass_rate", "long_pass_try", "long_pass_rate",
    "through_pass_try", "through_pass_rate", "dribble",
    "tackle_try", "tackle_rate", "block_try", "block_rate",
    "foul", "corner_kick", "offside",
    "opp_shoot_total", "opp_shoot_effective",
]
lab = df[df["result"].isin(["승", "패"])].copy()
lab["win"] = (lab["result"] == "승").astype(int)
lab[FEATURES] = lab[FEATURES].fillna(0)
dataset = lab[["match_id", "user", "tier_group"] + FEATURES + ["win"]]
dataset.to_csv("data/dataset_win.csv", index=False, encoding="utf-8-sig")

report.update({
    "draws_excluded": int((df["result"] == "무").sum()),
    "dataset_rows": len(dataset),
    "label_counts": {"win=1": int(dataset["win"].sum()), "win=0": int((dataset["win"] == 0).sum())},
    "features": FEATURES,
    "records_with_division": int(df["division"].notna().sum()),
})
print(f"[3] 라벨링 데이터셋: {len(dataset):,}건 "
      f"(승 {report['label_counts']['win=1']:,} / 패 {report['label_counts']['win=0']:,}, "
      f"무승부 {report['draws_excluded']:,}건 제외)")

# ---------------- 4. 슈팅 데이터셋 (슈팅 1회 = 1건) ----------------
# 라벨: goal (골=1, 골 아님=0). 넥슨 문서 기준 슈팅 결과 result: 1=유효슛, 2=무효슛, 3=골
sh_raw = pd.DataFrame(shots)
sh_raw.to_csv("data/shots_raw.csv", index=False, encoding="utf-8-sig")
print(f"\n[4] 원본 슈팅 기록: {len(sh_raw):,}건")
print("    result 값 분포:", sh_raw["result"].value_counts().to_dict())
print("    type 값 분포:", sh_raw["type"].value_counts().to_dict())

s_df = sh_raw.copy()
s_steps = []
for name, mask in [
    ("몰수·비정상 종료 경기의 슈팅 제거", s_df["match_end_type"].fillna(-1) == 0),
    ("좌표가 없거나 범위(0~1)를 벗어난 슈팅 제거",
     s_df["x"].between(0, 1) & s_df["y"].between(0, 1)),
    ("결과 값이 1·2·3이 아닌 슈팅 제거", s_df["result"].isin([1, 2, 3])),
]:
    before = len(s_df)
    s_df = s_df[mask.reindex(s_df.index, fill_value=False)]
    s_steps.append({"step": name, "removed": before - len(s_df), "remaining": len(s_df)})
    print(f"[4] {name}: -{before - len(s_df):,}건 → {len(s_df):,}건")

# 라벨 검증: 슈팅 상세의 골 수 합계가 경기 기록의 골 수(goalTotal)와 맞는지
check = s_df.assign(is_goal=(s_df["result"] == 3)).groupby(["match_id", "user"]).agg(
    shot_goals=("is_goal", "sum"), goal_total=("user_goal_total", "first"))
match_rate = (check["shot_goals"] == check["goal_total"]).mean() * 100
print(f"[4] 라벨 검증: 슈팅 상세 골 수 = 경기 기록 골 수 일치율 {match_rate:.1f}%")

# 골대 중앙(x=1, y=0.5) 기준 거리와 각도
s_df["distance"] = (((1 - s_df["x"]) ** 2 + (0.5 - s_df["y"]) ** 2) ** 0.5).round(4)
s_df["angle"] = (abs(0.5 - s_df["y"]) / (1 - s_df["x"]).clip(lower=0.001)).round(4)
s_df["goal"] = (s_df["result"] == 3).astype(int)
s_df["tier_group"] = (s_df["division"]
                     .map(lambda d: div_name.get(int(d), str(int(d))) if pd.notna(d) else None)
                     .astype("string").str.replace(r"\d+$", "", regex=True))
SHOT_FEATURES = ["x", "y", "distance", "angle", "type", "in_penalty", "assist", "sp_grade", "sp_level"]
s_df[SHOT_FEATURES] = s_df[SHOT_FEATURES].fillna(0)
shot_ds = s_df[["match_id", "user", "tier_group"] + SHOT_FEATURES + ["goal"]]
shot_ds.to_csv("data/dataset_shots.csv", index=False, encoding="utf-8-sig")
print(f"[4] 슈팅 데이터셋: {len(shot_ds):,}건 (골 {shot_ds['goal'].sum():,} / "
      f"골 아님 {(shot_ds['goal'] == 0).sum():,})")

report["shots"] = {
    "shots_raw": len(sh_raw),
    "preprocess_steps": s_steps,
    "label_check_match_rate": round(match_rate, 1),
    "dataset_rows": len(shot_ds),
    "label_counts": {"goal=1": int(shot_ds["goal"].sum()), "goal=0": int((shot_ds["goal"] == 0).sum())},
    "features": SHOT_FEATURES,
    "result_values": {str(k): int(v) for k, v in sh_raw["result"].value_counts().items()},
    "type_values": {str(k): int(v) for k, v in sh_raw["type"].value_counts().items()},
}

with open("docs/preprocess_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print("\n단계별 건수를 docs/preprocess_report.json에 저장했습니다.")