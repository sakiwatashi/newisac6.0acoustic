#!/usr/bin/env python3
"""E1 延伸:非線性小模型(MLP)對照 — 回應「E1 只比線性模型是打稻草人」之審查質疑。

═══ 預註冊設計(先於執行寫定)═══

背景:ml_stage3_suite.py 之 E1 預註冊刻意只用線性 Ridge(理由見該檔 header:
  樣本量、可歸因性、確定性資料)。其結論「解析法完勝波形 Ridge」隱含之機制解釋為
  「argmax(飛行時間萃取)本質非線性,線性模型無法表達」——此解釋若成立,
  一個具非線性容量的小模型應能縮小差距。本延伸直接檢驗此推論,不推翻原預註冊,
  而是在其旁邊加一個非線性對照臂。

資料:與 suite E1 完全相同(S2 distance_p1+tableh + D2 formal 兩臂 vantage 波形;
  載入代碼逐行照抄以保證同一性),同一分組鍵、同一 GroupKFold 5 摺。
模型:sklearn MLPRegressor,單隱藏層 64 神經元、ReLU、adam、max_iter=4000、
  random_state=0(確定性)。X 逐特徵標準化、y 標準化(均只以訓練摺擬合)。
  唯一自由超參數 = L2 正則 alpha ∈ {1e-4,1e-3,1e-2,1e-1},
  於訓練摺內以 3 摺分組交叉驗證選定(延續 suite「交由資料決定,不手調」紀律)。
對照:同摺解析法(峰值×當摺自校迴歸)與同摺波形 Ridge(與 suite 相同設定)。

判準(先寫):以 5 摺平均 RMSE 比較 MLP 與解析法——
  MLP < 解析×0.9   → 波形含峰值位置以外之可用距離資訊;E1 原結論需修正。
  介於 0.9–1.25 倍 → MLP 追平解析法;「非線性即可恢復」成立,
                     但解析特徵仍以極少參數達同等效果,E1 教學結論保留並補註。
  MLP ≥ 解析×1.25  → 非線性小模型亦不敵;E1 負結果升級(不再是僅對線性之宣稱)。
誠實邊界:n 僅數百、單一架構;本延伸只能回答「此樣本量下的小 MLP」,
  不能排除更大資料/更大模型之可能——無論結果為何,此句照錄入報告。

輸出:runtime/outputs/ml_stage3/e1_mlp_ext/report.json(新目錄,不覆寫 suite 輸出)
Usage: python3 scripts/ml_stage3_e1_mlp_ext.py
"""
from __future__ import annotations

import csv
import json
import math
import pathlib

import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "runtime" / "outputs" / "ml_stage3" / "e1_mlp_ext"
OUT.mkdir(parents=True, exist_ok=True)
ALPHAS = np.logspace(-4, 2, 7)
MLP_ALPHAS = (1e-4, 1e-3, 1e-2, 1e-1)
WF_LEN = 320


def _load_wf(path: pathlib.Path) -> np.ndarray | None:
    try:
        w = np.load(path)
        if w.size < WF_LEN:
            return None
        return np.asarray(w[:WF_LEN], dtype=float)
    except Exception:
        return None


# ── 資料載入:逐行同 ml_stage3_suite.py E1(同一性保證)──
X1, y1, pk1, g1 = [], [], [], []
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
        g1.append(f"{arm}_ep{r['episode']}")
X1, y1, pk1, g1 = np.array(X1), np.array(y1), np.array(pk1), np.array(g1)
print(f"樣本 n={len(y1)},距離範圍 {y1.min():.2f}–{y1.max():.2f} m(與 suite E1 相同)")

gkf = GroupKFold(n_splits=5)
an_errs, ridge_errs, mlp_errs, mlp_alpha_picked = [], [], [], []
for tr, te in gkf.split(X1, y1, g1):
    # 解析法(同 suite)
    A = np.vstack([pk1[tr], np.ones(len(tr))]).T
    coef, *_ = np.linalg.lstsq(A, y1[tr], rcond=None)
    an_errs.append(float(np.sqrt(np.mean((pk1[te] * coef[0] + coef[1] - y1[te]) ** 2))))
    # Ridge(同 suite)
    sc = StandardScaler().fit(X1[tr])
    m = RidgeCV(alphas=ALPHAS).fit(sc.transform(X1[tr]), y1[tr])
    ridge_errs.append(float(np.sqrt(np.mean((m.predict(sc.transform(X1[te])) - y1[te]) ** 2))))
    # MLP:內層 3 摺分組 CV 選 alpha,y 標準化
    ysc = StandardScaler().fit(y1[tr].reshape(-1, 1))
    ytr = ysc.transform(y1[tr].reshape(-1, 1)).ravel()
    inner = GroupKFold(n_splits=3)
    best_alpha, best_rmse = None, np.inf
    for a in MLP_ALPHAS:
        errs = []
        for itr, ite in inner.split(X1[tr], ytr, g1[tr]):
            isc = StandardScaler().fit(X1[tr][itr])
            mm = MLPRegressor(hidden_layer_sizes=(64,), alpha=a, max_iter=4000,
                              random_state=0).fit(isc.transform(X1[tr][itr]), ytr[itr])
            p = mm.predict(isc.transform(X1[tr][ite]))
            errs.append(float(np.sqrt(np.mean((p - ytr[ite]) ** 2))))
        if np.mean(errs) < best_rmse:
            best_rmse, best_alpha = float(np.mean(errs)), a
    mlp_alpha_picked.append(best_alpha)
    mm = MLPRegressor(hidden_layer_sizes=(64,), alpha=best_alpha, max_iter=4000,
                      random_state=0).fit(sc.transform(X1[tr]), ytr)
    p = ysc.inverse_transform(mm.predict(sc.transform(X1[te])).reshape(-1, 1)).ravel()
    mlp_errs.append(float(np.sqrt(np.mean((p - y1[te]) ** 2))))

rmse_an = float(np.mean(an_errs))
rmse_ridge = float(np.mean(ridge_errs))
rmse_mlp = float(np.mean(mlp_errs))
print(f"解析法(峰值×當摺自校): RMSE = {rmse_an*100:.2f} ± {np.std(an_errs)*100:.2f} cm")
print(f"波形 Ridge(320 維):    RMSE = {rmse_ridge*100:.2f} ± {np.std(ridge_errs)*100:.2f} cm")
print(f"波形 MLP(64 隱藏元):   RMSE = {rmse_mlp*100:.2f} ± {np.std(mlp_errs)*100:.2f} cm"
      f"(各摺 alpha={mlp_alpha_picked})")

if rmse_mlp < rmse_an * 0.9:
    verdict = "MLP 優於解析法——波形含峰值位置以外之距離資訊,E1 原結論需修正"
elif rmse_mlp < rmse_an * 1.25:
    verdict = "MLP 追平解析法——非線性容量即可恢復飛行時間資訊,惟解析特徵以 2 參數達同等效果,E1 教學結論保留並補註"
else:
    verdict = "非線性小模型亦不敵解析法——E1 負結果升級,不再僅是對線性模型之宣稱"
print(f"判準裁定:{verdict}")
honesty = "誠實邊界:n 僅數百、單一 MLP 架構;本結論限於此樣本量下之小模型,不排除更大資料/模型之可能。"
print(honesty)

json.dump({"n": int(len(y1)),
           "rmse_analytic_cm": rmse_an * 100, "rmse_ridge_cm": rmse_ridge * 100,
           "rmse_mlp_cm": rmse_mlp * 100,
           "per_fold_mlp_cm": [e * 100 for e in mlp_errs],
           "mlp_alpha_per_fold": mlp_alpha_picked,
           "verdict": verdict, "honesty": honesty},
          (OUT / "report.json").open("w"), ensure_ascii=False, indent=2)
print(f"→ {OUT/'report.json'}")
