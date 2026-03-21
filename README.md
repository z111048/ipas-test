# iPAS AI 應用規劃師備考平台

針對 iPAS AI 應用規劃師能力鑑定（初級）的靜態備考網站，部署於 GitHub Pages。

---

## 目錄結構

```
ipas-test/
├── scripts/                    # 資料處理腳本
│   ├── extract_pdfs.py         # PDF → 文字/JSON
│   ├── parse_exams_v2.py       # JSON 表格 → 題庫 JSON
│   └── build_web.py            # 題庫 JSON → docs/index.html
├── data/
│   └── 初級/                   # 初級題庫資料（gitignore）
│       ├── pdfs/               # 原始 PDF 來源
│       ├── extracted/          # 從 PDF 萃取的文字與結構（.txt / .json）
│       ├── questions/          # 題庫 JSON（mock_exam*.json、subject*_questions.json）
│       └── analysis/           # 分析輸出
├── logs/                       # 執行 log（gitignore）
└── docs/                       # GitHub Pages 網站（index.html 為唯一輸出）
```

> 後續擴充中級時，在 `data/` 下新增 `中級/` 資料夾，依相同結構組織 PDF 與題庫，並於 `scripts/` 中以 `LEVEL = '中級'` 切換或建立獨立腳本。

---

## 執行 Pipeline

從專案根目錄依序執行：

```bash
python3 scripts/extract_pdfs.py      # 萃取 PDF → data/初級/extracted/
python3 scripts/parse_exams_v2.py    # 解析題庫 → data/初級/questions/
python3 scripts/build_web.py         # 建置網站 → docs/index.html
```

僅更新網頁 UI（題庫不變）時只需執行最後一步。

依賴套件：

```bash
pip install pdfplumber pymupdf
```

---

## 腳本實作說明

### `scripts/extract_pdfs.py`

以 `pdfplumber` 為主要 PDF 解析器，`PyMuPDF`（`fitz`）為備援。

**提取流程：**
1. `extract_with_pdfplumber(pdf_path)` — 使用 `x_tolerance=3, y_tolerance=3` 提取文字，另以 `extract_tables()` 提取表格結構（list of list of str）。若 pdfplumber 無法取得任何文字，退回 `extract_with_pymupdf()`。
2. 每頁輸出一個 dict：`{page, text, tables, width, height}`。
3. 每份 PDF 同時存成 `.txt`（供人工閱覽）與 `.json`（供後續程式解析）。

**鍵名對應（`PDFS` dict）：**

| 鍵 | 說明 |
|---|---|
| `guide1` | 科目一學習指引 |
| `guide2` | 科目二學習指引 |
| `exam1` | 科目一公告試題 |
| `exam2` | 科目二公告試題 |
| `sample` | 考試樣題（114 年 9 月版） |

擴充其他年度或等級時，在 `PDFS` dict 新增鍵值，並更新 `LEVEL` 變數（目前為 `'初級'`）。

---

### `scripts/parse_exams_v2.py`

從 `extracted/*.json` 的表格資料解析選擇題。

**表格格式假設：**
- 公告試題（exam1/exam2）：每列 `[答案, 題目全文]`，答案欄為 A/B/C/D（含全形 Ａ/Ｂ/Ｃ/Ｄ，以 `FW_MAP` 正規化）。
- 樣題（sample）：每列有 8 個以上欄位，程式尋找符合 `[ABCD]` 的欄位作為答案，並尋找包含 `(A)` 且長度 > 10 的欄位作為題目全文。

**`parse_question_cell()` 解析邏輯：**
1. 移除嵌入的題號（`\n1.\n` 等格式）。
2. 以 regex `\(([A-D])\)(.*?)(?=\([A-D]\)|\Z)` 提取四個選項。
3. 第一個 `(A)` 之前的文字為題幹。
4. 少於 4 個選項的資料列直接丟棄。

**輸出 JSON 格式（題目）：**

```json
{
  "id": "exam1_q1",
  "question": "題幹文字",
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "answer": "B",
  "explanation": "正確答案為(B)。",
  "source": "exam1"
}
```

**輸出 JSON 格式（模擬考試 `mock_exam*.json`）：**

```json
{
  "exam": "科目一 模擬考試：...",
  "total": 50,
  "time_limit": "90分鐘",
  "passing_score": 60,
  "questions": [/* 題目陣列 */]
}
```

`subject*_questions.json` 額外以章節分組，格式見 `build_web.py` 中的 `SUBJECT1_QUESTIONS` / `SUBJECT2_QUESTIONS`。

---

### `scripts/build_web.py`

將所有題庫 JSON 內嵌為 JavaScript 常數，產生單一自包含的 `docs/index.html`（無外部依賴）。

**讀取的檔案：**

```
data/初級/questions/
├── subject1_questions.json   → JS 常數 SUBJECT1_QUESTIONS
├── subject2_questions.json   → JS 常數 SUBJECT2_QUESTIONS
├── mock_exam1.json           → JS 常數 MOCK_EXAM1
├── mock_exam2.json           → JS 常數 MOCK_EXAM2
└── sample_exam.json          → JS 常數 SAMPLE_EXAM
```

**注意事項：** 整個 HTML/CSS/JS 以 Python f-string 組合，大括號需雙寫（`{{`、`}}`）才能輸出字面量 `{`、`}`。JavaScript template literal 的插值語法在 Python 原始碼中須寫成 `${{variable}}`，才能在輸出的 JS 中產生 `${variable}`。

---

## GitHub Pages 部署

1. 建立 GitHub repo，將本目錄推上 `main` branch。
2. `Settings → Pages → Deploy from branch`，選 `main`，Folder 選 `/docs`。
3. 每次執行 `python3 scripts/build_web.py` 並 push `docs/index.html` 後即自動更新。

---

## 擴充為中級

1. 在 `data/中級/pdfs/` 放入中級 PDF。
2. 複製並修改 `scripts/extract_pdfs.py`，將 `LEVEL = '初級'` 改為 `LEVEL = '中級'`，更新 `PDFS` 對應新檔名。
3. 解析腳本同步修改 `OUT` 路徑。
4. 在 `scripts/build_web.py` 載入中級題庫並加入網頁 UI。
