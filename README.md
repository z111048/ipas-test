# iPAS AI 備考頁面

這個版本是給 GitHub Pages 使用的靜態閱讀站。

## GitHub Pages

1. 建立 GitHub repo
2. 把目前目錄推上去
3. 到 GitHub repo 的 `Settings` -> `Pages`
4. `Build and deployment` 選 `Deploy from a branch`
5. Branch 選 `main`，Folder 選 `/docs`
6. 儲存後等待 GitHub 發布

Pages 會讀取 `docs/index.html`。

## 內容說明

- `docs/index.html`: GitHub Pages 站點
- `docs/.nojekyll`: 避免 GitHub Pages 套用 Jekyll 處理

## 本機更新

如果你之後還在本機維護題庫與產生流程，可執行：

```bash
python3 output/build_web.py
```

這會同步更新：

- `output/web/index.html`
- `docs/index.html`
