# Executive Summary: 全台市值前十大股票漲跌儀表板

本專案建立一個公開可部署的台股監控儀表板，主題是「全台市值前十大股票的即時漲跌與趨勢」。資料來源採用 Yahoo Finance，後端資料管線會抓取股票代號、名稱、即時價格、漲跌幅、成交量、市值與近六個月歷史收盤價，清洗後存入 SQLite 資料庫。前端使用 Streamlit 與 Plotly，提供互動式視覺化，方便在課堂展示時用公開 URL 直接操作。

資料管線流程為 Yahoo Finance API 抓取、欄位標準化、缺失值處理、市值排序、取前十大、歷史價格補充，最後寫入 SQLite。為了提高穩定性，程式會優先嘗試 Yahoo Finance screener 取得台股大型股清單；若 screener 暫時失敗，則使用預先整理的台股大型股候選清單，再從 Yahoo Finance 取得最新市值並重新排序。此設計讓 demo 時不會因單一端點失敗而整個系統無法運作。

儀表板包含四個核心溝通重點：前十大總市值、最大上漲股票、最大下跌股票、平均漲跌幅。視覺化部分包含漲跌幅橫向長條圖、市值與漲跌幅泡泡圖、近六個月收盤價折線圖，以及可排序的明細表。使用者可以透過側邊欄按鈕重新整理資料，形成一個簡單但明確的 data refresh mechanism。

此專案不使用 Tableau、Power BI 等商業智慧工具，完全由 Python、Streamlit、Plotly、Requests、Pandas 與 SQLite 建置。部署時可使用 Streamlit Community Cloud 或 Render，取得公開網址後即可完成課堂 demo。未來可延伸功能包含每日排程更新、加入產業分類、技術指標、法人買賣超，以及異常波動通知。
