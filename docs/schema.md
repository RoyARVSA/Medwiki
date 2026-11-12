# 欄位與引用規格

## Wiki 與來源摘要

必要欄位：id、title、type、created、updated、summary、tags、source_ids、review_status、conflict_status。其定義見 AGENTS.md。

網頁欄位：

| 欄位 | 說明 |
| --- | --- |
| publish | true 才轉為網站；缺少/false 只維護 Markdown |
| web_topic | 小寫英文連字號主題 slug；本版省略時為 sjs-ten |
| web_file | 英文 HTML 檔名，主題入口使用 index.html，不能含路徑 |
| topic_title | 主題顯示名稱；sjs-ten 預設 SJS / TEN |
| nav_title | 該頁導航短名 |
| order | 同主題篇章順序 |
| eyebrow | 學術版面的小標籤 |
| title_en | 副標題 |
| aliases | 搜尋用的中英文別名、縮寫 |

route 為 `03_outputs/web/<web_topic>/<web_file>`。同一 route 不能重複，站內 Markdown 連結在兩端都已發布時轉為相對網址；未發布的連結不能悄悄產生失效網址。跨主題的入口與側欄由共用版型維護。

## 來源

source_id 穩定識別；short_id 是文內短代碼（本版 H/W）。pdf_pages、printed_start、printed_prefix 用於頁次檢核。DOI 用正式解析網址，原件位置只留 private 對照。processing_status complete 是提供的來源單位讀取完成，不包含未附補充資料或引用文獻全文。

## 引用語法

```text
[@H:3]
[@W:9-10]
[@W:2,4]
```

冒號後為一開始算起的 PDF 頁次，不是期刊頁。工具根據來源記錄換算顯示（H PDF3→期刊36；W PDF9→e96），保留兩種定位。未知來源、超過總頁、倒置範圍會中止建置。公開頁只連 DOI，不連本機 PDF。

## 索引

index.md 由文件欄位產生，map 由學習邏輯維護，index.html 掃描公開成果；三者職責不同。搜尋 JSON 與內嵌搜尋資料由公開頁正文產生，不讀 raw/private，不能放入私有擷取資料。

## 狀態

processing_status：registered / partial / complete / blocked。
review_status：not_reviewed / reviewed。
conflict_status：none / open / resolved。

open 必須配 not_reviewed。resolved 及 reviewed 必須有使用者或指定人工審閱者確認，不能由建置工具自動升級。
