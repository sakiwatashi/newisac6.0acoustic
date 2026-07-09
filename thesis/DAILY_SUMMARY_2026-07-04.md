# 今日工作統整 — 2026-07-04

**專案：** 逢甲大學電聲碩士 · RTX Acoustic 超音波閉環接近控制
**本日完成：** Bug 修復（延續 07-02/03）+ 兩份論文輔助文件建立

---

## 一、程式碼修復（scripts/）

### Fix A — `rtx_acoustic_factory.py`（實驗管線改善）

**問題：** `tof_ns` 距離估算使用「峰值振幅最大」的 Signal Way，但多徑反射可能讓非直接路徑能量更強，導致 ToF 高估距離。

**修復：** 新增 `_pick_tof_primary_way()` 函式，改為選取 `first_time_offset_ns` 最小（最早到達）的 Signal Way。

```python
# 新增函式
def _pick_tof_primary_way(ways) -> SignalWayStats:
    valid = [w for w in ways if isfinite(w.first_time_offset_ns) and w.first_time_offset_ns > 0]
    if not valid:
        return _pick_primary_way(ways)   # fallback
    return min(valid, key=lambda w: w.first_time_offset_ns)
```

**同步修改：**
- `summarize_gmo_frame` 新增 `tof_primary_sgw_*` 欄位輸出
- `acoustic_features_from_gmo` 改用 `tof_primary_sgw_first_time_offset_ns` 作為 `tof_ns`
- 舊 `primary_sgw_*` 欄位（能量基準）維持不變，向下相容

---

### Fix B — `ultrasonic_grasp_common.py`（代碼品質）

**問題：** `from ur10e_robotiq_common import ...` 出現在 `_tier_b_calibration_tables()` 函式定義之後，位置在模組層級，屬於語法上合法但邏輯上錯誤的佈局。

**修復：** 將所有 import 移至檔案頂部，在 `_TIER_B_CAL: tuple | None = None` 之前。

---

### Fix C — `ultrasonic_grasp_common.py`（SurfaceGripper 路徑錯誤）

**問題：** `setup_surface_gripper(stage, ee_path)` 接收 `ee_path="/World/ur10/ee_link"`，但內部硬寫 `gripper_parent = "/World"` → 夾爪建在 `/World/SurfaceGripper` 而非預期的 `/World/ur10/ee_link/SurfaceGripper`，導致 C++ plugin 找不到夾爪。

附帶問題：使用 `importlib.util` 動態載入 `robot_schema`，路徑異動即失效。

**修復：**
```python
# 修復前：
gripper_parent = "/World"
gripper_prim = create_surface_gripper(stage, gripper_parent)

# 修復後：
gripper_prim = create_surface_gripper(stage, ee_path)  # 掛在 ee_link 下

# import 修復前：
import importlib.util; spec = importlib.util.spec_from_file_location(...)

# 修復後：
from usd.schema.isaac import robot_schema  # 直接 import
```

---

## 二、論文文件建立（thesis/）

### 文件 1：`TECHNICAL_REFERENCE_2026-07-03.md`（代碼技術參考）

- 18 個章節，1,283 行
- 對象：需要了解程式實作的讀者
- 內容：每個 API 的完整使用方式、函式定義、常數表、腳本清單
- 焦點：**怎麼寫代碼**

### 文件 2：`CONCEPTS_AND_MATH_2026-07-03.md`（概念與數學）

- 11 個章節
- 對象：口試委員、不熟 Isaac Sim 的讀者
- 內容：名詞白話說明 + 9 個核心數學公式 + 驗證方法
- 焦點：**為什麼這樣做**

---

## 三、今日兩份文件涵蓋的關鍵內容對照

| 主題 | TECHNICAL_REFERENCE | CONCEPTS_AND_MATH |
|------|---------------------|-------------------|
| Isaac Sim 是什麼 | API 用法 | 白話說明 + 與真實世界對照 |
| RTX Acoustic | Acoustic / AcousticSensor / Writer 代碼 | WPM 物理模型說明 |
| GMO | 欄位定義、parse 代碼 | x/y/z 不是座標的警告說明 |
| Signal Way | SignalWayStats dataclass | 直接路徑 vs 多徑反射圖解 |
| Early Energy | `_early_energy()` 實作 | $E = \sum\|A_i\|$ 前 25%，物理意義 |
| 距離估算 | 標定表 + 插值代碼 | 線性插值數字範例、音速換算 |
| 閉環控制 | 狀態機全部狀態與轉換條件 | 開環 vs 閉環圖解 |
| 消融實驗 | 特徵欄位 19 維定義 | LOTO vs K-fold 洩漏問題圖解 |
| 統計驗證 | spearmanr 調用方式 | n=6 統計力道說明（趨勢 ≠ 顯著） |
| Claim Boundary | 可/不可宣稱對照表 | 背後原因說明 |

---

## 四、現行文件地圖

```
thesis/
  THESIS_OUTLINE_FCU_2026-06-30.md       ← 論文大綱（六章版）
  TECHNICAL_REFERENCE_2026-07-03.md      ← 代碼技術完整參考（今日）
  CONCEPTS_AND_MATH_2026-07-03.md        ← 名詞 + 數學 + 驗證（今日）
  PHYSICAL_AI_ACOUSTIC_GRASP_SUMMARY_*   ← 實驗結果摘要
  THESIS_REFRAME_PLAN_2026-06-30.md      ← 敘事重構計畫

REPRODUCIBILITY_AUDIT.md                 ← 可重現審計（口試委員用）
DATA_MANIFEST.md                         ← 資料契約

scripts/
  rtx_acoustic_factory.py                ← ✅ Fix A 已完成
  ultrasonic_grasp_common.py             ← ✅ Fix B + C 已完成
```

---

## 五、待辦事項

| 優先 | 項目 | 狀態 |
|------|------|------|
| 高 | 口試前嵌入 Phase B/C 軌跡圖（圖5.1–5.2） | ⏳ 待辦 |
| 高 | 填入封面研究生姓名 | ⏳ 待辦 |
| 中 | 導師確認 THESIS_OUTLINE 大綱 | ⏳ 待辦 |
| 低 | SurfaceGripper 殘留風險：runtime 測試確認 C++ plugin 時序 | ⏳ 待辦 |
| 低 | CH201 實機驗證（未來工作） | 📅 未來 |
