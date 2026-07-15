# D2 二維多點定位 — 正式裁定報告

**狀態**: 已執行、四判準全綠（primary）  
**正典資料**: `runtime/outputs/v2_d2v2_formal/`  
**Runner**: `scripts/d2v2_formal_runner.py`  
**Analyzer**: `scripts/analyze_d2v2.py`  
**設計／預註冊**: `docs/plan_v2/D2V2_DESIGN_2026-07-10.md`  
**論文對應**: §5.4  

## 1. 問題與前置

第四章側向四重證偽後，單次 GMO 輸出不含可用左右方向。D2 以**手臂運動合成多個已知視點**，各量一次距離，最小平方圓交會恢復 (x,y)。

## 2. 幾何與校正

- 側向五個量測位置，橫向基線 0.30 m。
- 距離換算沿用與 bar／桌高掛載相符之 **D3.0 合併校正**  
  `runtime/outputs/v2_d3_gates/bar_calibration.json`（當輪 slope/intercept，非固定 T_US）。
- 盲走臂：估距先置 ∞ → 定位無解／不依賴目標回波資訊。

## 3. 實驗設計

| 項目 | 設定 |
|------|------|
| 三臂 | closed / blind / open |
| 每臂回合 | 30（同 seed 配對目標） |
| 主指標 | 定位側向 r、前後 r；2D 停止 RMSE；盲走對照 |
| 稽核 | 姿態／感測器位姿 |

## 4. 預註冊判準與結果（正典 `d2_summary.json`）

| 判準 | 結果 | 值 |
|------|------|-----|
| d2_loc_y_tracking | **True** | r_y = 0.950，RMSE_y = 3.34 cm |
| d2_loc_x_tracking | **True** | r_x = 0.978，RMSE_x = 1.17 cm |
| d2_stop2d_beats_blind | **True** | closed 2D stop RMSE 1.88 cm vs blind 15.0 cm；Welch t≈−12.1 |
| d2_posture_clean | **True** | 姿態／感測器違規 0 |

成對佐證（同 seed；**不改裁定閾值**）：配對置換 p_one_sided ≈ 1e−5。

## 5. 詮釋邊界

- **可宣稱**: 在本引擎／幾何下，運動合成多點定位可恢復側向至 ~3.3 cm RMSE 量級，並支撐優於盲走之 2D 停止。
- **不可宣稱**: 單次輸出含側向；2D 誤差已進夾取窗（±1.5 cm）— g2-wide 探針側向 RMSE 1.84 cm 已依預註冊止損（`v2_d2v2_probe_wide/`）。
- 開環固定行程可有表面到達率，但不能隨目標移動（到達率陷阱，與 D1.5 同型論證）。

## 6. 重算

```bash
python3 scripts/analyze_d2v2.py --scan-dir runtime/outputs/v2_d2v2_formal
# 或
bash runtime/verify_all.sh   # 含 D2 段
```

## 7. 探針與延伸（非 primary）

| 目錄 | 角色 |
|------|------|
| `v2_d2v2_probe/` | 設計期 g2 |
| `v2_d2v2_probe_wide/` | 2D 再夾取閘門止損 |
