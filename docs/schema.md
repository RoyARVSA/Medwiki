# 欄位與引用規格

## Wiki 與來源摘要

必要欄位：id、title、type、created、updated、summary、tags、source_ids、review_status、conflict_status。其定義見 AGENTS.md。

`population` 與 `clinical_context` 記錄適用族群及治療／診斷情境，不以一段泛稱取代正文的限制。每個文內引用對應的 source-id 必須同時列在 `source_ids`，供來源面板與資訊關係使用；檢查工具會拒絕漏列。CANMAT 的指引版本與刊登年份分別保存，不以更新版名稱推定出版年。

`type` 支援 concept / comparison / approach / question / map / source_summary。新增的 `approach` 存於 `01_wiki/approaches/`；`specialties` 可列多個科別，`content_kind` 區分 disease、sign、chapter、comparison、approach、differential、criteria、atlas、specialty、navigation、learning_resource。`related_ids` 連到既有核心頁，分類不另複製正文。

`conflict_page_id` 明確指定保留分歧的已發布比較頁。沒有指定時只顯示衝突提示，不從同科別任選比較頁；目標為自身時不顯示重複跳轉按鈕。

科別、疾病與概念、臨床思路是不同瀏覽方式；網站路徑由穩定 page-id 與發布欄位決定。`view` 可選 atlas / concept-library / specialty / reasoning，未設定使用一般閱讀頁；前三者的導航由公開欄位生成。

網站以科別為主：`view: specialty` 且 `content_kind: specialty` 的 map 宣告科別入口；`specialties` 使用已宣告的英文科別 id，可列多個。`browse_group` 是可選的科內學習群組標籤；`cross_specialty: true` 明確加入主訴／跨科入口，不能由 comparison 類型推定。`catalog_role: work` 標示完整作品；一般頁與章節不因此逐一列成果。來源摘要仍按單一來源保留，文獻與作品目錄分開。

新介面目錄由 `scripts/navigation.py` 的公開欄位模型生成；首頁科別框格受控換頁，科內四類清單分開。既有 concept-library 網址保留作精簡目錄，首頁不再列全站疾病卡片。通用文獻／成果／全部科別目錄是網站介面，不預造醫學知識頁。安全返回 context 僅使用已知科別 id；查詢、分組、頁碼存 URL，不寫個人儲存。

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
| parent_id | 可選的共同核心頁 id；明記真正章節關係，與實體檔案或 web_topic 分開 |

route 為 `03_outputs/web/<web_topic>/<web_file>`。同一 route 不能重複，站內 Markdown 連結在兩端都已發布時轉為相對網址；未發布的連結不能悄悄產生失效網址。跨主題的入口與側欄由共用版型維護。

## 來源

source_id 穩定識別；short_id 是文內短代碼（目前 H/W/A/B/F/M/C）。pdf_pages、printed_start、printed_prefix 用於頁次檢核。DOI 用正式解析網址，原件位置只留 private 對照。processing_status complete 是提供的來源單位讀取完成，不包含未附補充資料或引用文獻全文。

## 引用語法

```text
[@H:3]
[@W:9-10]
[@W:2,4]
```

冒號後為一開始算起的 PDF 頁次，不是期刊頁。工具根據來源記錄換算顯示（H PDF3→期刊36；W PDF9→e96），保留兩種定位。未知來源、超過總頁、倒置範圍會中止建置。公開頁只連 DOI，不連本機 PDF。

HTML 彙編來源使用 `locator_type: html`、`locators` 字典，例如 `d01: 項目 01：雄性禿`；引用 `[@A:d01]`、`[@B:blister]`。`public_path` 可連到已發布的來源整理頁；每個宣告的定位都必須是該頁存在的 HTML id，建置於 staging 檢查後才替換網站。`original_access: local_only` 不變；公開來源整理不是原始 HTML。講義所列外部連結不自動視為已讀來源。

## 流程圖

`config/flows/<flow-id>.yml` 是單一流程定義，記錄 id、title、kind、population、version、source_ids、review_status、conflict_status、entry、nodes、edges、notes。kind 為 criteria / differential / management；node kind 為 step / decision / terminal / unknown，節點保留 label、detail、citations，分支保留 from、to、label。

`assets/figures/flows/` 保存由定義生成的 `.mmd`、`.svg` 及雜湊 manifest；資產紀錄在 `assets/records/flow-<id>.yml`。正式頁的 Markdown 保留原生圖片與註解：

```markdown
<!-- flow:japanese-sjs-criteria -->

![流程圖與來源文字對照](../../assets/figures/flows/japanese-sjs-criteria.svg)
```

Obsidian 可直接閱讀 SVG，網站以同一個流程定義產生互動圖、文字步驟與來源。決策節點須有來源與明確未知出口；所有節點/分支必須存在且從 entry 可達。工具不執行病人診斷或產生疾病機率。定義或引擎變更後，舊雜湊會使建置失敗，須重新產圖與核對。

## 圖譜導航

`config/atlas.yml` 只保存分組、原卡片 id/source、canonical page-id、Markdown 路徑與章節 anchor。圖片、辨認要點與驗證內容由核心頁讀取，不另維護第二份醫學正文。圖片預覽保留原圖、圖說及原署名/來源/授權；未知使用條件的圖不進公開資產。

## 索引

index.md 由文件欄位產生，map 由學習邏輯維護，index.html 提供固定入口及科別選擇。公開成果掃描結果在獨立學習成果頁按作品分組；章節不逐頁當作品。搜尋 JSON 與內嵌搜尋資料由公開頁正文產生，不讀 raw/private，不能放入私有擷取資料。

## 狀態

processing_status：registered / partial / complete / blocked。
review_status：not_reviewed / reviewed。
conflict_status：none / open / resolved。

open 必須配 not_reviewed。resolved 及 reviewed 必須有使用者或指定人工審閱者確認，不能由建置工具自動升級。
