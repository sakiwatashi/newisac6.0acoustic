# 軸向 P0 正式關閉聲明

**日期**: 2026-07-22  
**正典 commit 目標**: 含本文件與 `p0_signedness_check.json` 之提交  
**範圍**: GMO → 分路序列 → 峰值索引 → 軸向經驗距離（S1/S2/D1/D1.5 資料前提）  
**不在本關閉範圍**: D2 圓／橢圓幾何；實機；摩擦夾持

---

## 關閉條件清單

| # | 條件 | 狀態 | 證據 |
|---|------|------|------|
| 1 | Signal way 不串接；為 TX→RX 完整波形 | **PASS** | `P0_GMO_CHAIN_AUDIT.md`；NVIDIA 文件 |
| 2 | `scalar` 非 40 kHz 載波；時間格≈`sampleDuration` | **PASS** | 同上；S2 \(T_{\mathrm{cal}}\approx 103\) µs |
| 3 | 控制用 OLS \(\hat d=(k-b)/a\)，非裸 \(kTc/2\) | **PASS** | D1/D15 runner；斜率比≈0.993 |
| 4 | 包絡內峰為目標相關 | **PASS（有界）** | S1 with/without |
| 5 | S2 排除點機制透明（能量 QC） | **PASS** | `P0_FOLLOWUP_AB.md` A |
| 6 | primary 切換透明 | **PASS** | `P0_FOLLOWUP_AB.md` B |
| 7 | **有號峰值規則與程式／CSV 一致** | **PASS** | 本文件 §Signedness |
| 8 | **論文表述 = 實際 primary，非固定 way0** | **PASS** | `thesis/P0_SECTION_3_1_PATCH.md` 修訂 |

**裁定：軸向 P0 正式關閉。**

---

## Signedness／峰值規則核對（本輪完成）

### 程式正典（V2）

```text
peak_idx     = np.argmax(wf)           # 有號最大值索引
primary_way  = argmax over ways of np.max(wf)   # 有號最大值較大者
early_energy = sum(wf[:N_EARLY]**2)    # S2：能量用平方和
```

來源：`scripts/s2_datasheet_runner.py`（`_peak_idx`、`_measure_block`）；D1/D1.5 同源。

### 正典數據重算（`runtime/outputs/p0_gmo_chain_audit/p0_signedness_check.json`）

| 檢查 | 結果 |
|------|------|
| S2 p1–p3 全部 primary/rx0/rx1 波形（180 條） | 有號 \(\arg\max\) = 絕對值 \(\arg\max\)：**180/180** |
| 負樣本比例 | **0**（全部 sample ≥ 0） |
| CSV `peak_sample_idx` vs 有號 argmax（60 primary） | **60/60 一致** |
| S1 Block A pitch=0 之 with/without/noise_ref（45 條） | 有號=絕對值：**45/45** |
| primary 選 way：有號 max vs abs max（p1 20 點） | **20/20 相同** |

**結論：**

1. 正典操作定義必須寫 **有號 `argmax`**，與程式一致。  
2. 在已落盤 S1/S2 數據上，**與 `|·|` 數值等價**（無負值），故先前用絕對值重繪的審計圖**不推翻**數字結論。  
3. 未來若出現負振幅，**不得**假設 `|·|` 仍等價；以程式有號規則為準。

---

## 表述修正（已做）

| 錯誤／易誤導 | 正典 |
|--------------|------|
| 「取絕對值最大處之 \(k\)」為唯一定義 | \(k=\arg\max s[i]\)（有號）；正典數據上與 \|·\| 重合 |
| 「正式改為固定 way0」 | **否**；正典為 primary（峰 max 較大者）；way0 固定僅對照 |
| 「陣列式接收拓樸」暗示方位陣列 | 已降級：雙掛載但無可用通道身分／側向未過 |

---

## 刻意保留的限制（寫 limitation，不擋關閉）

1. 最大峰僅在**已驗證包絡**內稱為目標相關操作特徵。  
2. S2 中段四點：能量漂移 QC 排除；peak 仍線性。  
3. primary 於 d≈0.59 m 確定性切 way1（3/60）。  
4. **D2**：經驗 \(\hat d\) + 圓交會在 0.10 m 雙掛載下是否足夠 → **下一優先級**，非軸向 P0。

---

## 下一優先級（P0 關閉後）

> 在 0.10 m 空間分離掛載下，D2 使用經驗距離做**圓**交會，其相對於雙站**橢圓**路徑模型的近似是否足以支持現有判準與誤差敘述。

入口建議：`docs/plan_v2/reports/D2_multilateration_report.md`、`scripts/d2v2_formal_runner.py`、雙掛載幾何與 \(\hat d\) 定義。

---

## 重現

```bash
# 既有離線審計
python3 scripts/p0_gmo_chain_offline_audit.py

# signedness（本輪；可併入 audit 腳本後續）
python3 -c "import json; print(json.load(open('runtime/outputs/p0_gmo_chain_audit/p0_signedness_check.json'))['adjudication'])"
```
