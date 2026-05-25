# Taiwan Top 10 Stock Dashboard

這是一個以 Yahoo Finance 資料為來源的台股市值前十大儀表板範例。後端資料管線會抓取股票報價、市值、成交量與歷史收盤價，清洗後存進 SQLite；前端用 Streamlit 與 Plotly 呈現漲跌幅、市值關係與歷史趨勢。

## 專案結構 

```text
.
├── app.py
├── requirements.txt
├── executive_summary.md
└── src
    └── pipeline.py
```

## 本機測試

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/pipeline.py
streamlit run app.py
```

## 部署建議

可以部署到 Streamlit Community Cloud、Render 或 Hugging Face Spaces。最簡單的方式是：

1. 將此資料夾推到 GitHub repository。
2. 到 Streamlit Community Cloud 建立 app。
3. Main file path 填 `app.py`。
4. 部署完成後，用 Streamlit 提供的公開 URL 做 in-class demo。

## 資料更新

儀表板左側有「重新整理資料」按鈕，會即時呼叫 Yahoo Finance 更新 SQLite。Streamlit 的資料快取 TTL 設為 15 分鐘，適合課堂 demo。若要更完整的自動更新，可以在部署平台加上排程任務執行：

```bash
python src/pipeline.py
```
