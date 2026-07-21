# 回覆外部審查（GPT）— 軸向 P0 關閉 + D2 圓／橢圓裁定

**日期**: 2026-07-22  
**用途**: 直接貼給 GPT 繼續審查；請依此更新先前「有條件通過」結論，勿重開已關閉項。  
**正典 remote**: `newisac` → https://github.com/sakiwatashi/newisac6.0acoustic.git  
**請核對 SHA**: **`136367a`**（完整：`136367a` 為 tip；P0 關閉 `a27b3cd`；D2 幾何 `b591de3`）

```bash
git fetch newisac && git rev-parse newisac/main
# 期望以 136367a 為 tip（或之後的後續提交）
```

---

## 請你先讀的檔案（依序）

| 優先 | 路徑 | 內容 |
|------|------|------|
| 1 | `docs/plan_v2/reports/P0_AXIAL_CLOSED.md` | **軸向 P0 正式關閉聲明** |
| 2 | `docs/plan_v2/reports/P0_FOLLOWUP_AB.md` | S2 排除點 + primary 切換 |
| 3 | `runtime/outputs/p0_gmo_chain_audit/p0_signedness_check.json` | 有號 vs \|·\| 峰值 |
| 4 | `thesis/P0_SECTION_3_1_PATCH.md` | 3.1 可貼稿（primary + 有號 argmax） |
| 5 | `docs/plan_v2/reports/D2_CIRCLE_VS_ELLIPSE.md` | **D2 圓 vs 橢圓** |
| 6 | `runtime/outputs/d2_circle_vs_ellipse/metrics.json` | D2 幾何數字 |
| 7 | `docs/plan_v2/THESIS_ARGUMENTATION_GATES.md` | 論文論證閘門（審文字用） |

離線重算：

```bash
python3 scripts/p0_gmo_chain_offline_audit.py
python3 scripts/d2_circle_vs_ellipse_offline.py
# 兩者期望 exit 0
```

---

## 一、對你先前 P0 裁定的更新請求

你上次判定：

| 項 | 你的裁定 | **現在請改為** |
|----|----------|----------------|
| Signal way 串接 | PASS | **維持 PASS（關閉）** |
| scalar ≠ 40 kHz 波形 | PASS | **維持 PASS（關閉）** |
| 雙掛載／距離公式 | 有條件 PASS | **軸向：關閉**；D2 見下文 |
| 最大峰＝目標峰 | 有條件 PASS | **包絡內關閉**（限制保留） |
| A：S2 12/60 排除 | 待補查 | **已補 → 關閉**（能量 QC，非峰失效） |
| B：primary 切換 | 待補查 | **已補 → 關閉**（3/60 於 d≈0.59 m） |
| signedness／峰值規則 | 你後來指出待做 | **已做 → 關閉** |
| 3.1 固定 way0 誤寫 | 待改回 primary | **已改 → 關閉** |

**請回覆標明：軸向 P0 = PASS 關閉 / 仍 FAIL（列唯一理由）。**

---

## 二、軸向 P0 關閉摘要（證據一句話）

### 1–2（你已 PASS）
- way = TX→RX 完整波形；V2 **切開取 primary，不串接**。  
- `scalar` 時間格 ≈ `sampleDuration` 102.4 µs；≠ 40 kHz 載波。

### 3 距離公式
- 控制：\(\hat d=(k-b)/a\)（OLS），非裸 \(kTc/2\)。  
- 斜率與 \(2/(cT)\) 比 ≈ 0.993。

### 4 目標峰
- S1 with/without：峰隨距離；移除後峰位固定 304。  
- 僅限水平前視／已驗證包絡。

### A 排除 12/60
- 規則：**early_energy 兩段漂移 >5%**（事前門檻）。  
- 永遠是 idx 6,9,10,11（≈0.48–0.76 m），三遍相同。  
- 排除點 **peak 仍在直線上**；全 60 vs kept 48 的距離 OLS 幾乎一樣。  
- **不是** cherry-pick 不線性點。

### B primary
- 57/60 = way0；**僅 d≈0.592 m ×3 遍** 切 way1。  
- 正典規則仍是 **primary（有號 max 較大者）**，**不是**固定 way0。  
- 固定 way0 僅對照略優。

### Signedness（新建）
- 程式：`k = np.argmax(wf)`（**有號**）；primary = 較大 `np.max(wf)`。  
- S1/S2 落盤波形：**全非負** → 與 \(\arg\max|s|\) **180/180 重合**；CSV 與有號一致 60/60。  
- 論文寫有號 argmax；並註明正典數據上與絕對值等價。

### 3.1 貼稿
- 已改回 **primary 正典**；刪「改固定 way0」。  
- 陣列表述已降級（無可用通道身分／側向未過）。

**關閉文件**: `docs/plan_v2/reports/P0_AXIAL_CLOSED.md`

---

## 三、D2 圓 vs 橢圓（你列的下一優先）— 已裁定

### 問題
0.10 m 雙掛載 → 物理路徑可為 \(L=|p-TX|+|p-RX|\)（橢圓）→ 圓交會是否錯？

### 關鍵拆分
| 層 | 事實 |
|----|------|
| 幾何 | 軸向 \(L/2 - R \approx -s/2 \approx \mathbf{-5\,cm}\)（真） |
| 觀測 | V2 的 \(\hat r\) 是 **OLS→真值單站距離 \(R\)**，不是 \(L/2\) |
| 交會 | D2 用 \(\hat r\) 做**圓**最小平方 → 與觀測定義**匹配** |

### 正式 D2 closed 資料（150 視點量測）

| 比較 | RMSE |
|------|-----:|
| \(\hat r\) vs 單站 \(R\) | **1.46 cm**（bias +0.12 cm） |
| \(\hat r\) vs \(L/2\) | **4.71 cm**（bias +4.5 cm） |

Oracle：完美 \(R\)+圓 → 定位誤差 ≈0；誤用 \(L/2\)+圓 → ~5 cm。

### 裁定（請採納或反駁）

> **保持圓 multilateration 為 D2 正典。**  
> \(L/2-R\sim 5\) cm 寫入 **limitation／物理腳註**，不構成改橢圓的充分理由——除非放棄 OLS、改以原始雙站 ToF 為觀測。  
> 正式實驗側向 RMSE ~3.3 cm 主因是測距殘差與基線，不是「該用橢圓卻用圓」。

**報告**: `docs/plan_v2/reports/D2_CIRCLE_VS_ELLIPSE.md`  
**重算**: `python3 scripts/d2_circle_vs_ellipse_offline.py` → `circle_approx_adequate_for_D2_workspace: true`

---

## 四、請求你下一輪做什麼

請**不要**重開已關閉的 way 串接／40 kHz 波形／軸向 P0 主鏈，除非指出**與下列 SHA 數據矛盾**的具體行。

請擇一（或依序）：

### 選項 1（建議）— 審 3.1 貼稿是否可定稿
- 檔：`thesis/P0_SECTION_3_1_PATCH.md`  
- 用：`THESIS_ARGUMENTATION_GATES.md` G0–G5  
- 輸出：可貼入正式 docx / 還要改哪幾句

### 選項 2 — 審 D2 論文表述
- 檔：`D2_CIRCLE_VS_ELLIPSE.md` + 既有 `D2_multilateration_report.md`  
- 檢查：會不會過強宣稱「單站物理」、會不會漏寫 0.10 m 雙站 limitation

### 選項 3 — 第二優先內部效度（控制器／三臂）
- 僅在你接受：軸向 P0 = 關閉、D2 圓 = 接受（或有條件接受）之後

### 請用此表回覆

```text
軸向 P0：        [ ] 關閉 PASS  [ ] 仍有條件  [ ] FAIL — 理由：________
D2 圓正典：      [ ] 接受      [ ] 有條件    [ ] 拒斥 — 理由：________
下一節要審：    [ ] 3.1 貼稿  [ ] D2 論文句  [ ] 三臂效度  [ ] 其他：________
```

---

## 五、簡短版（聊天可另貼）

> Repo tip **136367a**。軸向 P0 已正式關閉（P0_AXIAL_CLOSED.md）：way 不串接、scalar≠40kHz、OLS 距離、S1 峰、A 排除=能量QC、B primary 僅 0.59m 切、有號 argmax、3.1 改回 primary。D2：正式 range_est 貼 monostatic R（RMSE 1.5cm）不貼 L/2（4.7cm），故**維持圓交會**；L/2−R≈−5cm 只寫 limitation（D2_CIRCLE_VS_ELLIPSE.md）。請確認兩項 PASS 後審 3.1 貼稿或 D2 論文句。

---

## 六、版本指紋

| Commit | 內容 |
|--------|------|
| `6488503` | 論證閘門 + P0 離線審計初版 |
| `b506855` | P0 follow-up A/B |
| `a27b3cd` | 軸向 P0 正式關閉 + signedness |
| `b591de3` | D2 圓 vs 橢圓分析與報告 |
| **`136367a`** | STATUS/HANDOFF 同步（**目前 tip**） |

本回覆文件：`docs/plan_v2/REPLY_TO_GPT_P0_CLOSED_AND_D2.md`
