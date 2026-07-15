#!/usr/bin/env python3
"""二維夾取誤差預算計算(閘門一,離線,零 GPU)— 決定 2D 夾取路線生死的第一關。

═══ 預註冊設計(先於執行寫定)═══

問題:D2 現行幾何(基線 0.30 m、5 視點)之側向定位 RMSE 3.3 cm,大於夾爪
  物理捕捉窗 ±1.5 cm,故二維夾取未執行。本計算回答:什麼幾何(基線 B ×
  視點數 N × 掃描線位置 × 滑動窗口)可將側向 RMSE 壓入 1.5 cm?該幾何
  之方位角是否仍在已驗證之偵測角域內?

資料(全部既有,不產生新模擬):
  v2_d2v2_formal closed+blind 之 vantage+approach 逐步量測(range_est vs
  真實 3D 距離之殘差池,含量化結構;分相位、分方位角刻畫)。

方法:
  1. 經驗殘差池:ε = range_est − true3D(sensor/target 已知);按方位角
     |atan2(Δy,Δx)| 分箱檢查殘差是否隨角度增長(外推合法性檢核)。
  2. 錨定:以殘差 bootstrap + 最小平方圓交會(與管線同式)蒙地卡羅重演
     現行幾何(B=0.30,N=5,scan_x=0.60),預測值須落於實測 3.3 cm 之
     ±25% 帶(2.5–4.1 cm),否則模型不得外推、本計算作廢。
  3. 幾何掃描(每配置 500 個 MC 目標,seed 0,目標 x∈[1.00,1.15](r3
     走廊)、y∈±0.15):B ∈ {0.30,0.45,0.60,0.75,0.90} × N ∈ {5,9,13} ×
     scan_x ∈ {0.60,0.50};滑動窗口變體=B0.30/N5 掃描後沿接近路徑補
     4 個順路視點(x 0.65–0.80,此為管線既有行為之重組,approach 相位
     殘差已實證存在於數據中)。
  4. 角域裁決:已驗證角域 = D2 實測數據中出現過的最大方位角(逐條計算,
     約 35–36°);配置之最大方位角超出者標記「需 g2 探針驗證」。

判準(先寫,三選一):
  可行     :存在配置側向 RMSE ≤ 1.5 cm 且最大方位角 ≤ 已驗證角域。
  有條件可行:僅存在需角域外推之配置達 ≤ 1.5 cm → 閘門二(g2 探針)
             之首要任務即為驗證該角域之偵測與測距。
  不可行   :全部配置(含滑動窗口)皆 > 1.5 cm → 2D 夾取就地終止,
             論文未來工作寫法不變。

誠實邊界(照錄):殘差 bootstrap 假設誤差跨視點獨立(量化誤差實為幾何
  確定,錨定檢核部分吸收此近似);角域外推之偵測性由本計算標記、不由
  本計算宣稱;可達性(IK)僅以幾何粗篩,正式判定屬 g2 探針。

模型修訂 v2(2026-07-12,錨定失效後之歸因修正——完整保留失效紀錄):
  v1 iid 殘差模型被錨定檢核否決(預測 11.8 cm >> 實測 3.3 cm,report.json
  之 anchor_v1 保留)。歸因:殘差含 −2.5 cm 系統性偏置(校正尺度誤差),
  屬「同回合共模」成分——圓交會之側向解僅依賴視點間距離差,共模誤差
  大幅相消;iid 抽樣錯誤地把共模當獨立噪聲。修正:兩成分模型——
  ε = c_ep(回合共模,自各回合 vantage 殘差均值之經驗分佈抽樣)
      + δ(視點獨立偏差,自去共模後之殘差池 bootstrap;vantage 與
        approach 相位分池)。錨定以同一接受帶重測,不放寬。

輸出:runtime/outputs/d2v2_error_budget_v1/(configs.csv + report.json)
Usage: python3 scripts/d2v2_error_budget.py
"""
from __future__ import annotations

import csv
import json
import math
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "runtime" / "outputs" / "d2v2_error_budget_v1"
OUT.mkdir(parents=True, exist_ok=True)
Z_OFF = 0.19
CAPTURE_CM = 1.5
N_MC = 500
TARGET_X = (1.00, 1.15)   # r3 走廊(夾取脈絡)
TARGET_Y = (-0.15, 0.15)
OBSERVED_LATERAL_RMSE_CM = 3.3
ANCHOR_BAND_CM = (2.5, 4.1)

# ── 1. 經驗殘差池(按回合分相位收集)──
ep_data: dict = {}
for arm in ("closed", "blind"):
    d = ROOT / "runtime/outputs/v2_d2v2_formal" / arm
    eps = {r["episode"]: (float(r["target_x"]), float(r["target_y"]))
           for r in csv.DictReader((d / "episodes.csv").open())}
    for r in csv.DictReader((d / "steps.csv").open()):
        est = float(r["range_est"])
        if not math.isfinite(est):
            continue
        tx, ty = eps[r["episode"]]
        sx, sy = float(r["sensor_x"]), float(r["sensor_y"])
        dx, dy = tx - sx, ty - sy
        true3d = math.sqrt(dx * dx + dy * dy + Z_OFF * Z_OFF)
        key = f"{arm}_{r['episode']}"
        ep_data.setdefault(key, {"vantage": [], "approach": [], "bearing": []})
        ep_data[key][r["phase"]].append(est - true3d)
        ep_data[key]["bearing"].append(abs(math.degrees(math.atan2(dy, dx))))

commons, dev_vant, dev_appr, resid_all, bearing_all = [], [], [], [], []
for key, d in ep_data.items():
    if len(d["vantage"]) < 2:
        continue
    c = float(np.mean(d["vantage"]))
    commons.append(c)
    dev_vant.extend(v - c for v in d["vantage"])
    dev_appr.extend(a - c for a in d["approach"])
    resid_all.extend(d["vantage"] + d["approach"])
    bearing_all.extend(d["bearing"])
commons, dev_vant, dev_appr = np.array(commons), np.array(dev_vant), np.array(dev_appr)
resid, bearing = np.array(resid_all), np.array(bearing_all)
print(f"兩成分分解:回合共模 c_ep std={commons.std()*100:.2f} cm(bias {commons.mean()*100:+.2f});"
      f"視點偏差 δ_vant std={dev_vant.std()*100:.2f} cm(n={len(dev_vant)});"
      f"δ_appr std={dev_appr.std()*100:.2f} cm(n={len(dev_appr)})")
max_validated_deg = float(bearing.max())
print(f"殘差池 n={len(resid)}(vantage+approach,closed+blind);"
      f"RMSE={np.sqrt(np.mean(resid**2))*100:.2f} cm,bias={resid.mean()*100:+.2f} cm")
print(f"已驗證最大方位角 = {max_validated_deg:.1f}°")
print("殘差 |ε| 按方位角分箱(外推合法性檢核):")
bins = [(0, 10), (10, 20), (20, 30), (30, 40)]
bin_stats = []
for lo, hi in bins:
    m = (bearing >= lo) & (bearing < hi)
    if m.sum() == 0:
        continue
    s = float(np.sqrt(np.mean(resid[m] ** 2))) * 100
    bin_stats.append({"bin_deg": f"{lo}-{hi}", "n": int(m.sum()), "rmse_cm": s})
    print(f"  {lo:>2}–{hi}° : n={m.sum():>3}  RMSE={s:5.2f} cm")

rng = np.random.default_rng(0)


def trilat(vx, vy, r3d):
    """圓交會:逐行移植 d2v2_formal_runner._trilat_solve(高斯-牛頓 25 迭代),
    含其初始猜測 x0 = mean(vx) + mean(h)、y0 = 0(共線視點下線性化退化,必須用非線性解)。"""
    rh = np.sqrt(np.maximum(r3d ** 2 - Z_OFF ** 2, 1e-6))
    x, y = float(vx.mean() + rh.mean()), 0.0
    for _ in range(25):
        dx, dy = x - vx, y - vy
        d = np.sqrt(dx * dx + dy * dy)
        m = d > 1e-9
        r = d[m] - rh[m]
        gx, gy = dx[m] / d[m], dy[m] / d[m]
        JtJ = np.array([[np.sum(gx * gx), np.sum(gx * gy)],
                        [np.sum(gx * gy), np.sum(gy * gy)]])
        Jtr = np.array([np.sum(gx * r), np.sum(gy * r)])
        if abs(np.linalg.det(JtJ)) < 1e-12:
            break
        step = np.linalg.solve(JtJ, Jtr)
        x -= float(step[0]); y -= float(step[1])
        if abs(step[0]) + abs(step[1]) < 1e-7:
            break
    return x, y


def mc_config(vantage_fn, label):
    """vantage_fn(tx,ty) → (vx[],vy[],n_scan);回傳側向/縱向 RMSE 與最大方位角。
    誤差模型 v2:每回合抽一共模 c_ep;前 n_scan 個視點加 δ_vant、其餘加 δ_appr。"""
    errs_y, errs_x, max_brg = [], [], 0.0
    for _ in range(N_MC):
        tx = rng.uniform(*TARGET_X); ty = rng.uniform(*TARGET_Y)
        vx, vy, n_scan = vantage_fn(tx, ty)
        dxy = np.degrees(np.arctan2(np.abs(ty - vy), tx - vx))
        max_brg = max(max_brg, float(dxy.max()))
        true3d = np.sqrt((tx - vx) ** 2 + (ty - vy) ** 2 + Z_OFF ** 2)
        c = rng.choice(commons)
        dev = np.concatenate([rng.choice(dev_vant, size=n_scan),
                              rng.choice(dev_appr, size=len(vx) - n_scan)
                              if len(vx) > n_scan else np.empty(0)])
        xh, yh = trilat(vx, vy, true3d + c + dev)
        errs_x.append(xh - tx); errs_y.append(yh - ty)
    return (float(np.sqrt(np.mean(np.array(errs_y) ** 2))) * 100,
            float(np.sqrt(np.mean(np.array(errs_x) ** 2))) * 100, max_brg)


# ── 2. 錨定:現行幾何 ──
def lateral_scan(B, N, scan_x):
    ys = np.linspace(-B / 2, B / 2, N)
    return lambda tx, ty: (np.full(N, scan_x), ys, N)


anchor_cm, _, _ = mc_config(lateral_scan(0.30, 5, 0.60), "anchor")
lat_cm = anchor_cm
anchor_ok = ANCHOR_BAND_CM[0] <= lat_cm <= ANCHOR_BAND_CM[1]
print(f"錨定:MC 預測現行幾何側向 RMSE = {lat_cm:.2f} cm(實測 {OBSERVED_LATERAL_RMSE_CM}"
      f",接受帶 {ANCHOR_BAND_CM})→ {'通過,模型可外推' if anchor_ok else '不通過,本計算作廢'}")
if not anchor_ok:
    json.dump({"anchor_failed": True, "predicted_cm": lat_cm},
              (OUT / "report.json").open("w"), ensure_ascii=False, indent=2)
    raise SystemExit(1)

# ── 3. 幾何掃描 ──
rows = []
for scan_x in (0.60, 0.50):
    for B in (0.30, 0.45, 0.60, 0.75, 0.90):
        for N in (5, 9, 13):
            lat, lon, mb = mc_config(lateral_scan(B, N, scan_x), f"B{B}N{N}x{scan_x}")
            rows.append({"config": f"scan_x={scan_x} B={B} N={N}", "lateral_rmse_cm": lat,
                         "x_rmse_cm": lon, "max_bearing_deg": mb,
                         "within_validated_bearing": mb <= max_validated_deg + 0.5,
                         "meets_capture": lat <= CAPTURE_CM})


def sliding(tx, ty):
    """B0.30/N5 掃描 + 沿接近路徑 4 順路視點(向真目標方向之近似路徑)。"""
    vx = [0.60] * 5; vy = list(np.linspace(-0.15, 0.15, 5))
    for ax in (0.65, 0.70, 0.75, 0.80):
        t = (ax - 0.60) / (tx - 0.60)
        vx.append(ax); vy.append(0.0 + t * (ty - 0.0))
    return np.array(vx), np.array(vy), 5


lat, lon, mb = mc_config(sliding, "sliding")
rows.append({"config": "sliding: B=0.30 N=5 + 4 approach vantages", "lateral_rmse_cm": lat,
             "x_rmse_cm": lon, "max_bearing_deg": mb,
             "within_validated_bearing": mb <= max_validated_deg + 0.5,
             "meets_capture": lat <= CAPTURE_CM})

print(f"\n{'配置':<38}{'側向RMSE':>9}{'縱向':>7}{'最大方位角':>9}{'角域內':>5}{'≤1.5cm':>7}")
for r in rows:
    print(f"{r['config']:<40}{r['lateral_rmse_cm']:7.2f}cm{r['x_rmse_cm']:5.2f}cm"
          f"{r['max_bearing_deg']:8.1f}°{'  ✓' if r['within_validated_bearing'] else '  ✗':>6}"
          f"{'  ✓' if r['meets_capture'] else '  —':>7}")

# ── 4. 裁決(先寫之三選一)──
ok_validated = [r for r in rows if r["meets_capture"] and r["within_validated_bearing"]]
ok_any = [r for r in rows if r["meets_capture"]]
if ok_validated:
    verdict = "可行"
    best = min(ok_validated, key=lambda r: r["lateral_rmse_cm"])
elif ok_any:
    verdict = "有條件可行(需 g2 探針驗證角域外推)"
    best = min(ok_any, key=lambda r: (r["max_bearing_deg"], r["lateral_rmse_cm"]))
else:
    verdict = "不可行"
    best = min(rows, key=lambda r: r["lateral_rmse_cm"])
print(f"\n裁決:{verdict}")
print(f"代表配置:{best['config']} → 側向 {best['lateral_rmse_cm']:.2f} cm,"
      f"最大方位角 {best['max_bearing_deg']:.1f}°(已驗證角域 {max_validated_deg:.1f}°)")
honesty = ("殘差 bootstrap 假設跨視點獨立(錨定檢核吸收近似);角域外推之偵測性"
           "由 g2 探針判定;IK 可達性未在本計算判定。")
print(f"誠實邊界:{honesty}")

with (OUT / "configs.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
json.dump({"n_resid": int(len(resid)), "resid_rmse_cm": float(np.sqrt(np.mean(resid**2)))*100,
           "bearing_bins": bin_stats, "max_validated_bearing_deg": max_validated_deg,
           "anchor_v1_iid_cm_rejected": 11.81,
           "anchor": {"predicted_cm": anchor_cm, "observed_cm": OBSERVED_LATERAL_RMSE_CM,
                      "band_cm": ANCHOR_BAND_CM, "ok": anchor_ok},
           "configs": rows, "verdict": verdict, "best": best, "honesty": honesty},
          (OUT / "report.json").open("w"), ensure_ascii=False, indent=2)
print(f"→ {OUT}/configs.csv, report.json")
