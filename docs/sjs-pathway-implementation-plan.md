# SJS clinical pathway implementation plan

> **For agentic workers:** Use subagent-driven-development to complete the scoped tasks below; perform independent clinical and engineering review before delivery.

**Goal:** 正式採用使用者已確認的新製圖流程，精簡多餘預防性句子，將SJS/TEN的診斷、嚴重度／器官評估、具體處置及重評追蹤接成可複習路徑。

**Architecture:** 保留疾病核心、approach的穩定id與網址；三張相連且各自有內容的圖分別處理診斷／分層、全身處置／反應、器官照護／追蹤。圖與文字沿用同一YAML定義。臨床內容限原有Watanabe與Heuer兩篇，方法來源只支援製作流程。

**Tech Stack:** Markdown/YAML、Python既有建置與檢查、已鎖定elkjs/Pele及原生SVG。

**Spec:** [已確認的流程修訂](clinical-pathway-authoring-revision.md)。

## Global constraints

- 原件、擷取、私有資料不發布；不新增來源未支持的醫學規則、劑量或時間。
- 保留not_reviewed；來源實質差異open並列，既有id／網址及主要科別維持。
- 主圖顯示主要條件、行動及重評；通用預防句與重複狀態框刪除，真實臨床安全條件保留為直接陳述。
- 不將其他疾病的參考圖內容移植為SJS治療；不以圖形／程式通過代替臨床路徑核對。

## Tasks

- [x] **1. 正式規範與範本。** 修改AGENTS、製圖手冊、臨床製圖骨架及schema/workflow，醫學原圖與臨床任務優先；撤除一律獨立unknown出口的要求。
- [x] **2. 來源決策表與教學案例。** 實讀兩篇原圖表／正文，建立診斷、器官／風險、治療分層、反應與追蹤的狀態—條件—行動—回饋對照。
- [x] **3. SJS圖與正文。** 從決策表產生三段相連定義與同頁文字，保留原入口；核對相關核心章節及醫學差異。
- [x] **4. 精簡已指出文字。** 修改MDD兩段正文與既有MDD圖中的重複提醒，用直接的族群、線別、終點及下一步表達。
- [x] **5. 工具對齊。** 先以失敗測試呈現有效雙向決策被強制未知出口拒絕的問題，再移除該限制；保留引用、條件標籤、可達性、安全SVG及真實未知回返的驗證。
- [x] **6. 圖像及獨立審查。** 重建受renderer雜湊影響的成品與資產紀錄，實際渲染檢視，另做來源／臨床完整性及工程審查並修正。
- [ ] **7. 完成驗證與發布。** 執行適用測試、索引／建置／lint、公開副本重建與私有排除；依既有授權更新GitHub Pages並核對線上成品。

驗收紀錄保存於 [SJS決策表與路徑驗收](sjs-pathway-decision-table.md)及log；保留實際裝置檢查的真實範圍。
