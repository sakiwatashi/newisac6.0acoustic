"""Stage-3 machine-learning suite (P1/P2/learned-ranging), offline, zero GPU.

All data are previously landed raw waveforms from the formal experiments; this
script trains/evaluates only -- it changes no experimental record.

═══ 預註冊設計(先於執行寫定;參數選擇之理由逐條載明)═══

模型:Ridge 線性迴歸(E1/E3)與 Ridge 分數作二元排序(E2)。
  理由:(a) 樣本量僅數十至數百,深度模型必過擬合;(b) 線性模型之權重可逐樣本
  歸因,延續本研究「因果可追溯」之一貫紀律;(c) 確定性引擎下資料無雜訊,
  模型容量過大只會記憶而非學習。**刻意不用深度網路是設計,不是妥協。**
正則化強度 alpha:於訓練摺內以內層交叉驗證自 {1e-4,1e-3,...,1e2} 選定。
  理由:唯一的自由超參數,交由資料決定,不手調。
交叉驗證:5 摺,**以「情境」分組**(E1 依幾何點、E2 依場景格、E3 依試驗回合)。
  理由:確定性模擬下同情境之波形近乎逐位相同,若隨機切分,訓練集會「見過」
  測試集的雙胞胎 → 分數虛高。分組切分杜絕此洩漏,測的是對「新情境」之泛化。
特徵:原始 320 樣本波形,逐特徵標準化。不做人工特徵工程。
  理由:E1 的科學問題正是「整條波形是否含峰值位置以外之資訊」,
  預先萃取特徵會污染這個問題。

判準(預先寫定):
  E1 learned-ranging:同摺對照——解析法(峰值×當摺自校迴歸)vs 波形 Ridge,
     報兩者 5 摺 RMSE。問題:波形模型能否追平或超越解析法?(兩種答案皆有價值)
  E2 presence(P2 第一關):場景分組 5 摺 AUC ≥ 0.7 為通過門檻
     (承 V2 計畫 §8 之原預註冊止損:AUC<0.7 → 不做任何後續目標狀態宣稱)。
  E3 ego-state(P1):回合分組 5 摺 R²,如實報告(V2 計畫 §8:報 R²、5-fold)。

Usage: python3 scripts/ml_stage3_suite.py
"""
from __future__ import annotations

import csv
import json
import math
import pathlib

import numpy as np
from sklearn.linear_model import RidgeCV, Ridge
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "runtime" / "outputs" / "ml_stage3"
OUT.mkdir(parents=True, exist_ok=True)
ALPHAS = np.logspace(-4, 2, 7)
WF_LEN = 320
report: dict = {}


def _load_wf(path: pathlib.Path) -> np.ndarray | None:
    try:
        w = np.load(path)
        if w.size < WF_LEN:
            return None
        return np.asarray(w[:WF_LEN], dtype=float)
    except Exception:
        return None


def _ridge_cv_rmse(X, y, groups, n_splits=5):
    gkf = GroupKFold(n_splits=n_splits)
    errs, preds = [], np.full(len(y), np.nan)
    for tr, te in gkf.split(X, y, groups):
        sc = StandardScaler().fit(X[tr])
        m = RidgeCV(alphas=ALPHAS).fit(sc.transform(X[tr]), y[tr])
        p = m.predict(sc.transform(X[te]))
        preds[te] = p
        errs.append(float(np.sqrt(np.mean((p - y[te]) ** 2))))
    return float(np.mean(errs)), float(np.std(errs)), preds


# ═══════════════ E1:學習式測距 vs 解析校正(同摺對照)═══════════════
print("═══ E1 學習式測距 vs 解析校正 ═══")
X1, y1, pk1, g1 = [], [], [], []
# S2 distance_p1 + tableh(p2/p3 與 p1 逐位相同,納入即洩漏,棄用)
for sub, note in (("distance_p1", "boresight"), ("distance_tableh", "tableh")):
    d = ROOT / "runtime/outputs/v2_s2_datasheet" / sub
    for r in csv.DictReader((d / "points.csv").open()):
        w = _load_wf(d / "waveforms" / f"{r['waveform_tag']}_primary.npy")
        td = float(r["true_distance_3d_m"])
        if w is None or not math.isfinite(td):
            continue
        X1.append(w); y1.append(td)
        pk1.append(float(r["peak_sample_idx"]))
        g1.append(f"{note}_{r['waveform_tag']}")
# D2 formal 掃描視點(sensor/target 已知 → 真實 3D 距離)
for arm in ("closed", "blind"):
    d = ROOT / "runtime/outputs/v2_d2v2_formal" / arm
    eps = {r["episode"]: (float(r["target_x"]), float(r["target_y"]))
           for r in csv.DictReader((d / "episodes.csv").open())}
    for r in csv.DictReader((d / "steps.csv").open()):
        if r.get("phase") != "vantage":
            continue
        w = _load_wf(d / "waveforms" / f"{r['waveform_tag']}.npy")
        if w is None:
            continue
        tx, ty = eps[r["episode"]]
        sx, sy = float(r["sensor_x"]), float(r["sensor_y"])
        td = math.sqrt((tx - sx) ** 2 + (ty - sy) ** 2 + 0.19 ** 2)
        X1.append(w); y1.append(td)
        pk1.append(float(np.argmax(w)))
        g1.append(f"{arm}_ep{r['episode']}")   # 依回合分組
X1, y1, pk1 = np.array(X1), np.array(y1), np.array(pk1)
print(f"樣本 n={len(y1)}(S2 兩幾何 + D2 兩臂視點),距離範圍 {y1.min():.2f}–{y1.max():.2f} m")

rmse_ml, rmse_ml_sd, _ = _ridge_cv_rmse(X1, y1, np.array(g1))
# 解析法同摺對照:各摺以訓練摺擬合 peak→dist 直線
gkf = GroupKFold(n_splits=5)
an_errs = []
for tr, te in gkf.split(X1, y1, np.array(g1)):
    A = np.vstack([pk1[tr], np.ones(len(tr))]).T
    coef, *_ = np.linalg.lstsq(A, y1[tr], rcond=None)
    p = pk1[te] * coef[0] + coef[1]
    an_errs.append(float(np.sqrt(np.mean((p - y1[te]) ** 2))))
rmse_an, rmse_an_sd = float(np.mean(an_errs)), float(np.std(an_errs))
print(f"解析法(峰值×當摺自校): RMSE = {rmse_an*100:.2f} ± {rmse_an_sd*100:.2f} cm")
print(f"波形 Ridge(320 維):    RMSE = {rmse_ml*100:.2f} ± {rmse_ml_sd*100:.2f} cm")
verdict1 = "波形模型優於解析法" if rmse_ml < rmse_an * 0.9 else (
    "兩者相當(解析法已榨乾波形中的距離資訊)" if rmse_ml < rmse_an * 1.25 else "解析法較佳")
print(f"E1 結論:{verdict1}")
report["E1"] = {"n": int(len(y1)), "rmse_analytic_cm": rmse_an * 100,
                "rmse_ridge_cm": rmse_ml * 100, "verdict": verdict1}

# ═══════════════ E2:目標存在偵測(P2 第一關,AUC 門檻 0.7)═══════════════
print("\n═══ E2 目標存在偵測(P2 第一關)═══")
X2, y2, g2 = [], [], []
for cell_dir in sorted((ROOT / "runtime/outputs/v2_s1_envelope").iterdir()):
    wfdir = cell_dir / "waveforms"
    if not wfdir.is_dir():
        continue
    for tag, lab in (("with", 1), ("without", 0)):
        w = _load_wf(wfdir / f"{tag}.npy")
        if w is not None:
            X2.append(w); y2.append(lab); g2.append(cell_dir.name)
X2, y2 = np.array(X2), np.array(y2)
print(f"樣本 n={len(y2)}(S1 {len(set(g2))} 場景 × 有/無目標;依場景分組 5 摺)")
gkf = GroupKFold(n_splits=5)
scores = np.full(len(y2), np.nan)
for tr, te in gkf.split(X2, y2, np.array(g2)):
    sc = StandardScaler().fit(X2[tr])
    m = RidgeCV(alphas=ALPHAS).fit(sc.transform(X2[tr]), y2[tr])
    scores[te] = m.predict(sc.transform(X2[te]))
auc = float(roc_auc_score(y2, scores))
gate = auc >= 0.7
print(f"分組交叉驗證 AUC = {auc:.4f}")
print(f"ADJUDICATION p2_presence_auc_ge_0.7: {gate}")
report["E2"] = {"n": int(len(y2)), "auc": auc, "gate_pass": bool(gate)}

# ═══════════════ E3:自體狀態回歸(P1)═══════════════
print("\n═══ E3 自體狀態回歸(P1:波形 → 感測器位置)═══")
X3, y3, g3 = [], [], []
for run, arm in (("v2_d15_arm_approach", "closed"), ("v2_d15_arm_approach", "blind"),
                 ("v2_d2v2_formal", "closed"), ("v2_d2v2_formal", "blind")):
    d = ROOT / "runtime/outputs" / run / arm
    for r in csv.DictReader((d / "steps.csv").open()):
        tag = r.get("waveform_tag", "")
        if not tag:
            continue
        w = _load_wf(d / "waveforms" / f"{tag}_primary.npy")
        if w is None:
            w = _load_wf(d / "waveforms" / f"{tag}.npy")
        if w is None:
            continue
        sx = float(r.get("sensor_x", "nan"))
        if not math.isfinite(sx):
            continue
        X3.append(w); y3.append(sx); g3.append(f"{run}_{arm}_ep{r['episode']}")
X3, y3 = np.array(X3), np.array(y3)
print(f"樣本 n={len(y3)}(D1.5+D2 之 closed/blind 逐步波形;依回合分組 5 摺)")
rmse3, rmse3_sd, preds3 = _ridge_cv_rmse(X3, y3, np.array(g3))
ss_res = float(np.nansum((preds3 - y3) ** 2))
ss_tot = float(np.sum((y3 - y3.mean()) ** 2))
r2 = 1 - ss_res / ss_tot
print(f"分組交叉驗證:R² = {r2:.4f},RMSE = {rmse3*100:.2f} cm(位置範圍 {y3.min():.2f}–{y3.max():.2f} m)")
print("(詮釋上限:波形編碼的是「感測器—場景相對構型」;本回歸含目標位置變異,")
print(" 不宣稱純自體感知——該分離實驗列為後續。)")
report["E3"] = {"n": int(len(y3)), "r2": r2, "rmse_cm": rmse3 * 100}

with (OUT / "ml_stage3_report.json").open("w") as f:
    json.dump(report, f, indent=1, ensure_ascii=False)
print(f"\n-> {OUT/'ml_stage3_report.json'}")
