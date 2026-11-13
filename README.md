# Medwiki

以 Markdown 累積醫學知識，以靜態網站閱讀、比較與展示。繁體中文內容、英文檔名。完整協作規則見 [AGENTS.md](AGENTS.md)。

## 開始閱讀

- [線上網站](https://royarvsa.github.io/Medwiki/)
- [內頁版型比較](https://royarvsa.github.io/Medwiki/03_outputs/web/layout-previews/index.html)：三種設計使用相同內容，正式內頁暫不替換。

- 本機建置後開啟根目錄 `index.html`：知識入口、完成成果與待加入區。
- [SJS/TEN 學習專題](https://royarvsa.github.io/Medwiki/03_outputs/web/sjs-ten/index.html)。
- [全部 wiki 索引](index.md)：適合 Obsidian。
- [皮膚科學習路徑](01_wiki/maps/dermatology.md)。
- [皮膚病灶辨識圖譜](01_wiki/maps/dermatology-image-atlas.md)：主講義 55 項與增補 4 項，連回共同核心頁。
- [疾病與概念](01_wiki/maps/diseases-concepts.md)、[臨床思路](01_wiki/maps/clinical-reasoning.md)。

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

網站 HTML 與搜尋 JSON 由來源重建，留在本機並由工具維護的精確 `.gitignore` 清單排除，不另提交。可編輯 Markdown、圖片、來源/流程定義與已驗證的 SVG 成品會保存。手動新增的成果不在此清單；移除產生頁或改為手動成果後，下次成功建置會同步移除對應忽略規則。

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
- 多疾病比較在 `01_wiki/comparisons/`，評估/診斷/處置思路在 `01_wiki/approaches/`。科別與其他 map 可指向同頁，不複製正文。

目前完成兩份 PDF 的閱讀與整理，人工審閱尚未完成。已記錄國際/日本分型、類固醇證據及原文數據等差異；缺少的補充檔與個別原始研究不視為已讀。

另外整合兩份使用者提供的皮膚病灶 HTML 教學彙編；引用 A/B 使用卡片與章節定位。彙編所列外部文獻保留連結，未視為本次全部重讀。原始 HTML 與 PDF 同樣只留本機。

## 圖譜與流程圖

圖譜可依病名/關鍵詞與學習分組搜尋，切換圖像、清單或當次自測。自測只揭示原有內容，不保存待讀、作答、熟練度或複習資料。圖片保留全幅、水印、圖說及署名/授權連結；一張使用條件未明的昆蟲附圖暫留本機。

流程圖由 `config/flows/` 定義、`assets/figures/flows/` 成品及 `assets/records/` 出處共同維護；網站提供圖形/文字對照、節點說明、來源與縮放。Obsidian 使用 Markdown 原生 SVG 圖片。需要重畫時：

```powershell
npm ci --prefix tools/diagrams --ignore-scripts
python scripts/flows.py --build
python scripts/build_site.py
```

固定使用 Pele 1.13.0。流程須標準則版本與適用情境；未知不視為陰性，圖形重排不改動醫學條件。一般建置會驗證既有成品，公開 clone 不需私有原件。必要修訂說明放頁尾，完整專案維護留在 log.md。

## 加入網頁或簡報

手動 HTML 放 `03_outputs/web/<topic>/`，PDF/PPTX 放 `03_outputs/slides/<topic>/`，執行更新即可被首頁收錄。不需先填 metadata，assets/ 裡的支援頁不列成果。來源圖先依可公開狀態歸檔，不放到文件範本。

新 wiki 不會預設變成網頁。經使用者要求製作時，頁面設定 `publish: true`、`web_topic`、`web_file` 等欄位；共用版型產生 HTML。詳見 [欄位規格](docs/schema.md)。

## GitHub Pages

已準備 `.github/workflows/pages.yml`：PR/分支執行檢查，只有預設分支 push 或手動執行才部署。儲存庫已設定 Pages source 為 GitHub Actions，首次部署已成功。之後推送預設分支會重新建置與部署。

公開來源文件可重建網站，不依賴私有 PDF。網站發布白名單與 `.gitignore` 分開管理；不把專案整個根目錄上傳為 Pages artifact。第三方內容未經確認不重新授權。

其他說明：[工作流程](docs/workflow.md) · [設計](docs/design.md) · [操作紀錄](log.md)。
