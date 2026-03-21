# Changelog

本文件記錄專案的重要變更，格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.0.0/)。

---

## [Unreleased]

## [0.2.0] - 2026-03-21

### 新增
- `README.md` 詳細記錄三支腳本的實作邏輯、JSON schema、f-string 雙括號規則，以及擴充中級的步驟
- `CHANGELOG.md`（本檔案）

### 變更
- **資料夾結構重組**：
  - 腳本從 `output/` 移至 `scripts/`
  - 原始 PDF 從根目錄移至 `data/初級/pdfs/`
  - 萃取結果移至 `data/初級/extracted/`，題庫移至 `data/初級/questions/`
  - 執行 log 移至 `logs/`
  - `data/<等級>/` 結構為後續擴充中級預留空間
- `scripts/extract_pdfs.py`：新增 `LEVEL` 變數，路徑改指 `data/初級/`；`main()` 加入 `OUT.mkdir()` 確保目錄存在
- `scripts/parse_exams_v2.py`：`OUT` 改指 `data/初級/`
- `scripts/build_web.py`：移除 `output/web/` 雙寫輸出，僅寫入 `docs/index.html`；log 路徑改指 `logs/`
- `.gitignore` 改為明確排除 `data/`、`logs/`，`scripts/`、`CLAUDE.md`、`AGENTS.md` 現納入版本控制
- `AGENTS.md`、`CLAUDE.md` 同步更新所有路徑參照

### 修復
- 章節練習題數量顯示為原文 `{ch.title}` / `{n}題`：Python f-string 中 JS template literal 插值須寫成 `${{variable}}` 才能輸出 `${variable}`

### 移除
- `output/parse_exams.py`（v1，已由 v2 取代）
- `output/web/index.html`（內容與 `docs/index.html` 相同，合併為單一輸出）

---

## [0.1.0] - 2026-03-21

### 新增
- PDF 萃取腳本 `extract_pdfs.py`：以 pdfplumber 為主、PyMuPDF 為備援，支援文字與表格提取
- 題庫解析腳本 `parse_exams_v2.py`：從表格 JSON 解析四選一選擇題，處理全形 A/B/C/D 正規化
- 網站建置腳本 `build_web.py`：將題庫 JSON 內嵌為 JS 常數，產生單一自包含 HTML
- `docs/index.html`：iPAS 初級備考平台，含章節練習、模擬考試、計時、成績解析功能，部署於 GitHub Pages
- 手機版 UI 改善：漢堡選單（drawer 式側欄）、overlay 遮罩、考試 header flex-wrap、表格水平捲動、觸控目標優化
- `CLAUDE.md`、`AGENTS.md`：記錄專案結構、建置指令與開發規範
