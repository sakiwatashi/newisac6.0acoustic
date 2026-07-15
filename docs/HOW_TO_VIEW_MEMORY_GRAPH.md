# 如何查看「B 種乾淨」記憶連線圖

## 1. 這張圖裡有什麼／沒有什麼

| 項目 | 說明 |
|------|------|
| **專案名（在 UI 裡選這個）** | `home-lab109-song-isaacsim6.0_v2_memory` |
| **本機路徑** | `/home/lab109/song/isaacsim6.0_v2_memory` |
| **有** | V2 runner/analyzer、plan_v2 報告、HANDOFF、論文腳本、文獻 PDF/清單、實驗 summary/json |
| **沒有** | 其他 Git 專案、舊 `isaac_acoustic_research`、整包 `clean/`、official_asset 舊管線、IsaacLab/app、大量波形 |

主實驗程式仍在：`/home/lab109/song/isaacsim6.0`（請繼續在這裡改 code／論文）。  
`_v2_memory` 只是 **給記憶圖用的精簡鏡像**。

規模：約 **3645 節點 / 9238 連線**（舊整包 index 約 1.2 萬節點已刪除）。

---

## 2. 開瀏覽器多連線圖（演示那種）

### 啟動伺服器（本機已可用含 UI 的二進位）

```bash
# 若 9749 尚未在聽：
sleep infinity | /home/lab109/.local/bin/codebase-memory-mcp-ui --ui=true --port=9749 &
```

> 注意：必須用 **`codebase-memory-mcp-ui`**（含圖形前端）。  
> 舊的 `codebase-memory-mcp` 可能是無 UI 版。  
> 且程序會跑 MCP 迴圈，**stdin 不能立刻關掉**（所以用 `sleep infinity |`）。

### 開網頁

瀏覽器進入：

**http://127.0.0.1:9749/**

在專案列表選：

**`home-lab109-song-isaacsim6.0_v2_memory`**

不要選：

- `home-lab109-song-isaac_acoustic_research`（舊專案）
- TTS / pyroom 等

然後即可拖曳、點節點看 CALLS／DEFINES 等多連線。

### 關掉伺服器

```bash
# 查 PID
ss -ltnp | grep 9749
# 或
ps aux | grep codebase-memory-mcp-ui | grep -v grep
kill <PID>
```

---

## 3. 不用圖、用指令查（確認沒混舊的）

```bash
# 應只看到 v2_memory 與其他「各自獨立」的專案，沒有整包 isaacsim6.0
codebase-memory-mcp-ui cli list_projects '{}'

# 應找得到 D2
codebase-memory-mcp-ui cli search_graph \
  '{"project":"home-lab109-song-isaacsim6.0_v2_memory","query":"d2v2_formal"}'

# 舊管線應 0 筆
codebase-memory-mcp-ui cli search_graph \
  '{"project":"home-lab109-song-isaacsim6.0_v2_memory","query":"official_asset"}'
```

---

## 4. 主專案改完後如何更新圖

```bash
# 1) 再同步一次精簡目錄（之後可做成腳本）
# 2) 重 index：
codebase-memory-mcp-ui cli index_repository \
  '{"repo_path":"/home/lab109/song/isaacsim6.0_v2_memory","mode":"full"}'
```

---

## 5. 其他專案索引

機器上仍可能有 TTS、pyroom、acoustic_research 的 **獨立 DB**，  
**不會自動併入** v2_memory 圖。只要 UI 裡選對專案名即可。  
若要完全刪掉舊專案記憶：

```bash
codebase-memory-mcp-ui cli delete_project '{"project":"home-lab109-song-isaac_acoustic_research"}'
# 其他同理
```
