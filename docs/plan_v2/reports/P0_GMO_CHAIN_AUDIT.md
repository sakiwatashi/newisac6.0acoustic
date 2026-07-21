# P0 審計：GMO → 回波序列 → 峰值 → 距離

**日期**: 2026-07-22  
**性質**: 感測資料鏈核對（非閉環、非論文修辭）  
**離線重算**: `python3 scripts/p0_gmo_chain_offline_audit.py`（零 GPU）  
**產物**: `runtime/outputs/p0_gmo_chain_audit/{metrics.json,figures/}`  
**論證閘門**: 3.1 定稿前須滿足本報告 + `THESIS_ARGUMENTATION_GATES.md` G3（P0 特則）

---

## 一句話結論

在本 repo 的 Isaac Sim 6.0 RTX Acoustic 配置下，GMO 的 `scalar` 是 **signal way（TX→RX→channel）上的離散振幅序列**，時間格對應引擎 **`sampleDuration`（schema 預設 102.4 µs）**，不是 40 kHz 載波 ADC 流。V2 正典 **不串接** 多條 way，而是切開後取 **primary（峰較高者）**；峰值索引 \(k\) 在 S1 隨目標出現／距離移動，移除目標後不再同軌；S2 上 \(k\) 與真距 OLS \(r\approx 0.9994\)，斜率與 \(2/(c\cdot T_{\mathrm{schema}})\) 相對差 **&lt;1%**。閉環距離使用 **經驗映射** \(\hat d=(k-b)/a\)，不以裸 \(c\Delta t/2\) 當物理真值。

**離線閘門**: `all_offline_gates_pass: true`（見 `metrics.json`）。

---

## 官方語意（文件來源）

| 項目 | 官方定義 | 來源 |
|------|----------|------|
| Signal way | 某一 TX 到某一 RX、特定 channel 的**完整**接收波形 | `inspect_acoustic_gmo.py` docstring；`acoustic_extension.rst` «Understanding Signal Ways» |
| `scalar` | Amplitude value in sample | 同上 GMO 表 |
| `numSamplesPerSgw` | 每條 signal way 的樣本數 | USSAuxiliaryData |
| `x,y,z` | TX id / RX id / channel id | 同上 |
| `sampleDuration` | Time sampling of waveform（預設 **0.0001024 s**） | schema 表 Physical parameters |
| `centerFrequency` | 訊號中心頻率參數（預設 51200 Hz） | 同上——**不是** scalar 取樣率 |

**推論（寫進論文時必須區分「官方」與「本文操作」）**：

- 多條 way **不應**接成一條更長時間軸。  
- 40 kHz 設定與 ~10 kHz 有效樣本率並存是預期行為，不是解析 bug。

---

## 本文 V2 實際解析（程式）

| 步驟 | 行為 | 腳本 |
|------|------|------|
| 1 | 讀 `scalar` 扁平 buffer + `numSamplesPerSgw` | `s2_datasheet_runner._extract_frame` 等 |
| 2 | 切成 `n_ways = n / num_spsgw` 段，每段長 320 | 同上 |
| 3 | 本配置 id 常全為 (0,0,0) → 以 **way 序數** 當 rx0/rx1 | S2 header / S2 報告 |
| 4 | primary = 兩 way 中 |peak| 較大者 | `_measure_point` |
| 5 | 多幀平均後 `peak_idx = argmax(|mean|)` | 同上 |
| 6 | \(\hat d = (k - b)/a\)，\(a,b\) 來自同幾何 S2 OLS | `d1_*` / `d15_*` startup calib |

**誤讀更正**：外部審查所稱「切開後串成一條時間軸」**不是** V2 正典行為。

---

## P0-1：Signal way 是否可串接？

| 判準 | 結果 |
|------|------|
| 官方：way = 完整 TX–RX 波形 | **支持「不串接」** |
| 實測：rx0 與 rx1 波形 identical？ | **否**（corr ≈ 0.01–0.03） |
| 實測：peak 索引 | 差約 2–3 sample（例 point_10: 36 vs 33） |
| 每 way 長度 | 320 = `numSamplesPerSgw` |

圖：`figures/fig4_s2_dual_ways_separate.png`

**裁定**: PASS — 分路分析；串接不作正典。

---

## P0-2：scalar 是不是「40 kHz 波形」？

| 量 | 值 |
|----|-----|
| Schema `sampleDuration` | 102.4 µs（≈ 9.77 kHz） |
| S2 自校 \(T_{\mathrm{cal}}=2/(a c)\) | **103.09 µs** |
| 理論單站斜率 \(2/(cT)\) | 56.94 samples/m |
| S2 實測斜率 | 56.56 samples/m |
| 比 | **0.993** |

**裁定**: PASS — 稱為「WPM 離散振幅響應序列」；**禁止**稱 40 kHz 原始聲壓波形。

---

## P0-3：0.10 m 雙掛載與「除以二」

| 事實 | 說明 |
|------|------|
| 掛載 | m001@(0,0,0), m002@(0.10,0,0) m；rxGroup [0,1] |
| 控制公式 | \(\hat d=(k-b)/a\)（OLS），非硬編碼 \(kTc/2\) |
| 物理一致性 | 斜率≈單站 ToF 格點 → 遠場往返時間尺度正確 |
| 截距 | ≈ −4.1 sample：吸收固定延遲／雙站常數／原點定義 |
| D2 圓 vs 橢圓 | 正典用經驗距離 + 圓交會；嚴格雙站橢圓為精煉項，非目前主宣稱 |

**裁定**: PASS（控制層）— 論文必須寫「經驗映射 + 單站一致性檢查」，不得寫「已驗證物理單站真值」。

---

## P0-4：最大峰是否為目標相關峰？

### S1 配對（Block A，0.10 m，pitch=0）

| d (m) | with \(k\) | without \(k\) | SNR_peak |
|------:|----------:|--------------:|---------:|
| 0.15 | 5 | 304 | 67 |
| 0.30 | 13 | 304 | 148 |
| 0.50 | 24 | 304 | 94 |
| 0.80 | 41 | 304 | 67 |
| 1.20 | 64 | 304 | 87 |

- with：\(k\) vs \(d\)，\(r=0.9999\)  
- without：峰位固定在 304（不跟距離走）  
- 圖：`fig1_*`、`fig2_*`（0.5 m 波形對照）

### S2 距離編碼

- combined p1–p3：\(r=0.9994\)，RMSE 1.21 cm（n_kept=48）  
- 圖：`fig3_*`、`fig5_*`（多距離疊加，峰外移）

**裁定**: PASS — 在 **水平前視、可偵測包絡內**，全域 |max| 選到的峰是目標相關且可編碼距離的特徵。  
**限制**: 近場桌高 outlier、強 clutter、側視幾何下不得外推；閉環不重做 with/without，依賴 S1 包絡前置。

---

## 通過表（對外部 P0 清單）

| 要求 | 狀態 | 證據 |
|------|------|------|
| way 組合有文件或控制實驗支持 | **是** | 官方 + 雙 way 非相同 |
| 目標移動時可識別特徵規律移動 | **是** | S1/S2 峰隨 d |
| 移除目標後特徵改變 | **是** | S1 without |
| 背景主峰不誤當目標（本包絡） | **是** | without 峰離群／固定 |
| 峰值索引與距離單調穩定 | **是** | S2 r&gt;0.95 |
| 批次不任意跳變 | **是** | S2 三遍逐位同；repeat 10/10 |
| TX/RX 幾何與模型陳述一致 | **部分→已寫清** | 雙掛載 + OLS；非裸單站 |
| 側移後距離模型 | **S2 側向已證偽空間差** | 距離主峰仍用 primary；不作側向編碼 |

---

## 刻意不做／後續可選

1. **可選 GPU**：`scripts/p0_fixed_sensor_gmo_dump.py` — 固定感測器、無臂、五距離 × 有無目標、整幀 GMO 落盤（滿足「原始欄位一幀」展示）。**不否決**本離線結論。  
2. 不因本審計重跑 D1–D3。  
3. 論文 3.1：刪「待 P0」語氣，改貼 `thesis/P0_SECTION_3_1_PATCH.md`。

---

## 重現

```bash
cd /path/to/isaacsim6.0
python3 scripts/p0_gmo_chain_offline_audit.py
# exit 0 且 metrics.json adjudication.all_offline_gates_pass == true
```
