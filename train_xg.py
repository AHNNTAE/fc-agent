"""
기대득점(xG) 모델 학습
- 슈팅 1회가 골이 될 확률을 예측 (입력: data/dataset_shots.csv)
- 비교: ① 평균값만 쓰는 기준선 ② 로지스틱 회귀(scikit-learn) ③ 텐서플로우 신경망
- 경기 단위로 학습/평가 데이터를 나눔 (같은 경기의 슈팅이 양쪽에 섞이지 않게)
출력:
  models/xg_model.keras, models/xg_features.json   학습된 모델과 입력 컬럼 목록
  data/xg_predictions.csv                          모든 슈팅의 xG (5겹 교차검증 예측)
  docs/model_report.json, docs/model_results.md    성능표와 등급별 결정력 (README용)
  docs/figures/09_xg_calibration.png               예측 확률 vs 실제 골 비율
  docs/figures/10_xg_map.png                       위치별 xG 지도
  docs/figures/11_finishing_by_tier.png            등급별 결정력 (실제 골 - xG)
"""
import os
import json

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")   # 텐서플로우 안내 메시지 줄이기

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from sklearn.model_selection import GroupShuffleSplit, GroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss
import tensorflow as tf

SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)

for name in ["Malgun Gothic", "AppleGothic", "NanumGothic"]:
    if any(name in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = name
        break
plt.rcParams["axes.unicode_minus"] = False
BLUE, GRAY, RED = "#2f6fdf", "#9aa3ad", "#d9534f"
FIG = os.path.join("docs", "figures")
os.makedirs(FIG, exist_ok=True)
os.makedirs("models", exist_ok=True)


def save(name):
    plt.tight_layout()
    plt.savefig(os.path.join(FIG, name), dpi=150)
    plt.close()
    print(f"저장: docs/figures/{name}")


# ---------------- 1. 데이터 준비 ----------------
df = pd.read_csv("data/dataset_shots.csv")


def to01(s):
    return s.astype(str).str.lower().isin(["true", "1", "1.0"]).astype(float)


df["in_penalty"] = to01(df["in_penalty"])
df["assist"] = to01(df["assist"])
df["type"] = df["type"].fillna(0).astype(int)
NUM = ["x", "y", "distance", "angle", "in_penalty", "assist", "sp_grade", "sp_level"]
df[NUM] = df[NUM].apply(pd.to_numeric, errors="coerce").fillna(0)

# 슈팅 종류는 숫자가 크기를 뜻하지 않으므로 원-핫 인코딩 (50회 미만 종류는 '기타'로 묶음)
counts = df["type"].value_counts()
TYPES = sorted(counts[counts >= 50].index.tolist())


def make_X(frame):
    X = frame[NUM].copy()
    for t in TYPES:
        X[f"type_{t}"] = (frame["type"] == t).astype(float)
    X["type_other"] = (~frame["type"].isin(TYPES)).astype(float)
    return X.astype("float32")


X = make_X(df)
y = df["goal"].astype(int).values
groups = df["match_id"].values
FEATURES = X.columns.tolist()
print(f"슈팅 {len(df):,}건 | 골 비율 {y.mean():.1%} | 입력 컬럼 {len(FEATURES)}개")

# 경기 단위로 학습 80% / 평가 20%
tr_idx, te_idx = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
                      .split(X, y, groups))
X_tr, X_te, y_tr, y_te = X.iloc[tr_idx], X.iloc[te_idx], y[tr_idx], y[te_idx]
print(f"학습 {len(tr_idx):,}건 / 평가 {len(te_idx):,}건 (경기 단위로 분리)\n")


def build_model():
    norm = tf.keras.layers.Normalization()
    norm.adapt(X_tr.values)
    model = tf.keras.Sequential([
        tf.keras.Input(shape=(len(FEATURES),)),
        norm,
        tf.keras.layers.Dense(64, activation="relu"),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(32, activation="relu"),
        tf.keras.layers.Dense(1, activation="sigmoid"),
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3),
                  loss="binary_crossentropy",
                  metrics=[tf.keras.metrics.AUC(name="auc")])
    return model


def fit(model, Xa, ya, verbose=0):
    stop = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5,
                                            restore_best_weights=True)
    return model.fit(Xa, ya, validation_split=0.15, epochs=60, batch_size=256,
                     callbacks=[stop], verbose=verbose)


def scores(p, yt):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return {"AUC": round(roc_auc_score(yt, p), 4),
            "LogLoss": round(log_loss(yt, p), 4),
            "Brier": round(brier_score_loss(yt, p), 4)}


# ---------------- 2. 모델 3개 비교 ----------------
results = {}
results["기준선 (평균 골 비율)"] = scores(np.full(len(y_te), y_tr.mean()), y_te)

scaler = StandardScaler().fit(X_tr)
lr = LogisticRegression(max_iter=2000).fit(scaler.transform(X_tr), y_tr)
p_lr = lr.predict_proba(scaler.transform(X_te))[:, 1]
results["로지스틱 회귀"] = scores(p_lr, y_te)

print("텐서플로우 신경망 학습 중...")
model = build_model()
hist = fit(model, X_tr.values, y_tr, verbose=2)
p_nn = model.predict(X_te.values, verbose=0).ravel()
results["텐서플로우 신경망"] = scores(p_nn, y_te)

print("\n===== 평가 데이터 성능 (AUC 높을수록, LogLoss·Brier 낮을수록 좋음) =====")
res_df = pd.DataFrame(results).T
print(res_df.to_string())

model.save("models/xg_model.keras")
with open("models/xg_features.json", "w", encoding="utf-8") as f:
    json.dump({"features": FEATURES, "numeric": NUM, "types": TYPES}, f, ensure_ascii=False)
print("\n저장: models/xg_model.keras")

# ---------------- 3. 보정 그래프 (예측 확률 vs 실제 골 비율) ----------------
bins = np.linspace(0, 1, 11)
plt.figure(figsize=(5.5, 5))
plt.plot([0, 1], [0, 1], "--", color=GRAY, label="완벽한 예측")
for p, name, c in [(p_lr, "로지스틱 회귀", GRAY), (p_nn, "텐서플로우 신경망", BLUE)]:
    b = pd.cut(p, bins, include_lowest=True)
    cal = pd.DataFrame({"p": p, "y": y_te, "b": b}).groupby("b", observed=True).agg(
        pred=("p", "mean"), real=("y", "mean"), n=("y", "size"))
    cal = cal[cal["n"] >= 20]
    plt.plot(cal["pred"], cal["real"], "o-", color=c, label=name)
plt.xlabel("예측한 골 확률 (xG)")
plt.ylabel("실제 골 비율")
plt.title("예측 확률과 실제 골 비율 (평가 데이터)")
plt.legend()
save("09_xg_calibration.png")

# ---------------- 4. 위치별 xG 지도 ----------------
gx, gy = np.meshgrid(np.linspace(0.70, 0.995, 60), np.linspace(0.15, 0.85, 60))
grid = pd.DataFrame({"x": gx.ravel(), "y": gy.ravel()})
grid["distance"] = np.sqrt((1 - grid["x"]) ** 2 + (0.5 - grid["y"]) ** 2)
grid["angle"] = (0.5 - grid["y"]).abs() / (1 - grid["x"]).clip(lower=0.001)
# 박스 안 여부는 실제 슈팅 데이터에서 그 위치의 다수값을 사용
cell = lambda a, b: (np.clip((a - 0.70) / 0.30 * 30, 0, 29).astype(int) * 100
                     + np.clip((b - 0.15) / 0.70 * 30, 0, 29).astype(int))
box_rate = df.assign(c=cell(df["x"], df["y"])).groupby("c")["in_penalty"].mean()
grid["in_penalty"] = (cell(grid["x"], grid["y"]).map(box_rate).fillna(0) >= 0.5).astype(float)
grid["assist"] = df["assist"].mean().round()
grid["sp_grade"] = df["sp_grade"].median()
grid["sp_level"] = df["sp_level"].median()
grid["type"] = int(df["type"].mode()[0])
xg_grid = model.predict(make_X(grid).values, verbose=0).reshape(gx.shape)

plt.figure(figsize=(7, 5.5))
im = plt.pcolormesh(gx, gy, xg_grid, cmap="Reds", vmin=0, vmax=1, shading="auto")
plt.colorbar(im, label="골 확률 (xG)")
plt.xlabel("x (1 = 상대 골라인)")
plt.ylabel("y")
plt.title(f"위치별 기대득점 (가장 흔한 슈팅 종류 {grid['type'].iloc[0]}번 기준)")
save("10_xg_map.png")

# ---------------- 5. 모든 슈팅의 xG (5겹 교차검증) + 등급별 결정력 ----------------
print("\n등급별 결정력 계산을 위해 5겹 교차검증 중 (몇 분 걸릴 수 있음)...")
oof = np.zeros(len(df))
for k, (a, b) in enumerate(GroupKFold(n_splits=5).split(X, y, groups), 1):
    X_tr, y_tr = X.iloc[a], y[a]          # build_model의 정규화 기준을 이 겹의 학습 데이터로 바꿈
    m = build_model()
    fit(m, X_tr.values, y_tr)
    oof[b] = m.predict(X.iloc[b].values, verbose=0).ravel()
    print(f"  {k}/5 완료")
df["xg"] = oof.round(4)
df[["match_id", "user", "tier_group", "x", "y", "type", "goal", "xg"]].to_csv(
    "data/xg_predictions.csv", index=False, encoding="utf-8-sig")
print("저장: data/xg_predictions.csv")

tier = df.dropna(subset=["tier_group"]).groupby("tier_group").agg(
    슈팅=("goal", "size"), 실제골=("goal", "sum"), 기대골=("xg", "sum"))
tier = tier[tier["슈팅"] >= 300].copy()
tier["실제 골 비율(%)"] = (tier["실제골"] / tier["슈팅"] * 100).round(1)
tier["평균 xG(%)"] = (tier["기대골"] / tier["슈팅"] * 100).round(1)
tier["결정력(실제-기대, %p)"] = (tier["실제 골 비율(%)"] - tier["평균 xG(%)"]).round(1)
tier["기대골"] = tier["기대골"].round(1)
tier = tier.sort_values("결정력(실제-기대, %p)")

if len(tier):
    plt.figure(figsize=(8, 0.5 * len(tier) + 1.5))
    v = tier["결정력(실제-기대, %p)"]
    plt.barh(tier.index, v, color=[BLUE if x > 0 else RED for x in v])
    plt.axvline(0, color="black", linewidth=0.8)
    plt.xlabel("실제 골 비율 - 평균 xG (%p)  |  0보다 크면 기대보다 골을 더 넣음")
    plt.title("등급별 결정력 (슈팅 300회 이상 등급, 역대 최고 등급 기준)")
    save("11_finishing_by_tier.png")

# ---------------- 6. 보고서용 저장 ----------------
report = {
    "shots": len(df), "goal_rate": round(float(y.mean()), 4),
    "train": int(len(tr_idx)), "test": int(len(te_idx)),
    "features": FEATURES, "results": results,
    "nn_epochs": len(hist.history["loss"]),
    "tier_finishing": tier.reset_index().to_dict(orient="records"),
}
with open("docs/model_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
with open("docs/model_results.md", "w", encoding="utf-8") as f:
    f.write("### xG 모델 성능 (평가 데이터, 경기 단위 분리)\n\n" + res_df.to_markdown() + "\n\n")
    f.write("### 등급별 결정력 (5겹 교차검증 xG 기준)\n\n"
            + (tier.to_markdown() if len(tier) else "등급 정보가 있는 슈팅이 부족함") + "\n")
print("저장: docs/model_report.json, docs/model_results.md")
print("\n===== 등급별 결정력 =====")
print(tier.to_string() if len(tier) else "등급 정보가 있는 슈팅이 부족함")