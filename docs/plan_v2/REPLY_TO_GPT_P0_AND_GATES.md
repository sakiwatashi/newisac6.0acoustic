# 回覆外部審查（GPT）— 可直接貼給對方繼續審

**日期**: 2026-07-22  
**用途**: 回覆你提出的 P0「GMO→序列→峰→距離」優先級，並說明本輪已完成項目；請依此繼續審下一節，不必重開 P0 清單除非你否決下列證據。  
**Repo**: `newisac` → https://github.com/sakiwatashi/newisac6.0acoustic.git（commit 見推送後 SHA）  
**交接入口**: `docs/HANDOFF_CURRENT.md`

---

## 給審查者的說明（建議整段貼上）

你好，感謝把最高優先級定在感測資料鏈，而不是控制器或修辭。我們已完成一輪**可重算的 P0 離線審計**，並補上「論證層」硬閘門，避免之後只過合規、不過論證。請你下一輪審查時：

1. **先讀** `docs/plan_v2/reports/P0_GMO_CHAIN_AUDIT.md` 與圖  
   `runtime/outputs/p0_gmo_chain_audit/figures/`  
2. **用** `docs/plan_v2/THESIS_ARGUMENTATION_GATES.md` 的 G0–G6 當論文文字標準（尤其 1.x / 3.1）  
3. **3.1 收斂稿**在 `thesis/P0_SECTION_3_1_PATCH.md`（尚未強制貼入正式 docx；請當工作稿審）  
4. 請從 **1.2 或 3.1（貼稿版）** 擇一繼續逐節審；P0 四問的答覆如下。

---

## 對你 P0 四問的直接答覆

### 1. Signal way 能不能串接？

**答：不能當正典串接；官方語意是「每條 way = 一條完整 TX→RX→channel 波形」。**

- NVIDIA 範例與文件：`inspect_acoustic_gmo.py`、`acoustic_extension.rst`（Understanding Signal Ways）。  
- **程式澄清（請修正先前假設）**：V2 正式管線是  
  `numSamplesPerSgw` **切開** → **分路保留** → 取 **primary（|peak| 較大者）**，  
  **並非**把多條 way 接成一條更長時間軸。  
- 實測：S2 `distance_p1` 同點 rx0/rx1 **非相同**（corr≈0.01–0.03；peak 差約 2–3 sample）。  
- 圖：`fig4_s2_dual_ways_separate.png`

### 2. scalar 是不是 40 kHz 原始波形？

**答：不是。**

- Schema `sampleDuration` 預設 **102.4 µs**（約 9.8 kHz 波形格），是「波形時間取樣」，不是對 40 kHz 載波做 Nyquist 取樣。  
- `centerFrequency`（本文 40 kHz）是 WPM 物理／脈衝參數，不是 `scalar` 的取樣率。  
- S2 自校 \(T_{\mathrm{cal}}\approx\mathbf{103.09\,\mu s}\)；斜率 56.56 samples/m vs 單站理論 \(2/(cT)=56.94\)，比 **0.993**。  
- 論文用語應為「WPM 離散振幅響應序列」，禁止稱「40 kHz 原始聲壓波形」。

### 3. 兩個掛載相距 0.10 m，為何可以除以二？

**答：正式控制不用裸 \(kTc/2\)；用同幾何 OLS \(\hat d=(k-b)/a\)。**

- 配置：m001@(0,0,0)、m002@(0.10,0,0)、rxGroup [0,1]。  
- 閉環讀的是 S2（或當輪）校正檔的 slope/intercept。  
- 斜率接近單站時間尺度 → 支持「索引隨往返時間單調」；截距吸收固定延遲／幾何常數。  
- 嚴格雙站路徑為橢圓；D2 正典用經驗距離 + 圓交會，**不宣稱**已完成橢圓模型。  
- 論文必須寫清：經驗映射 + 一致性檢查，不是未經檢驗的物理單站真值。

### 4. 全域最大峰是不是目標峰？

**答：在 S1 水平前視、可偵測包絡內，是目標相關峰（有配對移除證據）。**

| d (m) | with peak idx | without peak idx | SNR_peak |
|------:|--------------:|-----------------:|---------:|
| 0.15 | 5 | 304 | 67 |
| 0.30 | 13 | 304 | 148 |
| 0.50 | 24 | 304 | 94 |
| 0.80 | 41 | 304 | 67 |
| 1.20 | 64 | 304 | 87 |

（S1 Block A，0.10 m cube，pitch=0）

- 有目標：\(k\) vs \(d\)，\(r\approx 0.9999\)  
- 無目標：峰位固定在 304，不跟距離走  
- S2 距離編碼：\(r\approx 0.9994\)，RMSE≈1.2 cm（boresight 合併 kept）  
- 圖：`fig1`–`fig3`、`fig5`

**限制（誠實）**：近場桌高 outlier、大俯仰、強 clutter 不得外推；閉環不再做 with/without，依賴 S1 包絡前置。全域 |max| 是操作定義，不是萬能峰值分類器。

---

## 離線重算（審查者可要求我們再跑）

```bash
python3 scripts/p0_gmo_chain_offline_audit.py
# 期望：exit 0，metrics.json → adjudication.all_offline_gates_pass == true
```

可選 GPU 整幀 dump（非否決條件）：

```bash
bash runtime/run_p0_fixed_sensor_gmo_dump.sh
# 或 smoke：./app/python.sh scripts/p0_fixed_sensor_gmo_dump.py --smoke
```

---

## 本輪另完成：論文「論證閘門」

先前多輪修改優化的是：禁詞、引用覆蓋、數字與實驗同步、不超宣稱。  
這會造成「合規全綠，但 1.1 論證仍可被整段重寫」。

我們已新增硬閘門（之後貼正式稿也要過）：

- 文件：`docs/plan_v2/THESIS_ARGUMENTATION_GATES.md`  
- 重點：G0 節職能上限、G1 論證鏈、G2 減肥、G3 主張–證據閉環、G4 尺度、G6 章串線  
- **請你下一輪審論文時直接用此表打勾**，比只改詞藻更有效。

---

## 請你下一輪怎麼審（明確任務）

請擇一（或依序）：

**選項 A（建議）**：審 `thesis/P0_SECTION_3_1_PATCH.md`  
- 是否已關閉你提的 P0 表述風險？  
- 有無過強宣稱？缺哪句假設？  

**選項 B**：用論證閘門重審 **1.1 / 1.2**（優化整合稿或現用 docx 對應節）  
- 只評論證職能與讀者路徑，不必重開 GMO 四問（除非否決 P0 證據）。  

**選項 C**：審控制器／三臂內部效度（你列的第二優先）  
- 前提：你接受本回 P0 答覆為「暫定通過」或列出仍不通過的唯一條件。

請回覆時標明：**P0 四問各 PASS / FAIL / 有條件**，以及下一節要看的檔案路徑。

---

## 檔案清單（給對方）

| 內容 | 路徑 |
|------|------|
| P0 正式報告 | `docs/plan_v2/reports/P0_GMO_CHAIN_AUDIT.md` |
| 離線腳本 | `scripts/p0_gmo_chain_offline_audit.py` |
| 指標 JSON | `runtime/outputs/p0_gmo_chain_audit/metrics.json` |
| 圖 | `runtime/outputs/p0_gmo_chain_audit/figures/` |
| 可選 GPU dump | `scripts/p0_fixed_sensor_gmo_dump.py` |
| 3.1 可貼稿 | `thesis/P0_SECTION_3_1_PATCH.md` |
| 論證閘門 | `docs/plan_v2/THESIS_ARGUMENTATION_GATES.md` |
| 本回覆 | `docs/plan_v2/REPLY_TO_GPT_P0_AND_GATES.md` |

---

## 簡短版（聊天用，可另貼）

> P0 我們做完可重算離線審計了（報告 P0_GMO_CHAIN_AUDIT.md）。重點：① signal way 官方是 TX–RX 完整波形，V2 是切開取 primary、**不串接**；② scalar 對應 sampleDuration≈102µs，不是 40kHz 載波；③ 距離用 OLS (k−b)/a，斜率與 2/(cT) 差&lt;1%；④ S1 with/without 證明峰隨目標，S2 r≈0.9994。另補論證閘門 THESIS_ARGUMENTATION_GATES.md。請先對 P0 四問給 PASS/FAIL，再審 3.1 貼稿或 1.2。
