# Experiment: Document Parsing, Chunking, and the Index Pipeline

RAG-10 比較固定字元、逐層拆分和章節切塊。原本的假設是，沿文件邊界切會保留更多可用段落，並提升檢索分數。對照組是 RAG-9 的 500 字元、重疊 80。

這輪沿用原本的 100 篇 PEP、30 題及詞頻 cosine。每塊的詞頻向量先寫入 SQLite 倒排索引，搜尋時用共同詞的計數計算精確 cosine。比較和匯入都在本機執行。題庫標註的是文件 ID，Recall@5 計算前五個 chunk 覆蓋多少相關文件，MRR@5 只看第一個相關 chunk。兩題無答案題保留搜尋結果，有標註的 28 題用來計分。

## 重跑

```bash
uv sync --locked --group dev
uv run pytest -q
uv run python -m experiments.e02_ingestion.run compare
```

`compare` 建六個獨立索引，輸出 `results/metrics.json` 和 `results/questions.json`。要保存另外一輪，加上 `--output <directory>`。

以下命令把索引留在本機，方便查看命中的原文與來源資料。

```bash
uv run python -m experiments.e02_ingestion.run ingest --index .venv/rag10.sqlite3
uv run python -m experiments.e02_ingestion.run search --index .venv/rag10.sqlite3 "What is a docstring?"
```

預設是 `section`、本文上限 500 字元、重疊 0。要用基準設定，指定 `--strategy fixed --size 500 --overlap 80`，並使用另一個 SQLite 檔案。同一個索引保留建庫設定，避免把不同切法的資料混在一起。

## 匯入、更新與來源資料

使用 `--corpus <directory>` 指向自己的文件資料夾。支援 UTF-8 的 TXT、RST、Markdown、HTML，以及有文字層的 PDF。目錄可放 `MANIFEST.txt`，每行列出一個相對路徑，順序同時作為同分排序依據。省略清單時，依路徑排序讀取支援的文件。

Markdown、HTML 的標題、表格列與程式碼各自保留為區塊。RST 辨認 PEP 常用的下劃線標題，保留原本的文字及縮排。PDF 解析使用頁面座標、字體和表格框線，以單欄文字、一般章節及有框線表格為主要範圍。掃描頁需要 OCR，複雜多欄與無框線表格需要適用的版面規則。PDF 的頁碼是從 1 開始的實體頁序。解析介面可參考 [pdfplumber](https://github.com/jsvine/pdfplumber#extracting-text)、[markdown-it-py](https://markdown-it-py.readthedocs.io/en/latest/using.html) 和 [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)。

可選的 `metadata.json` 以相對路徑為鍵，例如：

```json
{
  "return.md": {
    "source_id": "return-policy",
    "version": "v4",
    "updated_at": "2026-11-06T09:00:00+08:00",
    "permissions": ["support"]
  }
}
```

預設以相對路徑作為來源 ID、原檔 SHA-256 作為版本、檔案修改時間作為更新時間。每個搜尋結果會帶回來源、版本、章節、頁碼、更新時間和權限標籤。權限標籤供後續過濾使用，目前的本機搜尋會查詢整個索引。偏移量指整理後的原文位置。

重跑同一個 `ingest` 即可更新。原檔相同時沿用解析結果；原檔不同但整理後文字和結構相同時，只更新來源資料。內容或結構變動時，重新建立該來源的 chunks 和詞頻索引。每次匯入使用一個交易，解析失敗時保留先前完整狀態。

```bash
uv run python -m experiments.e02_ingestion.run delete --index .venv/rag10.sqlite3 return-policy
```

`delete` 依來源 ID 移除索引資料。原始檔案有刪除時，也可對完整來源清單執行 `ingest --prune`，同步移除清單裡已不存在的來源。

## 切法和結果

三種策略的本文上限都是 500 字元。固定切法用精確字元數重疊；逐層與章節切法以 80 字元為重疊上限，只重用放得下的完整單位。章節切法也會在分開的塊上帶回章節標籤，因此連同標籤的文字可能超過 500 字元。

| 策略 | 怎樣選邊界 |
|---|---|
| Fixed | 每 500 個字元切一次 |
| Recursive | 先試段落，太長再依換行、空白和字元拆開 |
| Section | 先分章節，再組合各章節的段落、表格列或程式碼。過長的區塊再細拆 |

2026-11-06，本機建庫及查詢結果。建庫時間包含讀檔、解析、計算詞頻及寫入 SQLite。

| 策略 | 重疊上限 | Chunk 數 | Recall@5 | MRR@5 | 建庫 ms | SQLite MiB | 查詢 P50 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| Fixed | 0 | 2,453 | 0.643 | 0.533 | 687 | 5.47 | 8.3 |
| Fixed，RAG-9 基準 | 80 | 2,890 | 0.679 | 0.571 | 767 | 6.52 | 9.6 |
| Recursive | 0 | 3,016 | 0.661 | 0.574 | 722 | 5.64 | 8.6 |
| Recursive | 80 | 3,186 | 0.589 | 0.527 | 720 | 5.97 | 9.4 |
| Section | 0 | 3,423 | 0.679 | 0.571 | 715 | 5.99 | 9.2 |
| Section | 80 | 3,537 | 0.643 | 0.554 | 769 | 6.23 | 10.1 |

固定 500／80 的 30 題排名、分數和原文位置，與 RAG-9 的保存結果逐筆一致。Section／0 的兩項總分與基準相同，索引小約 8.1%，也保留了章節。這組成為新 CLI 的預設。Recursive／0 的 MRR 略高，但 Recall 較低。把重疊上限提高到 80，固定切法的分數上升，其他兩種切法的分數下降。

第 28 題要找 Unicode interpreter 和 Windows 檔名。Section／0 仍把 PEP 100 的 `References` 排在第 2 名。文件 ID 命中，段落仍不足以說明 interpreter 設計。這輪使用文件 ID 計分，因此需要一起看逐題的章節和位置。

## 解析和切塊驗收

`results/parsing_cases.json` 保存八個例子的原始抽取與修正結果。下表的「原本」對應各案例記錄的抽取方法。

| 案例 | 原本 | 修正結果 |
|---|---|---|
| PDF 跨行標題 | Return、policy 兩行 | 合成一個 Return policy 章節標籤 |
| PDF 版面換行 | returned 與 within 14 days 分行 | 保留為同一段完整句子 |
| PDF 有框線表格 | Sale 和 No returns 只有位置關係 | 同一列保留 Category 和 Window 欄名 |
| PDF 程式碼 | 普通文字抽取遺失行首位置 | 從等寬字體的水平位置還原四格縮排，保留第 2 頁 |
| Markdown fenced code | 全文壓空白會消除縮排與空行 | 解析程式碼區塊後保留縮排與空行 |
| Markdown 表格 | 直接按每個管線字元切分會拆錯儲存格 | `a \| b` 保留在 Example 欄 |
| HTML 跨列儲存格 | 最後一列只剩費用 150 | 延續上一列的 Region: Taipei |
| RST 相鄰章節 | 固定切法把一般與特價規則放在同一塊 | 章節切法保留各自標題及規則 |

42 個測試通過。正常 CLI 混合匯入 Markdown、HTML 和 PDF 共三份文件，重跑後沿用三份資料，寫入的新向量數為 0。改動一份後只重建一份，刪除指定來源後 SQLite 完整性檢查通過。另用 repo 內的論文試讀 19 個有文字的頁面，核對第一頁跨行標題。

六組重跑共 180 個查詢的排名、位置與分數一致。完整測試記錄及結果檔 SHA-256 見 `results/acceptance.json`。
