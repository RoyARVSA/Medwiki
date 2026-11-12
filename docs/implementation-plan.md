# Medwiki 第一版 Implementation Plan

**Goal:** 建立可持續維護的 wiki 與兩篇論文的學術藍色展示網站。
**Architecture:** Markdown 與 YAML 為內容來源，Jinja 版型與靜態 CSS/JS 為展示層，Python 白名單建置與成果索引。
**Tech Stack:** Python 3.11、PyYAML、Markdown、Jinja2、unittest；原件閱讀使用 pypdf/PyMuPDF。
**Spec:** design.md、../AGENTS.md。

## 執行順序

- [x] 1. 原件歸檔：Copy 原件、比對 SHA256、擷取全部頁面到 private/extracted；逐頁閱讀正文及圖表，建立來源與處理範圍。
- [x] 2. 內容：建立兩份來源紀錄與全文摘要、SJS/TEN 主題筆記、CQ、證據比較及 map；重要結論定位，保留衝突與缺口。
- [x] 3. 工具先測試：tests/test_pipeline.py 使用 temporary repo，驗證手動成果發現/改名/刪除/去重、私有檔排除、子路徑連結與失效引用；先執行 `python -m unittest discover -s tests -v` 確認未實作失敗。
- [x] 4. 實作 scripts/common.py、update_indexes.py、build_site.py、lint.py；輸入 root Path、輸出公開 HTML 與索引；用相同測試確認通過。
- [x] 5. 版型 templates、CSS、JS：完成入口、主題多頁、可收合三欄、手機返回、頁內目錄、搜尋/篩選、引用面板、圖放大、輕量動態；閱讀內容不依賴 JS。
- [x] 6. 文件/範本/CI：README、schema、workflow、04_templates、requirements、GitHub Actions（只配置、不推送或部署）。
- [x] 7. 建置與驗證：索引兩次雜湊一致、lint、unittest、白名單、HTTP、桌機/平板/手機瀏覽器驗證及截圖。以本機展示交付，回報未人工審閱與未上線。

## 邊界

只根據兩份原件，參考文獻及未提供補充檔不視為已讀；不外搜醫學內容。證據確定性引用原文，非本站另評；衝突 open/not_reviewed，不把診斷缺口填滿。資料夾/檔名全英文。沒有 Git repo 不執行 git init/commit/push；建立可部署檔案不代表已發布。

## 驗證結果

建置、14 項測試、lint、JS 語法、重建一致性與公開成品排除檢查完成。瀏覽器視覺/互動驗證受本機連線隔離與 file URL 政策阻擋，Task 7 的此部分仍未完成，未宣稱通過。獨立程式審查的五項具體問題已重現並修正，代理複查無剩餘阻擋。

## 線上驗證追加

2026-11-12：使用者授權發布後，GitHub Pages 已成功部署。透過公開 HTTPS 網址完成電腦、平板、手機排版與正文 18/17/17px 核對，引用、搜尋篩選、手機導航與 B/C 專注閱讀檢查。先前本機隔離限制仍成立，已不再阻擋本版線上驗證。
