# MVP 本機操作

這是第一條實務學習流程的開發預覽。實際驗收結果與發布缺口以 [progress.md](progress.md) 為準。
正式網站目前不會載入這批預覽內容。

在專案根目錄執行：

```bash
uv sync
uv run python scripts/build_learning_content.py --preview
cd frontend
npm ci
npm run dev -- --host
```

開啟 <http://localhost:5173/#/learn>。若 Vite 顯示其他 port，使用終端機列出的網址並加上 `#/learn`。

1. 從中級「模型訓練、評估與驗證」指引進入實務補充，閱讀資料切分、類別不平衡與閾值決策三單元。
2. 開啟「專題實作」，依步驟整理模型評估與決策成果。
3. 進入診斷模擬完成十題，查看對應單元與 Lab 的回饋；作答紀錄保存在本機瀏覽器。
4. 在考題分析查看五題官方考題選讀與來源；這是有限策展樣本，不能代表全部歷屆趨勢。
5. 到 Lab 頁下載練習版或解答版 `.ipynb`，以及 CSV、split manifest；在 Google Colab 開啟 notebook，再把 CSV 與 split manifest 上傳至目前工作目錄後依序執行。開啟或下載不等於完成；完成狀態採使用者自報。

新增十題已經獨立審查並策展進原題庫；一般啟動不需再次執行策展或建立審查紀錄。
必要來源保存在 `content/learning/`、`notebooks/labs/` 與既有題庫，暫存 run 目錄可由上述命令重建。

以下命令也在專案根目錄執行：

```bash
uv run --group learning-lab python scripts/verify_learning_labs.py --lab lab-imbalanced-classification --profile cpu --check
uv run python tests/run_all.py
```

Notebook 驗證需要可建立本機 Jupyter socket；瀏覽器測試需要 Playwright Chromium。
維護 Lab 來源或重建合成資料時，另用 `uv run --group learning-lab python scripts/generate_learning_lab.py --check` 檢查重建差異。
Lab 已有本機執行證據；真人 Colab 走查與可解析的已發布 notebook commit 仍待完成。
預覽使用獨立指標與資產目錄，不更新正式 `current.json`，也不代表網站已部署。
