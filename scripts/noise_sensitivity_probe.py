#!/usr/bin/env python3
"""噪聲敏感度探針(層一,離線,零 GPU)— 回應「確定性理想條件」之審查質疑。

═══ 預註冊設計(先於執行寫定)═══

問題:解析測距鏈(波形 argmax 峰值 → 當摺自校迴歸 → 距離)對量測噪聲的
  耐受邊界在哪裡?本探針給出「注入噪聲強度 vs 測距 RMSE」退化曲線。

資料:與 ml_stage3_suite E1 完全相同之 340 條已落盤波形
  (S2 distance_p1+tableh + D2 formal 兩臂 vantage;載入代碼逐行照抄),
  同一分組鍵、同一 GroupKFold 5 摺。不產生任何新模擬數據。

方法:對每一條波形注入加性高斯噪聲,噪聲標準差以該波形峰值振幅定義:
  σ = peak_amp / 10^(SNR_dB/20),SNR_dB ∈ {40,30,20,14,10,6,3,0}。
  峰值索引一律以注入後波形之 argmax 重取(校正摺與測試摺同受噪聲——
  模擬「整條管線都在噪聲下」而非只有測試段);每一噪聲等級以
  10 個固定種子(0–9)重複,報告 5 摺 RMSE 之跨種子平均±標準差。
  基線(不注入)同樣以 argmax 重取峰值,應重現 E1 解析法 ≈1.93 cm(同一性檢核)。

摘要統計(先寫,避免事後挑點):
  S_knee = 最低 SNR_dB 使 RMSE ≤ 2×基線(退化拐點);
  S_task = 最低 SNR_dB 使 RMSE ≤ 5 cm(任務尺度:低於開環臂誤差
           平均 6.2 cm,即閉環在此噪聲下仍優於無感測基線之誤差量級)。

誠實邊界(無論結果如何照錄):
  (1) 加性高斯噪聲不等於真實超聲失效模式(多徑、鏡面丟失、溫度漂移、串擾),
      本探針只回答「對估距抖動之耐受」,不構成任何模擬到實機之轉移宣稱。
  (2) 管線實際量測為 24 影格平均;本探針之噪聲應詮釋為「平均後殘餘噪聲」,
      對單影格噪聲之耐受另高約 √24 倍,不在本探針宣稱範圍。
  (3) 本探針為 appendix 級特性量測,無通過/不通過閘門,只有先寫定之報告格式。

輸出:runtime/outputs/noise_sensitivity_v1/(curve.csv + report.json)
Usage: python3 scripts/noise_sensitivity_probe.py
"""
from __future__ import annotations

import csv
import json
import math
import pathlib

import numpy as np
from sklearn.model_selection import GroupKFold

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "runtime" / "outputs" / "noise_sensitivity_v1"
OUT.mkdir(parents=True, exist_ok=True)
WF_LEN = 320
SNR_DB_SWEEP = (40, 30, 20, 14, 10, 6, 3, 0)
N_SEEDS = 10


def _load_wf(path: pathlib.Path) -> np.ndarray | None:
    try:
        w = np.load(path)
        if w.size < WF_LEN:
            return None
        return np.asarray(w[:WF_LEN], dtype=float)
    except Exception:
        return None


# ── 資料載入:逐行同 ml_stage3_suite.py E1(同一性保證)──
X1, y1, g1 = [], [], []
for sub, note in (("distance_p1", "boresight"), ("distance_tableh", "tableh")):
    d = ROOT / "runtime/outputs/v2_s2_datasheet" / sub
    for r in csv.DictReader((d / "points.csv").open()):
        w = _load_wf(d / "waveforms" / f"{r['waveform_tag']}_primary.npy")
        td = float(r["true_distance_3d_m"])
        if w is None or not math.isfinite(td):
            continue
        X1.append(w); y1.append(td)
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
        g1.append(f"{arm}_ep{r['episode']}")
X1, y1, g1 = np.array(X1), np.array(y1), np.array(g1)
peak_amp = np.abs(X1).max(axis=1)
print(f"樣本 n={len(y1)},距離範圍 {y1.min():.2f}–{y1.max():.2f} m(與 E1 相同)")


def analytic_rmse(pk: np.ndarray) -> float:
    """5 摺分組 CV:各摺以訓練摺擬合 peak→dist 直線(同 suite E1 解析臂)。"""
    gkf = GroupKFold(n_splits=5)
    errs = []
    for tr, te in gkf.split(pk.reshape(-1, 1), y1, g1):
        A = np.vstack([pk[tr], np.ones(len(tr))]).T
        coef, *_ = np.linalg.lstsq(A, y1[tr], rcond=None)
        errs.append(float(np.sqrt(np.mean((pk[te] * coef[0] + coef[1] - y1[te]) ** 2))))
    return float(np.mean(errs))


baseline = analytic_rmse(np.argmax(X1, axis=1).astype(float))
print(f"基線(無注入,argmax 重取): RMSE = {baseline*100:.2f} cm(E1 同一性檢核,預期 ≈1.93)")

rows = []
for snr_db in SNR_DB_SWEEP:
    sigma = peak_amp / (10 ** (snr_db / 20))
    per_seed = []
    for seed in range(N_SEEDS):
        rng = np.random.default_rng(seed)
        Xn = X1 + rng.standard_normal(X1.shape) * sigma[:, None]
        per_seed.append(analytic_rmse(np.argmax(Xn, axis=1).astype(float)))
    m, s = float(np.mean(per_seed)), float(np.std(per_seed))
    rows.append({"snr_db": snr_db, "rmse_cm_mean": m * 100, "rmse_cm_sd": s * 100})
    print(f"SNR {snr_db:>3} dB → RMSE = {m*100:6.2f} ± {s*100:5.2f} cm")

s_knee = min((r["snr_db"] for r in rows if r["rmse_cm_mean"] <= 2 * baseline * 100), default=None)
s_task = min((r["snr_db"] for r in rows if r["rmse_cm_mean"] <= 5.0), default=None)
print(f"S_knee(RMSE ≤ 2×基線 {2*baseline*100:.1f} cm 之最低 SNR)= {s_knee} dB")
print(f"S_task(RMSE ≤ 5 cm 之最低 SNR)= {s_task} dB")
honesty = ("加性高斯噪聲不代表真實失效模式;僅宣稱估距抖動耐受,非模擬到實機轉移;"
           "噪聲詮釋為 24 影格平均後之殘餘噪聲。")
print(f"誠實邊界:{honesty}")

with (OUT / "curve.csv").open("w", newline="") as f:
    wcsv = csv.DictWriter(f, fieldnames=["snr_db", "rmse_cm_mean", "rmse_cm_sd"])
    wcsv.writeheader(); wcsv.writerows(rows)
json.dump({"n": int(len(y1)), "baseline_rmse_cm": baseline * 100,
           "snr_db_sweep": list(SNR_DB_SWEEP), "n_seeds": N_SEEDS,
           "curve": rows, "S_knee_db": s_knee, "S_task_db": s_task,
           "honesty": honesty},
          (OUT / "report.json").open("w"), ensure_ascii=False, indent=2)
print(f"→ {OUT}/curve.csv, report.json")
