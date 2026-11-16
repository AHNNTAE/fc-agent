"""
등급별 기준값 만들기 → static/tier_stats.json
- 입력: data/records_clean.csv (build_dataset.py), data/xg_predictions.csv (train_xg.py)
- 등급마다 '유저별 평균'의 분포(평균 + 5% 단위 분위수)를 계산
- 서버는 이 파일만 읽어서 "내 등급 안에서 상위 몇 %"를 계산함 (텐서플로우 불필요)
- 통계값만 들어 있고 유저 ID는 없으므로 GitHub에 올려도 됨
"""
import os
import json
from datetime import datetime

import numpy as np
import pandas as pd
import requests

MIN_MATCHES_PER_USER = 5      # 유저 평균을 낼 최소 경기 수
MIN_SHOTS_PER_USER = 20       # 결정력을 낼 최소 슈팅 수
MIN_USERS_PER_TIER = 8        # 등급 기준값을 만들 최소 유저 수
DIST_BINS = [0, 0.05, 0.1, 0.15, 0.2, 0.3, 1.5]

# key, 이름, 설명, 높을수록 좋은지, 화면 표시 배율, 단위
AXES = [
    ("shoot_effective", "유효슈팅", "경기당 유효슈팅 수", True, 1, "개"),
    ("opp_shoot_effective", "실점 억제", "경기당 허용한 상대 유효슈팅 (적을수록 좋음)", False, 1, "개"),
    ("effective_shot_rate", "슈팅 정확도", "슈팅 중 유효슈팅 비율", True, 100, "%"),
    ("possession", "점유율", "평균 점유율", True, 1, "%"),
    ("pass_rate", "패스 성공률", "패스 성공 비율", True, 100, "%"),
    ("tackle_rate", "태클 성공률", "태클 성공 비율", True, 100, "%"),
    ("finishing", "결정력", "실제 골 비율 - 기대 골 비율(xG)", True, 1, "%p"),
]

rec = pd.read_csv("data/records_clean.csv")
xg = pd.read_csv("data/xg_predictions.csv")

# ---------- 1. 유저별 평균 ----------
rec = rec.dropna(subset=["tier_group"])
keys = [a[0] for a in AXES if a[0] != "finishing"]
users = rec.groupby("user").agg(tier_group=("tier_group", "first"),
                                division=("division", "first"),
                                matches=("match_id", "size"),
                                **{k: (k, "mean") for k in keys})
users = users[users["matches"] >= MIN_MATCHES_PER_USER]

shots = xg.groupby("user").agg(shots=("goal", "size"), goals=("goal", "sum"), xg=("xg", "sum"))
shots = shots[shots["shots"] >= MIN_SHOTS_PER_USER]
shots["finishing"] = (shots["goals"] - shots["xg"]) / shots["shots"] * 100
users = users.join(shots[["finishing"]], how="left")
print(f"기준값에 쓰는 유저: {len(users):,}명 (등급 확인 + {MIN_MATCHES_PER_USER}경기 이상)")

# ---------- 2. 등급 순서 (divisionId가 작을수록 높은 등급) ----------
try:
    meta = requests.get("https://open.api.nexon.com/static/fconline/meta/division.json", timeout=15).json()
    div_name = {int(d["divisionId"]): d["divisionName"] for d in meta}
except Exception:
    div_name = {}
div_to_group = {}
for d, g in rec.dropna(subset=["division"]).groupby("division")["tier_group"].first().items():
    div_to_group[int(d)] = g
for d, name in div_name.items():
    div_to_group.setdefault(d, pd.Series([name]).str.replace(r"\d+$", "", regex=True)[0])
group_rank = {}
for d, g in sorted(div_to_group.items()):
    group_rank.setdefault(g, d)          # 그 등급의 가장 높은 단계 divisionId
order_all = sorted(group_rank, key=group_rank.get)   # 높은 등급 → 낮은 등급

# ---------- 3. 등급별 분포 ----------
Q = list(range(0, 101, 5))
tiers = {}
for g, part in users.groupby("tier_group"):
    if len(part) < MIN_USERS_PER_TIER:
        print(f"  {g}: 유저 {len(part)}명 → 표본 부족으로 제외")
        continue
    t = {"users": int(len(part)), "axes": {}}
    for key, *_ in AXES:
        v = part[key].dropna()
        if len(v) < MIN_USERS_PER_TIER:
            continue
        t["axes"][key] = {"mean": round(float(v.mean()), 4), "n": int(len(v)),
                          "q": [round(float(x), 4) for x in np.percentile(v, Q)]}
    tiers[g] = t
tier_order = [g for g in order_all if g in tiers]

# ---------- 4. xG 조회표 (거리 구간 × 슈팅 종류) ----------
xg["distance"] = np.sqrt((1 - xg["x"]) ** 2 + (0.5 - xg["y"]) ** 2)
xg["bin"] = pd.cut(xg["distance"], DIST_BINS, labels=False, include_lowest=True)
overall = xg.groupby("bin")["xg"].mean()
lookup = {"bins": DIST_BINS,
          "overall": [round(float(overall.get(i, xg["xg"].mean())), 4) for i in range(len(DIST_BINS) - 1)],
          "by_type": {}}
for t, part in xg.groupby("type"):
    stat = part.groupby("bin")["xg"].agg(["mean", "count"])
    lookup["by_type"][str(int(t))] = [
        round(float(stat.loc[i, "mean"]), 4) if i in stat.index and stat.loc[i, "count"] >= 30
        else lookup["overall"][i] for i in range(len(DIST_BINS) - 1)]

out = {
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "axes": [{"key": k, "label": l, "desc": d, "higher_is_better": h, "scale": s, "unit": u}
             for k, l, d, h, s, u in AXES],
    "tier_order": tier_order,
    "tiers": tiers,
    "division_to_group": {str(k): v for k, v in div_to_group.items()},
    "xg_lookup": lookup,
    "min_matches": MIN_MATCHES_PER_USER, "min_shots": MIN_SHOTS_PER_USER,
}
os.makedirs("static", exist_ok=True)
with open(os.path.join("static", "tier_stats.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

print("\n등급 (높은 순) | 유저 수 | " + " | ".join(a[1] for a in AXES))
for g in tier_order:
    row = [f"{tiers[g]['axes'][k]['mean'] * s:.1f}" if k in tiers[g]["axes"] else "-"
           for k, _, _, _, s, _ in AXES]
    print(f"{g} | {tiers[g]['users']} | " + " | ".join(row))
print("\n저장: static/tier_stats.json")