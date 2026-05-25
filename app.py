from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.pipeline import DB_PATH, load_history, load_top10, run_pipeline


st.set_page_config(
    page_title="Taiwan Top 10 Stock Dashboard",
    page_icon="📈",
    layout="wide",
)


def format_twd(value: float | int | None) -> str:
    if pd.isna(value):
        return "-"
    value = float(value)
    if abs(value) >= 1_000_000_000_000:
        return f"NT${value / 1_000_000_000_000:.2f}T"
    if abs(value) >= 100_000_000:
        return f"NT${value / 100_000_000:.1f}B"
    return f"NT${value:,.0f}"


def ensure_data(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        with st.spinner("第一次啟動，正在從 Yahoo Finance 更新資料..."):
            run_pipeline(db_path)


@st.cache_data(ttl=900, show_spinner=False)
def cached_load() -> tuple[pd.DataFrame, pd.DataFrame]:
    quotes = load_top10()
    history = load_history()
    return quotes, history


ensure_data()

with st.sidebar:
    st.title("台股市值前十大")
    st.caption("Data source: Yahoo Finance")
    if st.button("重新整理資料", type="primary", use_container_width=True):
        with st.spinner("正在更新 Yahoo Finance 資料..."):
            run_pipeline()
        cached_load.clear()
        st.success("資料已更新")

    st.divider()
    st.caption("資料管線")
    st.write("Yahoo Finance -> 清洗/排序 -> SQLite -> Streamlit")


quotes, history = cached_load()

if quotes.empty:
    st.error("目前沒有資料，請按左側重新整理資料。")
    st.stop()

quotes = quotes.sort_values("market_cap", ascending=False).reset_index(drop=True)
quotes["rank"] = quotes.index + 1
quotes["display_name"] = quotes["name"].fillna(quotes["symbol"])
quotes["market_cap_label"] = quotes["market_cap"].apply(format_twd)

latest_refresh = quotes["refreshed_at"].dropna().max()
top_gainer = quotes.loc[quotes["change_pct"].idxmax()]
top_loser = quotes.loc[quotes["change_pct"].idxmin()]

st.title("全台市值前十大股票漲跌儀表板")
st.caption(f"最後更新 UTC: {latest_refresh}")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("前十總市值", format_twd(quotes["market_cap"].sum()))
kpi2.metric("最大上漲", top_gainer["display_name"], f"{top_gainer['change_pct']:.2f}%")
kpi3.metric("最大下跌", top_loser["display_name"], f"{top_loser['change_pct']:.2f}%")
kpi4.metric("平均漲跌幅", f"{quotes['change_pct'].mean():.2f}%")

left, right = st.columns([1.25, 1])

with left:
    fig = px.bar(
        quotes.sort_values("change_pct"),
        x="change_pct",
        y="display_name",
        color="change_pct",
        color_continuous_scale=["#c43c35", "#d9d9d9", "#16845b"],
        labels={"change_pct": "漲跌幅 (%)", "display_name": "股票"},
        title="今日漲跌幅排名",
        hover_data={
            "symbol": True,
            "price": ":.2f",
            "market_cap_label": True,
            "change_pct": ":.2f",
        },
    )
    fig.update_layout(height=470, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

with right:
    fig = px.scatter(
        quotes,
        x="market_cap",
        y="change_pct",
        size="volume",
        color="change_pct",
        color_continuous_scale=["#c43c35", "#d9d9d9", "#16845b"],
        text="symbol",
        labels={"market_cap": "市值", "change_pct": "漲跌幅 (%)"},
        title="市值與漲跌幅關係",
        hover_name="display_name",
        hover_data={"price": ":.2f", "volume": ":,.0f"},
    )
    fig.update_traces(textposition="top center")
    fig.update_layout(height=470, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

selected = st.multiselect(
    "選擇股票查看近六個月收盤價",
    quotes["symbol"].tolist(),
    default=quotes["symbol"].head(3).tolist(),
)

if selected and not history.empty:
    hist = history[history["symbol"].isin(selected)].copy()
    hist["date"] = pd.to_datetime(hist["date"])
    fig = px.line(
        hist,
        x="date",
        y="close",
        color="symbol",
        labels={"date": "日期", "close": "收盤價"},
        title="歷史收盤價趨勢",
    )
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

table = quotes[
    [
        "rank",
        "symbol",
        "display_name",
        "price",
        "change",
        "change_pct",
        "volume",
        "market_cap_label",
        "high_52w",
        "low_52w",
    ]
].rename(
    columns={
        "rank": "排名",
        "symbol": "代號",
        "display_name": "名稱",
        "price": "現價",
        "change": "漲跌",
        "change_pct": "漲跌幅(%)",
        "volume": "成交量",
        "market_cap_label": "市值",
        "high_52w": "52週高",
        "low_52w": "52週低",
    }
)

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
    column_config={
        "現價": st.column_config.NumberColumn(format="%.2f"),
        "漲跌": st.column_config.NumberColumn(format="%.2f"),
        "漲跌幅(%)": st.column_config.NumberColumn(format="%.2f"),
        "成交量": st.column_config.NumberColumn(format="%d"),
        "52週高": st.column_config.NumberColumn(format="%.2f"),
        "52週低": st.column_config.NumberColumn(format="%.2f"),
    },
)
