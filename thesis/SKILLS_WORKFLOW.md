# 論文 Skills 工作流（已安裝）

**Repo 位置：**
- PaperSpine: `/home/lab109/song/tools/PaperSpine`
- AERS（精選子 skill）: `/home/lab109/song/tools/Auto-Empirical-Research-Skills`
- Grok 專案 skill 連結: `/home/lab109/song/.grok/skills/`

---

## 建議用法（你的碩論）

| 階段 | 用哪個 skill | 做什麼 |
|------|-------------|--------|
| 1. 素材盤點 | `paper-spine-intake` | 讀 `paper_spine_config.json` |
| 2. 找文獻 | `paper-spine-citation` + `deep-research` / `openalex` | 建 `citation_support_bank.md` |
| 3. 從素材寫正文 | `paper-spine-build` | §3.9–§4.7 從 `thesis/*.md` 組裝 |
| 4. 複現包 | `aer-replication` | 對照 `REPLICATION_PACKAGE.md` |
| 5. 口試前審稿 | `academic-paper-reviewer` | 5 視角模擬審查 |
| 6. 貼 Word | `docx` skill | 更新 `THESIS_DRAFT_FCU_v1.docx` |

**不必** clone 整個 AERS（1145 skills）；已精選安裝 10 個。

---

## 對 Grok 說的話（複製即用）

### 文獻 + citation bank
```
用 paper-spine-citation 和 deep-research，以 local_first 讀 isaacsim6.0/thesis/，
主題是 UR10 RTX Acoustic + Isaac Sim/Lab 距離感知，輸出 citation_support_bank.md
到 isaacsim6.0/thesis/paper_rewriting_output/
```

### 從素材建章節
```
用 paper-spine-build，materials_dir=isaacsim6.0/thesis，
依 paper_spine_config.json 把 THESIS_LAB_SECTIONS 和 THESIS_PHASE5_INSIM_RL
整合成逢甲 13b 格式章節藍圖與 writing_rationale_matrix
```

### 模擬審稿
```
用 academic-paper-reviewer 審查 isaacsim6.0/thesis/THESIS_DRAFT_FCU_v1.docx 的
第二章文獻與第四章 claim boundary
```

---

## 更新 skills

```bash
cd /home/lab109/song/tools/PaperSpine && git pull
cd /home/lab109/song/tools/Auto-Empirical-Research-Skills && git pull
```