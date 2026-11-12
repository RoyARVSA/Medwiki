# Medwiki

以 Markdown 累積醫學知識，以靜態網站閱讀、比較與展示。繁體中文內容、英文檔名。完整協作規則見 [AGENTS.md](AGENTS.md)。

## 開始閱讀

- [線上網站](https://royarvsa.github.io/Medwiki/)
- [內頁版型比較](https://royarvsa.github.io/Medwiki/03_outputs/web/layout-previews/index.html)：三種設計使用相同內容，正式內頁暫不替換。

- [網站首頁](index.html)：學術藍色知識入口、完成成果與待加入區。
- [SJS/TEN 學習專題](03_outputs/web/sjs-ten/index.html)。
- [全部 wiki 索引](index.md)：適合 Obsidian。
- [皮膚科學習路徑](01_wiki/maps/dermatology.md)。

網站支援直接以瀏覽器開啟本機 index.html，搜尋資料已內嵌，不需連線或 API。檔案在 GitHub 原始碼頁不會直接執行；GitHub Pages 設定後才有正式網站網址。

## 建置與檢查

Python 3.11 或以上，在專案根目錄執行：

```powershell
python -m pip install --target .build/deps -r requirements.txt
python scripts/build_site.py
python scripts/lint.py
python -m unittest discover -s tests -v
```

工具優先使用專案 `.build/deps`，未存在則使用執行環境已安裝的依賴。CI 依 requirements 安裝。

`python scripts/update_indexes.py` 同樣執行完整索引更新與網站建置。公開成品在 `.build/site/`，根目錄 index.html 與指定成果同步更新。建置先檢查再替換舊網站。

一般本機環境可啟動：

```powershell
python -m http.server 8000 --bind 127.0.0.1 --directory .build/site
```

瀏覽器開啟 `http://127.0.0.1:8000/`。本次 agent 執行環境對本機連線有隔離限制；已改由公開 Pages 網址完成電腦、平板與手機的閱讀、引用、搜尋及版型檢查，不需停用系統防火牆。直接開啟 HTML 仍可離線閱讀。

## 加入資料

- 新來源先放 `00_inbox/`，告訴 agent 要處理的範圍。
- 原始筆記在 `private/notes/`；去識別病例在 `private/cases/`。
- 原始 PDF 歸檔至 `02_sources/raw/<source-id>/`，不公開。
- 書目與處理範圍在 `02_sources/records/`，摘要在 `summaries/`。
- 主題內容在 `01_wiki/`，重要結論保留頁次引用。

目前完成兩份 PDF 的閱讀與整理，人工審閱尚未完成。已記錄國際/日本分型、類固醇證據及原文數據等差異；缺少的補充檔與個別原始研究不視為已讀。

## 加入網頁或簡報

手動 HTML 放 `03_outputs/web/<topic>/`，PDF/PPTX 放 `03_outputs/slides/<topic>/`，執行更新即可被首頁收錄。不需先填 metadata，assets/ 裡的支援頁不列成果。來源圖先依可公開狀態歸檔，不放到文件範本。

新 wiki 不會預設變成網頁。經使用者要求製作時，頁面設定 `publish: true`、`web_topic`、`web_file` 等欄位；共用版型產生 HTML。詳見 [欄位規格](docs/schema.md)。

## GitHub Pages

已準備 `.github/workflows/pages.yml`：PR/分支執行檢查，只有預設分支 push 或手動執行才部署。儲存庫已設定 Pages source 為 GitHub Actions，首次部署已成功。之後推送預設分支會重新建置與部署。

公開來源文件可重建網站，不依賴私有 PDF。網站發布白名單與 `.gitignore` 分開管理；不把專案整個根目錄上傳為 Pages artifact。第三方內容未經確認不重新授權。

其他說明：[工作流程](docs/workflow.md) · [設計](docs/design.md) · [操作紀錄](log.md)。
