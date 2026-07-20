#!/usr/bin/env python3
"""掛口試備註（Word 註解／便利貼）到 THESIS_DRAFT_FCU_v2.docx。

- 不改正文，只加 comments（側邊便利貼）。
- 以唯一錨點字串定位；重建論文後可重跑本腳本再掛一次。
- 用法：
    python3 thesis/annotate_defense_sticky_notes.py
    python3 thesis/annotate_defense_sticky_notes.py --docx thesis/THESIS_DRAFT_FCU_v2.docx
"""
from __future__ import annotations

import argparse
import copy
import random
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
W16CID = "http://schemas.microsoft.com/office/word/2016/wordml/cid"
W16CEX = "http://schemas.microsoft.com/office/word/2018/wordml/cex"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

ET.register_namespace("w", W_NS)
ET.register_namespace("w14", W14)
ET.register_namespace("w15", W15)
ET.register_namespace("w16cid", W16CID)
ET.register_namespace("w16cex", W16CEX)
ET.register_namespace("r", R_NS)

AUTHOR = "口試備註"
INITIALS = "口試"

# (chapter_tag, unique_anchor_substring, sticky_note_text)
# anchor 必須在全文唯一出現（或第一次即為目標）；腳本取第一次匹配。
NOTES: list[tuple[str, str, str]] = [
    # ── 摘要 ──────────────────────────────────────────────
    (
        "摘要",
        "「包絡優先」之感測回授接近流程",
        "【口試・方法】包絡優先＝先量「讀得到」的幾何，再把任務放進包絡。"
        "若被問「為何不直接做閉環」：沒包絡就無法區分感測失敗 vs 控制失敗。"
        "【文獻】組合為本研究方法論；分項見 Valin 等 [4]、Tsuchiya 等 [18]、Liu 等 [13]。",
    ),
    (
        "摘要",
        "選定幾何格點之配對移除掃描",
        "【口試・方法】配對移除：同姿態先量有目標、再物理移除目標量背景；"
        "差＝目標貢獻。不是「關掉感測器」——那會把整條路徑一併拿掉。"
        "【文獻】Valin 等 [4]、Tsuchiya 等 [18]、Liu 等 [13]（3.3 支柱一）。",
    ),
    (
        "摘要",
        "閉環採三臂資訊消融",
        "【口試・方法】三臂缺一不可：\n"
        "• 聲學＝完整因果鏈\n"
        "• 盲走＝同管線只拿掉估距資訊（量測動作仍做）→ 證因果\n"
        "• 開環＝完全不量測之幾何基線 → 揭穿「到達率陷阱」\n"
        "同 seed、同目標組。"
        "【文獻】消融 Meyes 等 [11]；預註冊 Nosek 等 [5]。",
    ),
    (
        "摘要",
        "停止位置與目標 r＝0.9856",
        "【口試・數字】主結果是 D1.5（手臂載具），不是未掛臂 D1（r=0.997）。"
        "主指標是 r/RMSE，不是到達率。彈藥：開環也能 22/30「到達」。",
    ),
    (
        "摘要",
        "聲學對位與接觸觸發附著升舉",
        "【口試・邊界／Q2】這是 weld-on-stall／接觸觸發附著，不是摩擦夾持。"
        "可支持：聲學對位；推論不及：物理摩擦抓牢。"
        "盲走抓空→不觸發附著，對照區辨力仍在。",
    ),
    (
        "摘要",
        "單次輸出之左右線索經四項檢驗未成立",
        "【口試・負結果】四重證偽＝能量差 ρ=0.357／TDOA r≈0／id 恆 (0,0,0)／rxGroup 第二路噪音。"
        "結論：側向缺在引擎輸出層，不是演算法選錯。",
    ),
    (
        "摘要",
        "全文推論限於單一隨機種子與確定性模擬引擎",
        "【口試・Q3】承認單 seed。但每回合目標在走廊內隨機抽樣；"
        "確定性引擎下跨 seed 主要測的是目標分佈抽樣，不是感測雜訊。"
        "可補：D1.5 三 seed ~2h GPU。噪聲探針：SNR≥20 dB 測距無損。",
    ),
    # ── 第一章 ────────────────────────────────────────────
    (
        "1.1",
        "多徑傳播（multipath：聲波經牆面等表面多次反彈後才抵達接收器）",
        "【口試・名詞】multipath＝多條反射路徑疊加；殘響＝晚到回波時間拖尾。"
        "因此不能把「波形上一個峰」直接當唯一直達路徑。本文用配對移除隔離目標貢獻。"
        "【文獻】Valin 等 [4]；Tsuchiya 等 [18]；Liu 等 [13]。",
    ),
    (
        "1.1",
        "「最後一公尺」（last-meter）",
        "【口試・白話】目標大概已經進工作區了，還差最後一小段要靠距離回饋慢慢靠近。"
        "不是全場亂逛找東西。相機粗定位 + 超音波精接近＝互補，不是取代相機。",
    ),
    (
        "1.1",
        "Generic Model Output（GMO）的原始感測資料",
        "【口試・名詞】GMO＝RTX Acoustic 原始輸出；以 signal way（TX–RX–通道回波序列）紀錄振幅。"
        "詳 3.1。timeOffsetNs 在 6.0 恆 0，不能拿來算距離。",
    ),
    (
        "1.1",
        "實體超音波晶片（如 TDK CH201）",
        "【口試・範圍】CH201＝實機對應硬體例。本文全模擬、不宣稱波形等價；"
        "實機任務級協定列 6.3。選模擬理由：變因可隔離、消融可嚴格做。",
    ),
    (
        "1.1",
        "視覺語言模型（Vision-Language Model, VLM）",
        "【口試・定位／Q6】VLM＝影像+語言語義；強在「有什麼、大概在哪」。"
        "超聲＝已知方向距離趨勢、不怕反光煙塵。本文是 last-meter 元件，不是取代相機。",
    ),
    (
        "1.2",
        "執行前寫定通過判準（預註冊）",
        "【口試・方法】預註冊＝判準寫在 runner header、執行前鎖定。"
        "失敗不放寬：D3 首輪 posture 如實 False → 改走廊重跑（鐵律六）。"
        "【文獻】Nosek 等 [5] The preregistration revolution（PNAS 2018）。",
    ),
    (
        "1.2",
        "盲走失能能否把因果鎖在聲學資訊上",
        "【口試・方法】消融＝刻意拿掉資訊看是否失能。"
        "盲走保留量測時序／成本，只把估距換成 +∞ → 分離「量測副作用」與「資訊使用」。"
        "【文獻】Meyes 等 [11] Ablation studies in ANNs。",
    ),
    (
        "1.2",
        "對位／附著與摩擦界線見 5.3、6.2",
        "【口試・RQ4】對位已驗證；摩擦／附著細節見 5.3。側向見 5.4。",
    ),
    (
        "1.3",
        "先感測、再控制、再擴維、再夾取",
        "【口試・白話】整條研究像蓋樓：先確認「聽不聽得到」（S1/S2），"
        "再證明「聽覺能帶路」（D1/D1.5），再補「左右定位」（D2），最後才「對準夾起」（D3/D4）。"
        "第五章章節順序是寫作安排；邏輯順序以 1.3 這句為準。",
    ),
    (
        "1.3",
        "D1：感測器尚未掛上手臂",
        "【口試・白話】先不要手臂干擾，只問：估距對不對、會不會停。"
        "通過後才掛上 UR10e 做 D1.5（主結果）。",
    ),
    (
        "1.3",
        "D2：單次輸出左右資訊不足時",
        "【口試・白話】一次聽看不出左右 → 手臂側移量幾次距離，用幾何交會估平面位置。"
        "已做定位與二維接近；「定位完再夾」還沒宣稱（左右誤差仍偏大）。",
    ),
    (
        "1.3",
        "不在本文宣稱範圍者，併入限制說明",
        "【口試・白話】這段不是否定成果，是先講清楚「論文不包什麼」："
        "沒上真機探頭、不吹摩擦抓牢、還沒多 seed 統計。"
        "比單獨開一長段「排除項目」好讀，重點仍在限制句。",
    ),
    (
        "1.3",
        "定位之後再夾取",
        "【口試・白話】D2 能走到目標附近，但左右誤差大約還大於手指夾得住的寬度，"
        "所以不能說「二維定位完就能夾」。後續工作。",
    ),
    (
        "1.3",
        "預定停止距離固定為 0.35 m",
        "【口試・白話】0.35 m＝刻意停在目標前方的距離，不是撞上去。"
        "太近（約 0.32 m 以內、桌高目標）距離讀數不可靠，所以定在 0.35 m 留餘裕。",
    ),
    (
        "1.3",
        "桌面高度目標約在 0.32 m 以內距離編碼不可靠",
        "【口試・白話】太近、又從斜上看桌面目標時，波形不穩，不能再閉環邊走邊聽。"
        "D3 夾取改用「停下那一刻的估距往前推一步」，近距離不再邊量邊走。",
    ),
    (
        "1.3",
        "本機獨立執行環境",
        "【口試・白話】實驗在實驗室電腦本機跑 Isaac Sim，不是雲端代跑。"
        "正式數字用無視窗批次；錄影／口試展示才開視窗（GUI）。",
    ),
    (
        "1.4",
        "SNR（配對移除定義之偵測訊噪比，見 3.3）",
        "【口試・公式】本文 SNR 不是通訊 SNR。"
        "SNR = max|W有−W無| / max|W有−W雜訊參考|；>10 可偵測（見 3.3）。",
    ),
    (
        "1.4",
        "RMSE、r／ρ、IK、seed",
        "【口試・統計】側向能量用 ρ（單調），不用 Pearson；ρ≥0.9 判準，實測 0.357→證偽。"
        "IK＝末端位姿→關節角；暖啟動防多解。D3 遠端升舉 IK 無解＝可達性非聲學。",
    ),
    (
        "1.4",
        "指標失效：表面到達率可被走廊寬度撐高",
        "【口試・方法學】表面指標（到達率）可被走廊寬度撐起來。"
        "主指標改用停止位置相關性 + 盲走消融。6.1 開環到達率是活教材。",
    ),
    (
        "1.4",
        "盲走臂：量測管線同聲學臂，僅估距改無資訊值",
        "【口試・名詞】對位＝夾爪中心 vs 目標中心水平吻合（±2 cm）。"
        "多點定位＝多視點距離交會（D2：5 點、基線 0.3 m）。"
        "【文獻】Kapoor 等 [2]；Hayes 等 [1]；Meyes 等 [11]。",
    ),
    (
        "1.4",
        "貢獻定位（全文一句）",
        "【口試・Q1 彈藥】若被譏「只是在測光線追蹤測距儀」："
        "正結果是載體；負結果地圖＋效度框架才是可推廣主張（6.1）。"
        "口頭收斂三項：包絡優先／三臂因果／側向證偽＋多視點恢復。",
    ),
    # ── 第二章 ────────────────────────────────────────────
    (
        "2.1",
        "工具中心點（Tool Center Point, TCP：手臂末端工具的參考點）",
        "【口試・名詞】TCP＝末端工具參考點。感測器掛載相對 TCP／腕連桿幾何固定。",
    ),
    (
        "2.1",
        "Geometry Passport，即「幾何護照」",
        "【口試・工程】Geometry Passport＝掛載／目標／桌面幾何寫清楚並可核對的記錄慣例。",
    ),
    (
        "2.2",
        "不宜假設「模擬波形＝實機波形」",
        "【口試・邊界】本文不做 sim-to-real 遷移實驗。"
        "Höfer：任務級指標；RTX Acoustic＝趨勢級可行性，非 CH201 波形對照。"
        "【文獻】Höfer 等 [16]；Gao 等 [27]；NVIDIA [28] 等。",
    ),
    (
        "2.2",
        "近端策略最佳化（Proximal Policy Optimization, PPO）",
        "【口試・名詞】PPO＝常見 RL 策略優化。主線控制器仍是規則式（D1–D3／D4-A）。"
        "D4-B 另在 Isaac Lab 用 PPO 學接近／合爪時機（觀測不含目標座標），"
        "再串回同一物理場景；不得把 Lab 高成功率說成純聲學 end-to-end。"
        "仍須 scaffold／消融邊界（見 5.3 節末 D4）。",
    ),
    (
        "2.3",
        "早期反射能量可作距離的弱趨勢指標",
        "【口試・特徵取捨】文獻提早期能量；本文主特徵是峰值位置（飛行時間代理），不以能量主推距離。",
    ),
    (
        "2.3",
        "跨實驗室輪測（round-robin：同一題目多實驗室各自跑再比較）",
        "【口試・方法學】不同引擎對早期反射／殘響常有系統差 → 模擬≠實機。"
        "支持「任務級、趨勢級」表述。",
    ),
    (
        "2.4",
        "參數化模型用公式直接產生「看起來合理」的回波",
        "【口試・為何 WPM】參數化：快但不跟場景走；光線追蹤：跟幾何走 → 包絡問題才有意義。",
    ),
    (
        "2.4",
        "不輸出點雲",
        "【口試・澄清】RTX Acoustic ≠ 光達。輸出是波形／信號路徑，不是深度圖或點雲。",
    ),
    (
        "2.5",
        "已知搜尋走廊（目標被允許出現的工作帶）",
        "【口試・範圍】不是全域 open-world 搜尋；VLM 粗定位屬上層，本文管最後一公尺距離回授。",
    ),
    (
        "2.6",
        "不含實體感測器的熱雜訊與元件變異",
        "【口試・Q3 延伸】引擎確定 → 重複量測可逐位相同。"
        "離線噪聲探針（未入正文）：SNR≥20 dB 解析測距仍穩；20→14 dB 斷崖。",
    ),
    (
        "2.7",
        "波束成形（beamforming：依幾何延遲把多路訊號對齊相加，形成指向性）",
        "【口試・名詞】要多路可獨立取樣。第四章證偽後改多點定位／合成孔徑。"
        "【文獻】Kerstens 等 [10]；Kapoor [2]；Hayes [1]。",
    ),
    (
        "2.7",
        "合成孔徑（synthetic aperture）",
        "【口試・名詞】移動中多次量測等效大孔徑。D2 是離散五點圓交會，不是完整 SAS 成像。"
        "【文獻】Hayes 等 [1]。",
    ),
    (
        "2.8",
        "模擬可行性研究（simulation-based feasibility study）",
        "【口試・定位】可行性＋效度，不是新物理模型、不是部署標竿。",
    ),
    (
        "2.8",
        "表 2.1 最接近工作類型與本研究之對照",
        "【口試】表回答「差在哪」：元件都會撞車；組合＝RTX Acoustic＋三臂＋包絡＋側向證偽。"
        "貢獻是流程不是發明 ToF／多點定位。",
    ),
    # ── 第三章 ────────────────────────────────────────────
    (
        "3.1",
        "波傳播模型（Wave Propagation Model, WPM）屬幾何光線追蹤式聲波模擬",
        "【口試・名詞】WPM＝光線追蹤式波路徑模擬，對幾何敏感 → 包絡實驗前提。"
        "仍非完整波動方程解算器。",
    ),
    (
        "3.1",
        "必須依「每條路徑的樣本數」把資料切開再接成一條時間軸",
        "【口試・工程陷阱】波形重建要按每路徑樣本數切緩衝區；"
        "誤用通道編號當時間軸 → 峰值壞掉。正文已降級程式名，口試可講原則。",
    ),
    (
        "3.1",
        "時間偏移欄位（timeOffsetNs）在 Isaac Sim 6.0 恆為 0",
        "【口試・引擎限制】不能靠 timeOffset 算 ToF；用 peak×週期×c/2。"
        "id 恆 (0,0,0)＝側向證偽第三項。",
    ),
    (
        "3.1",
        "量測一律多幀平均，並配合 3.3 節稽核剔除不穩定量測",
        "【口試・程序】暫態＋幀間跳動 → 多幀平均；標準常搭配 40 等待 + 24 平均。",
    ),
    (
        "3.2",
        "不沿用外部或舊批次常數，而在每一批新實驗中當場自校",
        "【口試・Q5】當輪自校用已知距離；控制回合真值只進記錄。"
        "若校正能造假，盲走共用校正也該成功——它失能。",
    ),
    (
        "3.2",
        "樣本週期 = 2 ÷（斜率 × 聲速）",
        "【口試・公式卡①自校】全文核心估距（不必背矩陣）：\n"
        "• peak = a·d + b  （峰值取樣點對已知距離 OLS）\n"
        "• d̂ = (peak − b) / a  （控制用估距）\n"
        "• T = 2/(a·c)  （樣本週期；c＝聲速）\n"
        "• ToF 敘事：d ≈ peak·T·c/2  與上式一致\n"
        "視軸 T≈103 µs、桌高≈101 µs；仍當輪自校，禁用固定 132.5 µs。\n"
        "【文獻】Zhmud 等 [7]。",
    ),
    (
        "3.2",
        "視軸（boresight，感測器指向軸）",
        "【口試・名詞】boresight＝指向軸。側向掃描是垂直於視軸橫移。",
    ),
    (
        "3.3",
        "max|W有目標 − W無目標| ÷ max|W有目標 − W雜訊參考|",
        "【口試・公式卡②SNR】本文操作定義（不是通訊 SNR）：\n"
        "SNR = max|W有 − W無| / max|W有 − W雜訊參考|\n"
        "W＝多幀平均波形；SNR>10 → 可偵測（S1 門檻）。\n"
        "分子＝目標貢獻；分母＝重複量測雜訊底。",
    ),
    (
        "3.3",
        "只把控制器可用的估距換成無資訊值（正無窮）",
        "【口試・盲走】估距→∞ → 永不聲學停止 → 撞護欄；量測動作仍做。",
    ),
    (
        "3.3",
        "執行前鎖定，避免看完結果再改門檻（資料窺探）",
        "【口試・方法】預註冊。D3：沒過就 False，改設計新目錄重跑。",
    ),
    (
        "3.3",
        "刻意不用單純到達率",
        "【口試・6.1】窄帶上開環也可高到達率；主指標＝r + 盲走失能。",
    ),
    (
        "3.3",
        "不合格量測標成無效並排除，不做事後插補",
        "【口試・稽核】平穩／姿態／感測器位姿。總帳 3173 步 0 違規（verify_all）。",
    ),
    (
        "3.4",
        "直接改寫空間位置，使下一影格出現在指定處，而非以物理力推動",
        "【口試・場景】寫 pose；探針：移目標波形大變；刪除≈移遠。手臂寫關節角。",
    ),
    (
        "3.4",
        "掛於腕部連桿並前伸 0.25 m，以離開夾爪機構的聲學陰影",
        "【口試・掛載】前伸躲 4.3 腕載聲影；D3 才真用夾爪。",
    ),
    (
        "3.4",
        "先等 40 影格消化暫態，再取 24 影格並拆成前後兩段各 12 影格平均",
        "【口試・參數】40+24；兩段能量差>5%→無效。經驗＋稽核，非任意。",
    ),
    (
        "3.5",
        "峰值樣本索引——多幀平均波形中振幅絕對值最大的取樣點位置",
        "【口試・特徵】最強回波到達時間代理＝往返距離。E1：學波形打不過此特徵。"
        "【文獻】Zhmud 等 [7]；He 等 [9]。",
    ),
    (
        "3.5",
        "早期能量——平均波形前 20 個取樣點的振幅平方和",
        "【口試・特徵】只做 SNR／平穩稽核，不推距離。",
    ),
    (
        "3.5",
        "已知垂直高度差（約 0.19–0.20 m）換成水平距離估計",
        "【口試・公式卡③控制律】\n"
        "• d̂_3D 來自 ①；水平：d̂_h = sqrt(d̂_3D² − Δh²)，Δh≈0.19–0.20 m（場景常數）\n"
        "• 若 d̂_h ≤ 0.35 m（standoff）→ 停止；否則沿軸前進 0.05 m\n"
        "• 無濾波、無多步預測——可歸因優先\n"
        "盲走：d̂→∞ → 永不聲學停 → 撞護欄。",
    ),
    (
        "3.5",
        "目標真實世界座標只進記錄欄，不進任何控制判斷",
        "【口試・鐵律五】oracle 只進 log；盲走拿掉估距就崩。",
    ),
    (
        "3.5",
        "走廊端點強制停止",
        "【口試・名詞】護欄≠聲學停止；盲走幾乎全靠它停。",
    ),
    (
        "3.5",
        "控制器保持最簡：固定步長前進、無濾波、無多步預測",
        "【口試・公式卡④對位】D3 成功定義：|x_夾爪 − x_目標| ≤ 0.02 m（±2 cm 預註冊）。\n"
        "升舉成功：附著後目標升高 ≥ 0.05 m（與對位分開陳報）。",
    ),
    (
        "3.5",
        "控制器保持最簡：固定步長前進、無濾波、無多步預測",
        "【口試・取捨】可歸因優先。D4-B 的 PPO 是輔助接口，不是取代此最簡律；"
        "同場景串聯仍分層報對位／升舉，並保留 weld 邊界。",
    ),
    (
        "3.6",
        "D3 更換目標物前，另以三道前置閘門重測",
        "【口試・閘門】可偵測／測距／夾取力學。另有斜率歸因（移目標 vs 移感測器）。",
    ),
    # ── 第四章 ────────────────────────────────────────────
    (
        "4.1",
        "四因子配對移除掃描",
        "【口試・S1】距離×尺寸×俯仰×干擾 → 52 格；每格獨立啟動。"
        "三段：有目標／雜訊參考／無目標。",
    ),
    (
        "4.1",
        "合計 36/52 格可偵測",
        "【口試・數字】否定「完全不可行」；也沒觸發「有手臂就全滅」中止條件。"
        "後續任務放水平指向可偵測帶。",
    ),
    (
        "4.1",
        "主宰因子是「指向」，不是「干擾物」",
        "【口試・發現】0° 有桌+臂仍可偵測；60° 無干擾也全滅。"
        "機制：方塊鏡面，大俯角回波偏離 RX。",
    ),
    (
        "4.1",
        "感測器後方物體對前向路徑的貢獻，在此確定性模擬下為零",
        "【口試・發現】C vs D SNR 逐位相同 → 後方手臂 0 貢獻。失敗先查擺位指向。",
    ),
    (
        "4.2",
        "皮爾森 r＝0.9994，RMSE 1.21 cm",
        "【口試・Q1】這是開環測距 datasheet，不是閉環主張。"
        "閉環看消融＋行為量（D1.5 r≈0.986）。",
    ),
    (
        "4.2",
        "0.15–0.26 m 近距點因俯視角超過約 50°，被平穩性稽核排除",
        "【口試・0.32 m】近距角大被踢；任務避開；連到 standoff 0.35 m 與 D3 一次推算。",
    ),
    (
        "4.2",
        "十次重啟重複性測試中，峰值位置完全相同，能量特徵變異係數為 0",
        "【口試・詮釋】CV=0＝管線確定性≠抗真實雜訊。跨 seed／噪聲另談。",
    ),
    (
        "4.2",
        "校正斜率跨批次表面可差約一成，做了兩層歸因",
        "【口試・M3】CI 涵蓋主斜率；移目標 vs 移感測器無系統差。斜率≈介質+取樣。",
    ),
    (
        "4.3",
        "側向（左右）四重證偽",
        "【口試・背誦】①能量 ρ=0.357 ②TDOA 恆偏移 ③id 000 ④分組二路噪音 → 改 D2 多點定位。",
    ),
    (
        "4.3",
        "中心頻率參數無效",
        "【口試・負結果】20–100 kHz 峰值相同；引擎無頻率物理。40 kHz 是實務對應不是掃頻最優。",
    ),
    (
        "4.3",
        "腕載聲影",
        "【口試・機制】腕部+夾爪網格陰影 → 含臂桌貢獻≈噪聲；無臂超高。解法：前伸 0.25 m。",
    ),
    # ── 第五章 ────────────────────────────────────────────
    (
        "5.1",
        "感測器是可獨立放置、未掛在實體手臂上的物件",
        "【口試・D1】未掛臂＝隔離感測+控制，先拿掉 IK 變因；再 D1.5 上臂。",
    ),
    (
        "5.1",
        "避開第四章約 0.32 m 以內的桌高失效區",
        "【口試】任務幾何引用 S1/S2；包絡優先的閉環體現。",
    ),
    (
        "5.1",
        "D0 閘門",
        "【口試】移感測器 13 點 r＝0.9958≥0.99；證明引擎有追感測器。",
    ),
    (
        "5.1",
        "目標真值只進記錄欄，不進控制",
        "【口試・鐵律五】oracle 隔離；被問洩漏＋盲走失能。",
    ),
    (
        "5.1",
        "停止位置與目標 r＝0.9970",
        "【口試】D1 上限；D1.5 0.9856 幾乎無損 → 主誤差不是 IK。",
    ),
    (
        "5.2",
        "腕部第三連桿（軟體名稱 wrist_3_link）",
        "【口試】前伸 0.25 m 離陰影；逐步姿態／位姿稽核。",
    ),
    (
        "5.2",
        "以上一步解為初值（暖啟動）",
        "【口試】暖啟動減多解跳躍；D3 遠端升舉仍可能 IK 無解。",
    ),
    (
        "5.2",
        "Welch t 檢定（不假設兩組變異數相等）",
        "【口試】D1.5 t＝−10.6 p＜0.001；主判準仍是 r/消融。",
    ),
    (
        "5.2",
        "開環臂：固定行程停 0.80 m，RMSE 7.8 cm，22/30 落入 10 cm",
        "【口試・到達率陷阱】看起來不差但 r＝0；不是追蹤。",
    ),
    (
        "5.3",
        "用停止當下估距一次推算目標位置",
        "【口試】近距＜0.32 m 不再閉環；一次推算是設計輸入。",
    ),
    (
        "5.3",
        "正式前三道閘門皆過",
        "【口試】SNR 31.9–82.3；r＝0.996；10 次序列姿態乾淨。",
    ),
    (
        "5.3",
        "改為接觸觸發之附著",
        "【口試・Q2】非摩擦夾持；觸發＝物理接觸；盲走抓空失敗。",
    ),
    (
        "5.3",
        "聲學對盲走費雪精確檢定單尾 p＝0.004",
        "【口試】首輪 18/30 vs 7/30；複驗 p＜0.001。",
    ),
    (
        "5.3",
        "對位率與升舉率不相乘成「總成功率」",
        "【口試】聲學 vs 力學分開，避免 weld/捕捉窗洗成聲學成功率。",
    ),
    (
        "5.3",
        "90 回合中 3 回合在升舉階段 IK 無解",
        "【口試】如實 False；可達性邊界；縮走廊重跑不改判準。",
    ),
    (
        "5.3",
        "正典主結果為獨立複驗（走廊上限 1.20→1.15 m",
        "【口試・複驗】新目錄重跑；四判準全綠；數據保留。",
    ),
    (
        "5.3",
        "統計容差 ±2 cm 略寬於夾爪物理捕捉窗約 ±1.5 cm",
        "【口試・縫隙】對位成功升舉失敗多在 1.5–2.0 cm、停短；容差預鎖不事後改。",
    ),
    # ── 5.3 末 D4 延伸（正文已寫入；便利貼補口試口徑）────────────────
    (
        "5.3-D4",
        "其後另做一輪延伸（代號 D4）",
        "【口試・D4 定位】D4 不改寫 D3 r3 主數字，只補三件事：\n"
        "（1）連續小步升舉執行器；（2）摩擦-only 是否救得了升舉；（3）策略能否接到同場景升舉。\n"
        "口頭三句：主結果仍是對位；weld 不是偷渡摩擦；同場景 n=90 有數字但不乘成 e2e。",
    ),
    (
        "5.3-D4",
        "無附著時摩擦保持是否真的救不回來",
        "【口試・g0／摩擦邊界】無 weld、僅指墊摩擦：對位／接觸可有，升舉 z 增益≈0（冒煙 0/2）。\n"
        "同條件開 weld-on-stall：升舉恢復。故主宣稱仍是聲學對位；升舉＝接觸觸發附著，不是摩擦夾持。",
    ),
    (
        "5.3-D4",
        "正式 90 回合（單一 closed 臂，seed＝20260718）",
        "【口試・同場景串聯數字】n=90：對位 76.7%（69/90）、升舉 74.4%（67/90）、"
        "P(升舉|對位)≈76.8%、平均 |e|≈1.5 cm。\n"
        "規則臂 D4-A closed n=30：對位 73.3% vs 盲走 40%（Fisher p≈0.009），方向同 D3 r3。\n"
        "對位與升舉仍分層、不相乘。",
    ),
    (
        "5.3-D4",
        "對位率 76.7%（69/90）",
        "【口試・domain gap】策略在 Lab 固定 TCP 走廊訓，評測在桌面臂載物理場景 → 有落差。\n"
        "對位與規則臂同級 → 瓶頸不在「完全對不到」，而在域差＋升舉仍靠 weld。",
    ),
    (
        "5.3-D4",
        "純估距獎勵與部署級摩擦夾持都不在宣稱內",
        "【口試・Lab 消融】聲學 obs＋距離 scaffold → 真實近距+合爪可高；\n"
        "BLIND（聲學置 0）＋scaffold 也可高 → 不能說「必須聽音」；\n"
        "純 d̂ 獎勵 → 真實成功可崩成 0%（估距假近遠距合爪）。\n"
        "故：可支持「無目標座標觀測下時機可學」；不支持 pure-reward e2e、不支持摩擦夾持。",
    ),
    (
        "5.3-D4",
        "小結與 D3 r3 的關係",
        "【口試・正典關係】口試主對位數字仍背 D3 r3（對位 80% vs 盲走 33% 等四判準）。\n"
        "D4＝執行器／摩擦負結果／策略串聯接口。被問「那 D4 算不算主結果」→ 延伸證據，不替換 r3。",
    ),
    (
        "1.4",
        "D4 以同場景策略串聯再驗此鏈",
        "【口試・白話】D4 只是證明「策略接得上同一套物理場景」；主故事仍是聲學對位，不是改走強化學習主線。"
        "對位、升舉要分開報，不要乘成一個漂亮總成功率。",
    ),
    (
        "6.2",
        "策略在 90 回合同場景串聯中對位約 77%",
        "【口試・6.2 邊界】D4 強化「鏈可接」；可支持表可加：同場景串聯對位～77%、升舉～74%。\n"
        "推論不及表必保留：摩擦夾持、pure-reward e2e、對位×升舉當唯一總成功率。",
    ),
    (
        "6.4",
        "D4 同場景串聯（90 回合）對位約 77%",
        "【口試・RQ4】D3 證明對位；D4 n=90 只強化鏈可接，不改「升舉＝weld、非摩擦」。\n"
        "二維再夾取仍因 D2 側向 3.3 cm＞夾取窗而不宣稱。",
    ),
    (
        "6.4",
        "以同場景策略串聯展示接口可行",
        "【口試・收尾加一句】驗證鏈＋對位正典（D3 r3）＋D4 接口可行；"
        "不是新物理、不是部署摩擦夾持、不是 pure RL 主線。",
    ),
    (
        "5.4",
        "側向掃描五個量測位置（橫向基線 0.30 m）",
        "【口試・公式卡⑤D2】五視點各得 d̂_i，求 (x,y) 使\n"
        "Σ_i ( d̂_i − √[(x−x_i)²+(y−y_i)²] )²  最小（最小平方圓交會）。\n"
        "實作：Gauss–Newton 數值解（程式有 JᵀJ）；正文不展開矩陣推導。\n"
        "盲走：d̂→∞ → 定位無解。不是新公式，是 Kapoor/Hayes 譜系。\n"
        "【文獻】Kapoor [2]；Hayes [1]；Meyes [11]。",
    ),
    (
        "5.4",
        "側向 r＝0.950（RMSE 3.3 cm）",
        "【口試】3.3 cm＞夾取窗±1.5 → 未宣稱 2D 夾取；g2-wide 1.84 止損（未入正文）。",
    ),
    (
        "5.4",
        "負結果界定問題，正結果回答問題",
        "【口試】4.3 證偽↔5.4 恢復；可宣稱合成側向，不可宣稱單次輸出含側向。",
    ),
    (
        "5.5",
        "三臂裡的盲走與開環對照都不能省",
        "【口試】盲走＝資訊因果；開環＝到達率陷阱。缺一可被鑽。",
    ),
    # ── 第六章 ────────────────────────────────────────────
    (
        "6.1",
        "不能只報告到達率，可由 D1.5 開環臂直接說明",
        "【口試・金句】開環高到達率＋r≈0＝指標失效現場演示；主指標必須 r＋消融。"
        "【文獻】Meyes 等 [11]；Nosek 等 [5]。",
    ),
    (
        "6.1",
        "同一框架也可推廣到其他模擬感測回授研究",
        "【口試・貢獻五】框架可推廣：預註冊、消融、行為主指標、稽核。",
    ),
    (
        "6.2",
        "推論範圍（可支持與不支持的結論）",
        "【口試・總表】可支持：1D 閉環、對位（D3 r3 正典 80%）、包絡、D2 合成側向、效度、"
        "D4 同場景串聯接口（對位～77%／升舉～74%，分層）。"
        "不及：摩擦夾持、單次側向、實機、0.32m 內閉環、跨 seed、2D 再夾取、pure-reward e2e。",
    ),
    (
        "6.2",
        "跨隨機種子與跨場景的統計穩健性",
        "【口試・Q3】在「推論不及」清單；低成本＝同判準多 seed 重跑。承認＋方案。",
    ),
    (
        "6.2",
        "二維定位後再夾取的完整鏈",
        "【口試】D2 定位／閉環已完成；側向 3.3 cm＞夾取窗 → 再夾取未入推論。",
    ),
    (
        "6.4",
        "6.4 研究結論",
        "【口試・收尾】逐題 RQ1–4；貢獻＝驗證鏈非新物理；正典 D3＝走廊修正複驗；"
        "D4 為延伸（執行器／串聯），不替換 r3。",
    ),
    (
        "6.3",
        "D2 已完成二維定位與閉環接近，但側向誤差 3.3 cm 仍大於夾取容差",
        "【口試】正文未來方向；實驗側 g2-wide 1.84 止損（未入正文）可作彈藥。",
    ),

    (
        "6.3",
        "滑動窗口對最近數步距離做圓交會",
        "【口試・延伸】動態追蹤＝路徑當視點；仍建議三臂。尚未做。",
    ),
    (
        "6.3",
        "各實驗已留存逐步波形與位姿（數百回合）",
        "【口試・ML】Stage3：E2 AUC=0.981；E3 R²=0.925；E1 解析法勝。分組 CV 防双胞胎。",
    ),
    (
        "6.3",
        "TDK CH201 等商用超音波測距等級的任務級驗證協定",
        "【口試・實機】任務級（包絡＋三臂），不是先比波形。對齊 Höfer。",
    ),
]


def qn(tag: str) -> str:
    if tag.startswith("{"):
        return tag
    prefix, local = tag.split(":") if ":" in tag else ("w", tag)
    ns = {
        "w": W_NS,
        "w14": W14,
        "w15": W15,
        "w16cid": W16CID,
        "w16cex": W16CEX,
        "r": R_NS,
        "ct": CT_NS,
        "pr": REL_NS,
    }[prefix]
    return f"{{{ns}}}{local}"


def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[-1] if tag.startswith("{") else tag


def write_default_ns_xml(path: Path, root: ET.Element, default_ns: str) -> None:
    """Serialize package parts that Word requires with a *default* xmlns (not ns0:).

    ElementTree.ET.write() rewrites default namespaces as ns0/ns1, which makes
    Microsoft Word and LibreOffice refuse to open the docx.
    """
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    root_name = _local_tag(root.tag)
    parts.append(f'<{root_name} xmlns="{default_ns}">')
    for child in root:
        name = _local_tag(child.tag)
        attrs = " ".join(f'{k}="{v}"' for k, v in child.attrib.items())
        if attrs:
            parts.append(f"<{name} {attrs}/>")
        else:
            parts.append(f"<{name}/>")
    parts.append(f"</{root_name}>")
    path.write_text("".join(parts), encoding="utf-8")


def fix_markup_compat_prefix(xml_path: Path) -> None:
    """Rewrite ElementTree's xmlns:ns1 markup-compat → mc: (cosmetic, safer for Word)."""
    text = xml_path.read_text(encoding="utf-8")
    if 'xmlns:ns1="' not in text or "markup-compatibility" not in text:
        return
    text = text.replace("xmlns:ns1=", "xmlns:mc=")
    # only replace prefix uses, not the URI string itself
    text = re.sub(r"(?<=[<\s])ns1:", "mc:", text)
    xml_path.write_text(text, encoding="utf-8")


def hex_id() -> str:
    return f"{random.randint(0, 0x7FFFFFFE):08X}"


def para_text(p: ET.Element) -> str:
    return "".join((t.text or "") for t in p.iter(qn("w:t")))


def ensure_comment_parts(word: Path, ct_path: Path, rels_path: Path) -> None:
    """Create empty comment parts + content types + relationships if missing."""
    templates = {
        "comments.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments xmlns:w="{W_NS}" xmlns:w14="{W14}" xmlns:w15="{W15}"/>
''',
        "commentsExtended.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w15:commentsEx xmlns:w15="{W15}" xmlns:w14="{W14}"/>
''',
        "commentsIds.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w16cid:commentsIds xmlns:w16cid="{W16CID}"/>
''',
        "commentsExtensible.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w16cex:commentsExtensible xmlns:w16cex="{W16CEX}"/>
''',
    }
    for name, body in templates.items():
        path = word / name
        if not path.exists():
            path.write_text(body, encoding="utf-8")

    # Content_Types
    ct = ET.parse(ct_path)
    root = ct.getroot()
    existing = {el.get("PartName") for el in root if el.tag.endswith("Override")}
    overrides = [
        ("/word/comments.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"),
        ("/word/commentsExtended.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml"),
        ("/word/commentsIds.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsIds+xml"),
        ("/word/commentsExtensible.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtensible+xml"),
    ]
    for part, ctype in overrides:
        if part not in existing:
            el = ET.SubElement(root, qn("ct:Override"))
            el.set("PartName", part)
            el.set("ContentType", ctype)
    # Must use default xmlns — ET.write emits ns0: which Word/LibreOffice reject.
    write_default_ns_xml(ct_path, root, CT_NS)

    # relationships
    rels = ET.parse(rels_path)
    rroot = rels.getroot()
    targets = {el.get("Target") for el in rroot}
    max_id = 0
    for el in rroot:
        rid = el.get("Id") or ""
        if rid.startswith("rId"):
            try:
                max_id = max(max_id, int(rid[3:]))
            except ValueError:
                pass
    rel_defs = [
        ("http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments", "comments.xml"),
        ("http://schemas.microsoft.com/office/2011/relationships/commentsExtended", "commentsExtended.xml"),
        ("http://schemas.microsoft.com/office/2016/09/relationships/commentsIds", "commentsIds.xml"),
        ("http://schemas.microsoft.com/office/2018/08/relationships/commentsExtensible", "commentsExtensible.xml"),
    ]
    for rtype, target in rel_defs:
        if target not in targets:
            max_id += 1
            el = ET.SubElement(rroot, qn("pr:Relationship"))
            el.set("Id", f"rId{max_id}")
            el.set("Type", rtype)
            el.set("Target", target)
    write_default_ns_xml(rels_path, rroot, REL_NS)


def append_comment_records(
    word: Path,
    cid: int,
    text: str,
    ts: str,
) -> str:
    """Append comment metadata; return para_id."""
    para_id = hex_id()
    durable = hex_id()

    # comments.xml
    cpath = word / "comments.xml"
    ctree = ET.parse(cpath)
    croot = ctree.getroot()
    comment = ET.SubElement(croot, qn("w:comment"))
    comment.set(qn("w:id"), str(cid))
    comment.set(qn("w:author"), AUTHOR)
    comment.set(qn("w:date"), ts)
    comment.set(qn("w:initials"), INITIALS)
    p = ET.SubElement(comment, qn("w:p"))
    p.set(qn("w14:paraId"), para_id)
    p.set(qn("w14:textId"), "77777777")
    r0 = ET.SubElement(p, qn("w:r"))
    rPr0 = ET.SubElement(r0, qn("w:rPr"))
    ET.SubElement(rPr0, qn("w:rStyle")).set(qn("w:val"), "CommentReference")
    ET.SubElement(r0, qn("w:annotationRef"))
    r1 = ET.SubElement(p, qn("w:r"))
    rPr1 = ET.SubElement(r1, qn("w:rPr"))
    ET.SubElement(rPr1, qn("w:color")).set(qn("w:val"), "000000")
    ET.SubElement(rPr1, qn("w:sz")).set(qn("w:val"), "20")
    ET.SubElement(rPr1, qn("w:szCs")).set(qn("w:val"), "20")
    t = ET.SubElement(r1, qn("w:t"))
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    ctree.write(cpath, encoding="UTF-8", xml_declaration=True)

    # commentsExtended
    epath = word / "commentsExtended.xml"
    etree = ET.parse(epath)
    eroot = etree.getroot()
    ex = ET.SubElement(eroot, qn("w15:commentEx"))
    ex.set(qn("w15:paraId"), para_id)
    ex.set(qn("w15:done"), "0")
    etree.write(epath, encoding="UTF-8", xml_declaration=True)

    # commentsIds
    ipath = word / "commentsIds.xml"
    itree = ET.parse(ipath)
    iroot = itree.getroot()
    iid = ET.SubElement(iroot, qn("w16cid:commentId"))
    iid.set(qn("w16cid:paraId"), para_id)
    iid.set(qn("w16cid:durableId"), durable)
    itree.write(ipath, encoding="UTF-8", xml_declaration=True)

    # commentsExtensible
    xpath = word / "commentsExtensible.xml"
    xtree = ET.parse(xpath)
    xroot = xtree.getroot()
    xe = ET.SubElement(xroot, qn("w16cex:commentExtensible"))
    xe.set(qn("w16cex:durableId"), durable)
    xe.set(qn("w16cex:dateUtc"), ts)
    xtree.write(xpath, encoding="UTF-8", xml_declaration=True)

    return para_id


def iter_run_text_nodes(p: ET.Element) -> list[tuple[ET.Element, ET.Element, str]]:
    """Return list of (run_element, t_element, text) in document order for direct children runs."""
    out = []
    for child in list(p):
        if child.tag != qn("w:r"):
            continue
        t_el = child.find(qn("w:t"))
        if t_el is None:
            continue
        out.append((child, t_el, t_el.text or ""))
    return out


def wrap_anchor_in_paragraph(p: ET.Element, anchor: str, cid: int) -> bool:
    """Insert comment markers around the first occurrence of anchor in paragraph runs.

    Works when anchor is contiguous across concatenated run texts.
    Returns True on success.
    """
    runs = iter_run_text_nodes(p)
    if not runs:
        # maybe text only in nested (hyperlinks etc.) — fallback: whole-paragraph markers
        return wrap_whole_paragraph(p, cid)

    full = "".join(t for _, _, t in runs)
    idx = full.find(anchor)
    if idx < 0:
        return False
    end = idx + len(anchor)

    # Map char offsets to run indices
    spans: list[tuple[int, int, int]] = []  # run_i, start_in_run, end_in_run
    pos = 0
    for i, (_, _, t) in enumerate(runs):
        a, b = pos, pos + len(t)
        if b <= idx or a >= end:
            pos = b
            continue
        sa = max(0, idx - a)
        sb = min(len(t), end - a)
        spans.append((i, sa, sb))
        pos = b

    if not spans:
        return False

    # Split boundary runs so that the annotated range is exact run sequences
    # Process from the end so earlier indices stay valid
    for run_i, sa, sb in reversed(spans):
        run, t_el, text = runs[run_i]
        if sa == 0 and sb == len(text):
            continue
        # Need to split this run into up to 3 pieces
        pieces = []
        if sa > 0:
            pieces.append(text[:sa])
        pieces.append(text[sa:sb])
        if sb < len(text):
            pieces.append(text[sb:])

        # Build new runs
        new_runs = []
        for j, piece in enumerate(pieces):
            if j == 0:
                t_el.text = piece
                if piece != piece.strip() or piece.startswith(" ") or piece.endswith(" "):
                    t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                new_runs.append(run)
            else:
                nr = copy.deepcopy(run)
                nt = nr.find(qn("w:t"))
                assert nt is not None
                nt.text = piece
                if piece.startswith(" ") or piece.endswith(" "):
                    nt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                # insert after previous
                # find current position of last inserted
                parent = p
                # insert relative to run currently at this conceptual place
                # We'll insert after `new_runs[-1]`
                prev = new_runs[-1]
                # find index of prev among p children
                children = list(parent)
                pi = children.index(prev)
                parent.insert(pi + 1, nr)
                new_runs.append(nr)

        # After split, re-fetch runs list for next reverse iteration? 
        # Because we reverse, earlier run_i still valid if we only split later runs.
        # But we modified later runs; earlier indices unchanged. Good.
        runs = iter_run_text_nodes(p)

    # Recompute spans after splits (anchor now exact multi-run contiguous)
    runs = iter_run_text_nodes(p)
    full = "".join(t for _, _, t in runs)
    idx = full.find(anchor)
    if idx < 0:
        return False
    end = idx + len(anchor)
    first_run_el = None
    last_run_el = None
    pos = 0
    for run, t_el, text in runs:
        a, b = pos, pos + len(text)
        if b <= idx or a >= end:
            pos = b
            continue
        if first_run_el is None:
            first_run_el = run
        last_run_el = run
        pos = b

    if first_run_el is None or last_run_el is None:
        return False

    children = list(p)
    fi = children.index(first_run_el)
    li = children.index(last_run_el)

    start = ET.Element(qn("w:commentRangeStart"))
    start.set(qn("w:id"), str(cid))
    end_el = ET.Element(qn("w:commentRangeEnd"))
    end_el.set(qn("w:id"), str(cid))
    ref_r = ET.Element(qn("w:r"))
    ref_rPr = ET.SubElement(ref_r, qn("w:rPr"))
    ET.SubElement(ref_rPr, qn("w:rStyle")).set(qn("w:val"), "CommentReference")
    ref = ET.SubElement(ref_r, qn("w:commentReference"))
    ref.set(qn("w:id"), str(cid))

    p.insert(fi, start)
    # after insert, last index shifts by 1
    children = list(p)
    li2 = children.index(last_run_el)
    p.insert(li2 + 1, end_el)
    children = list(p)
    ei = children.index(end_el)
    p.insert(ei + 1, ref_r)
    return True


def wrap_whole_paragraph(p: ET.Element, cid: int) -> bool:
    """Fallback: mark entire paragraph content."""
    children = list(p)
    # insert start after pPr if present
    insert_at = 0
    if children and children[0].tag == qn("w:pPr"):
        insert_at = 1
    start = ET.Element(qn("w:commentRangeStart"))
    start.set(qn("w:id"), str(cid))
    p.insert(insert_at, start)
    end_el = ET.Element(qn("w:commentRangeEnd"))
    end_el.set(qn("w:id"), str(cid))
    p.append(end_el)
    ref_r = ET.Element(qn("w:r"))
    ref_rPr = ET.SubElement(ref_r, qn("w:rPr"))
    ET.SubElement(ref_rPr, qn("w:rStyle")).set(qn("w:val"), "CommentReference")
    ref = ET.SubElement(ref_r, qn("w:commentReference"))
    ref.set(qn("w:id"), str(cid))
    p.append(ref_r)
    return True


def strip_existing_comments(word: Path, doc_root: ET.Element) -> None:
    """Remove previous sticky-note markers so re-run is idempotent."""
    body = doc_root.find(qn("w:body"))
    if body is None:
        return
    for p in body.iter(qn("w:p")):
        for el in list(p):
            if el.tag in (qn("w:commentRangeStart"), qn("w:commentRangeEnd")):
                p.remove(el)
            elif el.tag == qn("w:r"):
                if el.find(qn("w:commentReference")) is not None:
                    p.remove(el)
    # reset comment parts
    for name in (
        "comments.xml",
        "commentsExtended.xml",
        "commentsIds.xml",
        "commentsExtensible.xml",
    ):
        path = word / name
        if path.exists():
            path.unlink()


def pack_docx(unpacked: Path, out_docx: Path) -> None:
    if out_docx.exists():
        out_docx.unlink()
    with zipfile.ZipFile(out_docx, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(unpacked.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(unpacked).as_posix())


def apply(docx_path: Path, work: Path) -> list[tuple[int, str, str, str]]:
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    with zipfile.ZipFile(docx_path) as z:
        z.extractall(work)

    word = work / "word"
    doc_path = word / "document.xml"
    tree = ET.parse(doc_path)
    root = tree.getroot()
    strip_existing_comments(word, root)

    ensure_comment_parts(
        word,
        work / "[Content_Types].xml",
        word / "_rels" / "document.xml.rels",
    )

    body = root.find(qn("w:body"))
    assert body is not None
    paragraphs = [p for p in body if p.tag == qn("w:p")]
    # also tables
    for tbl in body.iter(qn("w:tbl")):
        for p in tbl.iter(qn("w:p")):
            paragraphs.append(p)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results: list[tuple[int, str, str, str]] = []
    failures: list[str] = []

    for cid, (chapter, anchor, note) in enumerate(NOTES):
        target_p = None
        for p in paragraphs:
            if anchor in para_text(p):
                target_p = p
                break
        if target_p is None:
            failures.append(f"[{chapter}] anchor not found: {anchor[:60]}")
            continue
        ok = wrap_anchor_in_paragraph(target_p, anchor, cid)
        if not ok:
            failures.append(f"[{chapter}] wrap failed: {anchor[:60]}")
            continue
        append_comment_records(word, cid, note, ts)
        results.append((cid, chapter, anchor, note))

    tree.write(doc_path, encoding="UTF-8", xml_declaration=True)
    fix_markup_compat_prefix(doc_path)

    if failures:
        print("FAILURES:")
        for f in failures:
            print(" ", f)
        raise SystemExit(f"{len(failures)} anchors failed; abort pack")

    pack_docx(work, docx_path)
    return results


def write_index(results: list[tuple[int, str, str, str]], path: Path) -> None:
    lines = [
        "# 論文口試便利貼索引（Word 註解同步清單）",
        "",
        f"> 產生時間：{datetime.now().isoformat(timespec='seconds')}",
        f"> 作者標記：`{AUTHOR}`（在 Word／LibreOffice 側邊註解顯示）",
        f"> 共 {len(results)} 則。正文未改；重建 docx 後請重跑 `python3 thesis/annotate_defense_sticky_notes.py`。",
        "",
        "| # | 章節 | 錨點（文中高亮） | 備註摘要 |",
        "|---|------|------------------|----------|",
    ]
    for cid, chapter, anchor, note in results:
        summary = note.replace("\n", " / ")
        if len(summary) > 120:
            summary = summary[:117] + "…"
        anc = anchor.replace("|", "\\|")
        if len(anc) > 40:
            anc = anc[:37] + "…"
        lines.append(f"| {cid} | {chapter} | `{anc}` | {summary} |")
    lines.append("")
    lines.append("## 使用方式")
    lines.append("")
    lines.append("1. 用 Word 或 LibreOffice 開啟 `thesis/THESIS_DRAFT_FCU_v2.docx`")
    lines.append("2. 開啟「註解／修訂」窗格，作者篩選「口試備註」")
    lines.append("3. 點註解即可跳到對應名詞／方法句")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--docx",
        type=Path,
        default=Path(__file__).resolve().parent / "THESIS_DRAFT_FCU_v2.docx",
    )
    ap.add_argument(
        "--work",
        type=Path,
        default=Path("/tmp/thesis_sticky_work"),
    )
    ap.add_argument(
        "--index",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "docs"
        / "plan_v2"
        / "THESIS_DEFENSE_STICKY_NOTES.md",
    )
    args = ap.parse_args()

    # backup once per run
    bak = args.docx.with_suffix(".docx.bak_before_sticky")
    if not bak.exists():
        shutil.copy2(args.docx, bak)
        print(f"backup → {bak}")

    results = apply(args.docx, args.work)
    write_index(results, args.index)
    print(f"OK: {len(results)} sticky notes → {args.docx}")
    print(f"index → {args.index}")


if __name__ == "__main__":
    main()
