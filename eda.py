"""
원본 데이터 EDA (탐색적 데이터 분석)
입력: data/records_raw.csv, data/records_clean.csv, data/dataset_win.csv, data/dataset_shots.csv
출력: docs/figures/*.png (그래프), docs/eda_summary.md (README에 붙일 표)
"""
import os
import json

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 한글 폰트 (Windows: 맑은 고딕)
for name in ["Malgun Gothic", "AppleGothic", "NanumGothic"]:
    if any(name in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = name
        break
plt.rcParams["axes.unicode_minus"] = False

FIG = os.path.join("docs", "figures")
os.makedirs(FIG, exist_ok=True)
BLUE, GRAY, RED = "#2f6fdf", "#9aa3ad", "#d9534f"

raw = pd.read_csv("data/records_raw.csv")
clean = pd.read_csv("data/records_clean.csv")
data = pd.read_csv("data/dataset_win.csv")
features = [c for c in data.columns if c not in ("match_id", "user", "tier_group", "win")]


def save(name):
    plt.tight_layout()
    plt.savefig(os.path.join(FIG, name), dpi=150)
    plt.close()
    print(f"저장: docs/figures/{name}")


# 1. 날짜별 경기 수
dates = pd.to_datetime(raw.drop_duplicates("match_id")["match_date"]).dt.date
by_day = dates.value_counts().sort_index()
plt.figure(figsize=(9, 3.5))
plt.bar(by_day.index.astype(str), by_day.values, color=BLUE)
plt.title(f"날짜별 수집 경기 수 (총 {len(dates):,}경기)")
plt.ylabel("경기 수")
plt.xticks(rotation=60, fontsize=8)
save("01_matches_by_date.png")

# 2. 경기 결과 분포 + 종료 유형
fig, ax = plt.subplots(1, 2, figsize=(9, 3.5))
res = raw["result"].value_counts().reindex(["승", "무", "패"]).fillna(0)
ax[0].bar(res.index, res.values, color=[BLUE, GRAY, RED])
ax[0].set_title("경기 결과 분포 (원본)")
end = raw["match_end_type"].map({0: "정상 종료"}).fillna("몰수·비정상").value_counts()
ax[1].bar(end.index, end.values, color=[BLUE, RED][:len(end)])
ax[1].set_title("경기 종료 유형 (원본)")
save("02_result_and_end_type.png")

# 3. 등급 분포 (등급 확인된 유저 기록)
tiers = clean["division_name"].dropna().value_counts()
if len(tiers):
    plt.figure(figsize=(9, 3.8))
    plt.barh(tiers.index[::-1], tiers.values[::-1], color=BLUE)
    plt.title(f"등급 분포 (등급 확인된 기록 {tiers.sum():,}건, 역대 최고 등급 기준)")
    plt.xlabel("기록 수")
    save("03_division_distribution.png")

# 4. 주요 지표 분포
key = ["possession", "shoot_total", "shoot_effective", "pass_try",
       "pass_rate", "through_pass_try", "tackle_try", "goals_for", "goals_against"]
fig, axes = plt.subplots(3, 3, figsize=(10, 8))
for a, col in zip(axes.flat, key):
    a.hist(clean[col].dropna(), bins=30, color=BLUE, alpha=0.85)
    a.set_title(col, fontsize=10)
save("04_feature_distributions.png")

# 5. 승리 vs 패배 평균 비교 (패배 평균 대비 승리 평균의 차이, %)
mean = data.groupby("win")[features].mean().T
diff = ((mean[1] - mean[0]) / mean[0].replace(0, pd.NA) * 100).dropna().sort_values()
plt.figure(figsize=(8, 7))
plt.barh(diff.index, diff.values, color=[BLUE if v > 0 else RED for v in diff.values])
plt.axvline(0, color="black", linewidth=0.8)
plt.title("승리 기록이 패배 기록보다 몇 % 높은가 (지표별 평균)")
plt.xlabel("차이 (%)")
save("05_win_vs_loss.png")

# 6. 승패 라벨과의 상관계수
corr = data[features + ["win"]].corr()["win"].drop("win").sort_values()
plt.figure(figsize=(8, 7))
plt.barh(corr.index, corr.values, color=[BLUE if v > 0 else RED for v in corr.values])
plt.axvline(0, color="black", linewidth=0.8)
plt.title("지표와 승리(win=1)의 상관계수")
save("06_correlation_with_win.png")

# 7. 요약 표 (README용)
desc = clean[key].describe().T[["mean", "std", "min", "50%", "max"]].round(2)
missing = raw.isna().sum()
missing = missing[missing > 0]
with open("docs/eda_summary.md", "w", encoding="utf-8") as f:
    f.write("### 주요 지표 기술통계 (전처리 후)\n\n")
    f.write(desc.to_markdown() + "\n\n")
    f.write("### 원본 결측치\n\n")
    f.write((missing.to_frame("결측 건수").to_markdown() if len(missing) else "결측치 없음") + "\n\n")
    f.write("### 승리와 상관이 큰 지표 상위 5개\n\n")
    f.write(corr.abs().sort_values(ascending=False).head(5).round(3).to_frame("|상관계수|").to_markdown() + "\n")
print("저장: docs/eda_summary.md")

# 8. 슈팅 데이터셋 EDA
shots = pd.read_csv("data/dataset_shots.csv")
goal, miss = shots[shots["goal"] == 1], shots[shots["goal"] == 0]
plt.figure(figsize=(7, 5))
plt.scatter(miss["x"], miss["y"], s=4, alpha=0.25, color=GRAY, label=f"골 아님 {len(miss):,}")
plt.scatter(goal["x"], goal["y"], s=6, alpha=0.6, color=RED, label=f"골 {len(goal):,}")
plt.xlim(0.5, 1.0)
plt.ylim(0, 1)
plt.xlabel("x (1 = 상대 골라인)")
plt.ylabel("y")
plt.title(f"슈팅 위치와 결과 (총 {len(shots):,}회)")
plt.legend(loc="lower left")
save("07_shot_map.png")

shots["dist_bin"] = pd.cut(shots["distance"], bins=[0, 0.05, 0.1, 0.15, 0.2, 0.3, 1.5])
by_dist = shots.groupby("dist_bin", observed=True)["goal"].agg(["mean", "count"])
fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
ax[0].bar(by_dist.index.astype(str), by_dist["mean"] * 100, color=BLUE)
ax[0].set_title("골대까지 거리별 골 성공률 (%)")
ax[0].tick_params(axis="x", rotation=30, labelsize=8)
by_type = shots.groupby("type")["goal"].agg(["mean", "count"])
by_type = by_type[by_type["count"] >= 30]
ax[1].bar(by_type.index.astype(str), by_type["mean"] * 100, color=BLUE)
ax[1].set_title("슈팅 종류(type 코드)별 골 성공률 (%, 30회 이상)")
save("08_shot_goal_rate.png")

with open("docs/eda_summary.md", "a", encoding="utf-8") as f:
    f.write("\n### 슈팅 거리별 골 성공률\n\n")
    f.write((by_dist.assign(mean=(by_dist["mean"] * 100).round(1))
             .rename(columns={"mean": "골 성공률(%)", "count": "슈팅 수"}).to_markdown()) + "\n")

summary = {
    "dates": f"{dates.min()} ~ {dates.max()}",
    "top_corr": corr.abs().sort_values(ascending=False).head(5).round(3).to_dict(),
    "win_vs_loss_top": diff.abs().sort_values(ascending=False).head(5).round(1).to_dict(),
}
print(json.dumps(summary, ensure_ascii=False, indent=2))