# iPAS AI 應用規劃師備考平台

初級與中級共用的靜態備考網站。專案把官方學習指引、樣題與公告試題轉成可稽核的結構化資料，
再由 React/Vite 建成 GitHub Pages 網站。內容解析品質是核心：PDF 對章節、題號與圖片資產的對齊，
都必須先通過閘門才能發佈。

## 快速開始

需求：Python 3.11、[uv](https://docs.astral.sh/uv/)、Node.js 20。

```bash
uv sync
cd frontend && npm ci && cd ..
uv run playwright install chromium       # 第一次跑完整測試時安裝

cd frontend && npm run dev -- --host     # 開發伺服器
uv run python scripts/build_web.py        # 資源審核 + production build → docs/
uv run python tests/run_all.py            # 靜態、資料、build 與瀏覽器端到端閘門
```

`build_web.py --skip-audit` 只供本機快速迭代，該產物不可發佈。沒有瀏覽器環境時可先跑
`uv run python tests/run_all.py --skip-browser`，但不能用它取代合併前的完整驗收。

## 架構

```text
PDF / OCR
  ├─ Guide Track B ─→ canonical 出題講義 ─→ 題目生成／審核
  ├─ Guide Track A ─→ guideContent blocks ─→ 前端閱讀頁
  └─ Exam extraction ─→ 公告試題 JSON ─────→ 前端考試頁

toc_manifest.json + resource_catalog.json
  └─ Python pipeline 與 React loaders/navigation 共用 metadata

frontend/src + committed JSON/assets
  └─ Vite build ─→ docs/ ─→ GitHub Pages
```

主要目錄：

- `data/{level}/pdfs/`：來源 PDF；`level` 為 `初級` 或 `中級`。
- `data/{level}/`：抽取快取、講義與題庫產物；哪些檔案需提交以 playbook 為準。
- `scripts/`：Python 抽取、組裝、審核、匯出與 build 工具，路徑均由腳本位置解析。
- `frontend/`：React 19、TypeScript、Tailwind CSS v4、React Router 與 Zustand 前端。
- `frontend/src/generated/`、`frontend/public/`：已生成且目前隨版控發佈的前端資料與資產。
- `tests/`：資料契約、可攜性、pipeline 安全與 Playwright 端到端閘門。
- `docs/`：本機 build 產物，gitignored；正式站由 GitHub Actions 重建。

## 單一權威與資料所有權

| 資料 | 權威來源 | 消費者 |
|---|---|---|
| 科目／章節 | `scripts/build_manifest.py` → `data/{level}/toc_manifest.json` | 所有資料腳本與前端章節導覽 |
| 等級／考卷／資源 metadata | `data/resource_catalog.json` | Python 抽取、解析、驗證、摘要，以及前端 loaders／導覽 |
| 出題講義（Track B） | `parse_guides.py` → `subject{N}_guide.json` | audit、出題與小節切片；`supplement_guide_from_audit.py` 是刻意的 Track B 後處理 |
| 閱讀內容（Track A） | `export_guide_outline_data.py` → `frontend/src/generated/guideContent/` | Guide 閱讀頁 |
| Track A 出題參考快照 | `export_question_generation_data.py` → `subject{N}_reading_guide.json` | 比對／seed 用；不會覆寫 canonical Track B |

Guide 的兩條軌不可互換。Track B 由 OCR/Vision `pages_cache` 組成；缺少合格快取時
`parse_guides.py` 會停止，只有明確加 `--allow-regex-fallback` 才能產生帶來源標記的舊式結果。
Track A 則由逐頁版面抽取、清洗與 blocks 匯出，服務前端閱讀版面。

考卷與共用資源 metadata 不得再寫第二份常數表。初級 114 年兩份既有圖片目錄以 catalog 的
`legacyAssetKey` 保留 `exam1`／`exam2` 相容性；中級 114 年資產已使用 canonical key。
`gemini_exam_vision_extract.py` 只產生稽核 sidecar，正式題庫仍由 `extract_pdfs.py` →
`parse_exams_v2.py` 建立。

## Pipeline 與安全操作

完整命令、重跑順序、輸出與 s1c2/s1c4/s2c3 deterministic publication overlays 只維護在
[`playbook/pipeline-reference.md`](playbook/pipeline-reference.md)。執行 pipeline 前也要讀：

- [`CLAUDE.md`](CLAUDE.md)：不變量與文件路由。
- [`playbook/pipeline-reference.md`](playbook/pipeline-reference.md)：唯一的腳本操作手冊。
- [`tests/README.md`](tests/README.md)：驗收範圍與端到端測試設計。
- [`playbook/04-maintenance.md`](playbook/04-maintenance.md)：修改權威文件的備份與 read-back 程序。

幾個不能跳過的原則：

- 凡提供 `--level` 的 pipeline 命令都顯式指定；不同腳本預設值並不一致。
- `export_guide_outline_data.py` 現在會在 staging 完成驗證，再原子替換並可回復；單等級匯出也會
  保留另一等級。常規完整重跑仍依不變量使用 `--all-levels`；exporter 會在 staged candidate
  套用並驗 Track A 169＋3＋3，`apply_manual_guide_fixes.py` 僅為 optional compatibility check，
  標準輸出預期 0 change。
- `export_pdf_image_gallery.py` 的單等級匯出會合併既有 manifest，不再抹掉另一等級。
- 動資料 pipeline 後至少跑對應等級的 `verify_data_alignment.py`；動前端或資料 JSON 後必須 build；
  動執行時行為則跑完整 `tests/run_all.py`。

## CI 與靜態資產

`.github/workflows/deploy.yml` 在 pull request 與 `main` push 先跑完整 quality job；只有 `main`
通過後才 build 與 deploy。正式 build 使用 `build_web.py`，因此資源審核不是可繞過的旁路。

大型 `pdf-assets/` 與 `images/` 目前仍在本 repo，尚未宣告完成外部搬遷。若日後上傳到物件儲存：

```bash
python scripts/publish_assets.py --dry-run
python scripts/publish_assets.py
python scripts/verify_r2_assets.py --base https://assets.example.com
```

必須讓最後一支命令對所有引用做完整 HEAD 驗證後，才能在 GitHub Repository Variables 設定
`VITE_ASSET_BASE_URL`。設定後前端 URL 會指向外部資產站，Vite 改用 `frontend/public-shell/`，
Pages artifact 才會由 400+ MB 的完整 public 內容降為 app-only；未設定時維持現行本地資產模式。

## 開發約定

Python 使用 4-space、`snake_case` 與 `Path`；測試放在 `tests/test_*.py`。不要手改 derived JSON，
除非是有意識的內容策展並在 commit 說明。Commit subject 採祈使句加 scope，例如
`parser: preserve exam asset aliases`。
