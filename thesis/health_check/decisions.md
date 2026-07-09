# decisions.md — 專案健檢關鍵決策紀錄
# isaacsim6.0 Acoustic Thesis Pipeline
# 健檢日期：2026-07-04

---

## 決策 D-01：向量數學工具不立即提取為共用模組

**決策：** 保留現狀（17+ 個檔案各自複製 `vec_tuple/sub/norm/dot/unit/add/scale`），**不在口試前重構**。

**理由：**
- 口試前動任何 `official_asset_*.py` 均可能引入 import 錯誤，破壞已驗證的 30/30 管線
- 這些函式是純數學，複製版本完全一致，執行時無分歧風險
- 重構屬「改善技術債」，不影響論文主 claim 的驗證鏈

**捨棄替代方案：** 立即建立 `vector_utils.py` 並全面替換 import
- 風險：17+ 個檔案需同時修改，任一遺漏即導致 `NameError`
- 影響範圍：Phase A 的 `official_asset_ur10_fixed_tcp_distance_sweep.py`、Phase B/C 的 `official_asset_ur10_ultrasonic_closed_loop_grasp.py` 等核心腳本

**建議時機：** 口試後，以獨立 PR 進行，附單元測試

**驗證狀態：** ✅ 已驗證（代碼掃描確認 17+ 個重複，內容完全相同）

---

## 決策 D-02：`to_jsonable()` 不立即統一

**決策：** 保留 13+ 個各自複製的 `to_jsonable()`，**不合併**。

**理由：**
- 各複製版本有微小差異（型別順序、遞迴深度），合併需小心比對每個版本
- 函式輸出影響所有 trial 的 JSON 序列化，若改錯則 dataset 格式變動
- v9 canonical dataset 已產出，修改序列化邏輯有污染歷史對比的風險

**風險：** 若需修改序列化行為（例如新增欄位），必須在 13+ 個地方同步

**驗證狀態：** ✅ 已驗證（代碼掃描確認）

---

## 決策 D-03：`ROBOT_PRIM_PATH` 與 `EE_FRAME` 雙重定義 — 接受現狀

**決策：** `grasp_passport_v1.py` 和 `geometry_passport_v1.py` 各自定義相同的 `ROBOT_PRIM_PATH="/World/ur10"` 和 `EE_FRAME="ee_link"`，**不合併**。

**理由：**
- 兩個 passport 有不同的功能域（幾何場景 vs 夾取任務）
- 合併需重新調整所有 import 鏈
- 值不可能分歧（這是 USD 場景固定路徑），不構成執行時風險

**驗證狀態：** ✅ 已驗證（兩個檔案的值完全一致）

---

## 決策 D-04：DATA_MANIFEST.md 中 Canonical Phase A 摘要缺失 — 標記為高優先補救

**決策：** `phase3_rtx_pra_comparison_fixed_tcp_repeatability_v1/` 未在 `runtime/outputs/` 下找到，而文件宣稱此目錄應進 git。**需要在口試前執行一次 Phase A 流程或重新放置此目錄。**

**理由：**
- 口試委員可能直接查詢此路徑驗證 Phase A 結果（ρ≈−0.66 等數字）
- DATA_MANIFEST.md 和 REPRODUCIBILITY_AUDIT.md 均明確記載此為 canonical 輸出
- 這是 claim L1（30/30 + 距離趨勢）的唯一直接依據

**捨棄替代方案：** 修改文件說明「不進 git」
- 風險：文件一致性更難維護，口試時需解釋為什麼沒有

**驗證狀態：** ❌ 未驗證（目錄不存在，無法確認內容）

---

## 決策 D-05：7 個靜默例外吞噬 — 接受（低優先）

**決策：** `ur10e_robotiq_common.py`（L366/645/689）等處的 `except Exception: pass` **不在口試前修改**。

**理由：**
- 這些 except 都在 robot 初始化的 retry 路徑或 fallback 路徑
- 修改後需要重新測試整個機器人啟動序列
- 口試前的主要風險在文件完整性，而非 robot 初始化 retry 邏輯

**後續建議：** 改為 `except Exception as e: print(f"WARN: {e}", flush=True)` 或寫入 log

**驗證狀態：** ✅ 已驗證（7 個位置確認）

---

## 決策 D-06：舊版論文大綱與 SESSION_HANDOFF 文件 — 保留不刪

**決策：** `THESIS_OUTLINE_FCU_2026-06-27.md`、`06-29.md`、`SESSION_HANDOFF_2026-06-27.md`、`06-28.md` 及 `THESIS_CONTENT_2026-06-27.md` 保留現狀，**不刪除**。

**理由：**
- 健檢規則明確要求「不刪除任何檔案」
- 這些是歷史紀錄，可作為論文演進的 audit trail

**影響：** 增加 thesis/ 目錄的導覽難度；後續接手者可能誤用舊版大綱

**緩解方案：** 在 final_report.md 和 notes.md 中明確標示哪個版本是 canonical

**驗證狀態：** ✅ 已驗證（檔案存在確認）

---

## 決策 D-07：硬寫絕對路徑 — 標記技術債，不立即修改

**決策：** 30+ 個 `/home/lab109/song/isaacsim6.0/...` 硬寫路徑（包含 `acoustic_calibration_v1.py:13`）**不在口試前修改**。

**理由：**
- 本專案在固定機器（lab109）上執行，移植性不是當前需求
- `acoustic_calibration_v1.py` 的 hardcode 路徑有 fallback（找不到 JSON 就用 DEFAULT_CALIBRATION），不影響實驗

**最高風險點：** `acoustic_calibration_v1.py:13` — 若 calibration JSON 不存在且靜默 fallback，可能導致標定表不一致而不被發現

**後續建議：** 用 `Path(__file__).parent.parent / "runtime/outputs/..."` 相對路徑替代

**驗證狀態：** ⚠️ 部分驗證（路徑存在，fallback 邏輯確認，但 JSON 實際存在性未確認）
