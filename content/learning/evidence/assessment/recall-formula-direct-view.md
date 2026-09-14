# Recall 公式的原頁與定義對照

查核時間：2026-09-07T12:28:58Z。查核者 `/root/content_labs`（`agent-content-labs`），角色 `independent_model`；方法為本機原 PDF 直接轉成暫存頁圖後視覺閱讀，並以 PyMuPDF 讀取同頁文字。不是人類審閱，也沒有重跑 OCR 或修改任何 Guide/PDF。

原 PDF 路徑來自 `data/中級/toc_manifest.json` 的 `mid-s3` 科目：`data/中級/pdfs/AI應用規劃師(中級)-學習指引-科目3機器學習技術與應用_20251222101907.pdf`，整份原始 bytes hash 為 `sha256:cc4300a4133276509f34750313f65fd02e4bd1960366fc604f236f057719247a`。

查核位置為零起算 `pageIndex=154`，實體 PDF 第155頁、顯示頁碼 `5-21`。當頁 Recall 公式顯示分母 `TP+FP`；同頁文字定義是「實際正類樣本中，被正確預測為正類的比例」。按該定義，分母應由 TP 與 FN 組成。

既有版本化頁圖 `frontend/public/pdf-assets/中級/guide3/page_154/page.png` 與本次直接原 PDF 讀檢一致；其 raw hash 為 `sha256:f81f786305e8f4986883a6673d7ce88d7f41554b80b6fc21d356eb2823d96102`。本次另產生的暫存圖僅為讀檢工具輸入，不是新的來源權威。

既有 Track A `frontend/src/generated/guideContent/中級-guide3/mid-s3c9.json` 的 `block-77` 公式已是 `TP/(TP+FN)`；整份 artifact 的 raw hash 為 `sha256:263987fb931e9736a15bf16c4c1b3e94fec3d91d68d33ab601c7c16d77d06f37`。本次未修改該 block 或檔案。

獨立外部核對為 [scikit-learn recall_score 官方文件](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.recall_score.html)（查核日2026-09-07），其定義為 `tp / (tp + fn)`。本例 TP=12、FN=8，所以 recall=12/20=.60；TP+FP=30 的分母則是 precision=.40 的分母。

建議實務補充保留中性的原頁對照：「原 PDF 此頁公式分母顯示 TP+FP；本文依召回率定義使用 TP+FN。」這不是官方已發布勘誤的主張，也不回寫原始指引。十題凍結診斷與既有獨立算式皆使用正確分母，因此不需要更改題幹、答案或既有題稿審查紀錄；Unit 新增文字與 claim 必須重算其 contentHash，先前該 Unit 的正文 hash 不可當成新版本的正式批准。
