# 正典狀態（Canonical Status）

> 新讀者先看本頁。研究日誌見 `docs/plan_v2/PROGRESS.md`；舊管線交接見 `docs/handoff/`（**不支撐論文主結論**）。

**最後更新**: 2026-07-13（WPM 1.1 文案：自校正典 + 前伸掛載表述）  
**公開倉庫**: https://github.com/sakiwatashi/isaacsimacousticfinal （對版本請用 commit SHA，勿只看 HTML 快取）  
**本機完整工作樹**: 含論文 `thesis/`（口試前不上公開倉）

## 一句話

在 Isaac Sim 6.0 RTX Acoustic 中，以包絡優先 + 三臂消融 + 預註冊判準，完成 S1→S2→D1→D1.5→D3→D2 全鏈；**實驗判準全綠**，主限制為單 seed、確定性引擎、非摩擦夾持、無實機。

## 一鍵驗證

```bash
bash runtime/verify_all.sh   # 零 GPU；exit 0 = 全部當場重算通過
```

腳本可攜（相對自身定位 repo root），失敗累計後 **exit 1**。

## 正式實驗正典表

| 實驗 | 正典資料目錄 | 主結果 | 判準 | 論文 |
|------|--------------|--------|------|------|
| S1 包絡 | `runtime/outputs/v2_s1_envelope/` | 36/52 可偵測；指向主宰 | 止損未觸發 | §4.1 |
| S2 特性 | `runtime/outputs/v2_s2_datasheet/` | 測距 r=0.9994；側向證偽 | 側向 False=預定 | §4.2–4.3 |
| D1 飛行 | `runtime/outputs/v2_d1_approach/` | r=0.9970, RMSE 2.5 cm | 3/3 | §5.1 |
| D1.5 手臂（主結果） | `runtime/outputs/v2_d15_arm_approach/` | r=0.9856, RMSE 2.8 cm | 4/4 | §5.2 |
| D3 夾取 **r3（正典）** | `runtime/outputs/v2_d3_grasp_r3/` | 對位 80% vs 33%；零違規 | **4/4** | §5.3 |
| D3 首輪（歷史失效） | `runtime/outputs/v2_d3_grasp/` | 60% vs 23%；3/90 升舉 IK | 3/4（如實） | §5.3 複驗段 |
| D3 r2（歷史） | `runtime/outputs/v2_d3_grasp_r2/` | 1.18 m 走廊仍 1/90 | 中間輪 | 報告 |
| D2 二維 | `runtime/outputs/v2_d2v2_formal/` | 側向 r=0.950；2D stop RMSE 1.9 cm | 4/4 | §5.4 |
| 側向四重證偽 | `rxgroup_probe_v1/` 等 | 全證偽 | 負結果 | §4.3 |

詳見 `runtime/outputs/MANIFEST.md`。

## 重跑 D3 注意

```bash
# 正典（預設走廊 1.00–1.15）→ 新目錄
./app/python.sh scripts/d3_grasp_runner.py --mode closed \
  --output-dir runtime/outputs/v2_d3_grasp_NEW --target-x-max 1.15

# 重現首輪失效（1.20）→ 必須新目錄
./app/python.sh scripts/d3_grasp_runner.py --mode closed \
  --output-dir runtime/outputs/v2_d3_grasp_repro_r1 --target-x-max 1.20
```

## 已知方法精煉（不推翻結果）

- 三臂同 seed 為配對設計；預註冊主檢定仍為 Welch / Fisher。
- Analyzer **已附**成對佐證（非待辦）：D2 配對置換 p、D3 McNemar exact（裁定閾值不變）。
- Welch p 在 `analyze_d2v2` 為 erfc 常態近似；效應量極大，結論不翻。
- `docs/WPM_EXPERIMENT_RULES.md` v1.1：禁止固定 T_US；手臂「掩蓋」改為「近貼腕載／前伸可恢復」。

## 刻意不做 / 口試邊界

- 論文全文不上公開倉（口試前）。
- 無跨 seed 正式表、無實機 CH201、無摩擦夾持宣稱、無 0.32 m 內閉環。
- 2D 再夾取：g2-wide 側向 RMSE 1.84 cm > 1.5 cm 預註冊止損（見 `v2_d2v2_probe_wide/`）。

## 待收尾（非實驗重跑）

見外部審查分類：結果圖入論文、D2 獨立報告、LICENSE/CITATION、PDF metadata、誌謝等。
