# MVP 實作進度

本頁追蹤實際實作；架構藍圖與驗收條件見 [implementation-plan.md](implementation-plan.md)。
使用者於 2026-09-07 確認本輪範圍為 P0→P1 的第一條完整 MVP。
本機 MVP 已完成；正式發布仍保留真人 Colab L5 閘門。

## 已驗證基線

- 起始 commit：`e35a312`。
- 開工前已存在的 README／specifications 變更來自前輪規劃，予以保留。
- 完整既有驗收：13/13 通過，exit 0。
- 沙箱內瀏覽器建立 socket 受限；取得執行許可後，於本機完整重跑通過，未以略過瀏覽器替代。
- 詳細盤點與命令證據由 [baseline.md](baseline.md) 保存。

## 目前工作

| 工作包 | 狀態 | 完成證據 |
|---|---|---|
| LP-000 基線 | 完成 | baseline.md 與原有 13 項完整驗收 |
| LP-010 契約與型別 | 完成 | 8 組 JSON Schema、Python validator、型別；10 項測試通過，含三種惡形資料不崩潰反例 |
| LP-020 引用解析 | 完成 | 10 項引用測例通過；最終候選驗證 128 份文件、issues 為空 |
| LP-120 候選建置／發布閘門 | 完成 | 12 項發布測例通過；無 staging 重建及連跑兩次 byte-identical；正式產物無候選正文與 Lab 資產 |
| LP-110／140 教材與 Lab | L0–L4 通過，L5 真人 Colab 待完成 | 修正版 6 項測試通過；L4 獨立 kernel 15.852 秒、八種竄改全拒絕、400 筆測試真值與兩組 19 列成本表核對 |
| LP-150／165／170 來源題與診斷 | 獨立內容與組卷評審通過 | 10 題以 3／4／3 分配；原科目 102 題與 cards 保留、追加為 112 題；官方選讀 5／150 題；非作者覆核 21／21 通過 |
| LP-130／160／180 前端與學習紀錄 | 本機 MVP 完成 | 獨立 state 15 checks 通過；真操作涵蓋 10 題／90 分、精確回補、五檔 filename/hash、375px 鍵盤、未知／載入失敗／逾時；console 為空 |
| LP-190 整合驗收 | 本機完整驗收完成 | 非作者執行 20／20 PASS、exit 0、679 秒；包含舊 13 項與新 7 項，未省略瀏覽器 |

本機重建與操作方式見 [mvp-runbook.md](mvp-runbook.md)；教材與診斷題的獨立審查見 [content-review.md](content-review.md)。
最終獨立驗收見 [acceptance.md](acceptance.md)；完整測試包含 production build、初級／中級 alignment、既有三項與新增兩項瀏覽器驗收。

最終候選為 `learning-e6732041208784d31304146c`。已完成的 17 項審查均已補齊真實正式紀錄；
`unmetReviews` 只剩 Lab 的真人 L5，`invalidReviews` 為空；沒有正式 `current.json`。
正式模式的 `build_learning_content.py --check` 如預期 exit 1，只因缺少 L5 而阻擋，沒有寫入發布指標。

## 預覽與發布邊界

本機開發預覽使用獨立 candidate 與 preview 指標，不能寫入 production current 指標。
預覽仍須通過資料結構、來源引用與雜湊驗證，並列出未完成的審查項目。
Lab 的人類 Colab 走查、可解析的 GitHub commit 連結及正式發布驗收尚未完成，不能假簽。
未公開的 notebook 提供本機／手動上傳 Colab 的方式；不建立指向不存在 GitHub 檔案的連結。
本輪不重試前次被拒絕的 Claude 外送，也不修改權限設定繞過限制。
