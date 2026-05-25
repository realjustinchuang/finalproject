from __future__ import annotations

import argparse
import math
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "taiwan_top10_stocks.sqlite"

YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_SCREENER_URL = "https://query2.finance.yahoo.com/v1/finance/screener"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}

# Fallback universe: large Taiwan-listed names. The pipeline first tries Yahoo's
# screener API, then uses this list if Yahoo changes or blocks the screener.
FALLBACK_SYMBOLS = [
    "2330.TW",
    "2317.TW",
    "2454.TW",
    "2308.TW",
    "2382.TW",
    "2412.TW",
    "2881.TW",
    "2882.TW",
    "2303.TW",
    "3711.TW",
    "2891.TW",
    "2886.TW",
    "1216.TW",
    "1303.TW",
    "1301.TW",
    "2884.TW",
    "5871.TW",
    "3045.TW",
    "2002.TW",
    "2207.TW",
    "2892.TW",
    "5880.TW",
    "2885.TW",
    "3034.TW",
    "2357.TW",
    "2327.TW",
    "2379.TW",
    "3008.TW",
    "2395.TW",
    "2912.TW",
    "1101.TW",
    "2603.TW",
    "2609.TW",
    "2615.TW",
    "2880.TW",
    "2883.TW",
    "4938.TW",
    "6669.TW",
    "1590.TW",
    "6415.TW",
    "6505.TW",
    "5876.TW",
    "2345.TW",
    "4904.TW",
    "9910.TW",
    "2408.TW",
    "3661.TW",
    "6488.TW",
    "6409.TW",
    "6446.TW",
]


@dataclass(frozen=True)
class PipelineResult:
    symbols_checked: int
    top10_rows: int
    history_rows: int
    refreshed_at: str
    source_mode: str


def _get_json(url: str, params: dict | None = None, retries: int = 3) -> dict:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=20)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - retry network/API failures.
            last_error = exc
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"Yahoo request failed: {url}") from last_error


def _post_json(url: str, payload: dict, retries: int = 2) -> dict:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.post(
                url, json=payload, headers=HEADERS, timeout=25
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - retry network/API failures.
            last_error = exc
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"Yahoo screener request failed: {url}") from last_error


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for idx in range(0, len(values), size):
        yield values[idx : idx + size]


def fetch_yahoo_screener_symbols(limit: int = 80) -> list[str]:
    payload = {
        "offset": 0,
        "size": limit,
        "sortField": "intradaymarketcap",
        "sortType": "DESC",
        "quoteType": "EQUITY",
        "query": {
            "operator": "AND",
            "operands": [
                {"operator": "eq", "operands": ["region", "tw"]},
                {"operator": "eq", "operands": ["quoteType", "EQUITY"]},
            ],
        },
        "userId": "",
        "userIdType": "guid",
    }
    data = _post_json(YAHOO_SCREENER_URL, payload)
    quotes = data.get("finance", {}).get("result", [{}])[0].get("quotes", [])
    symbols = [quote.get("symbol") for quote in quotes if quote.get("symbol")]
    return [symbol for symbol in symbols if symbol.endswith((".TW", ".TWO"))]


def fetch_quotes(symbols: list[str]) -> pd.DataFrame:
    rows: list[dict] = []
    for group in chunks(symbols, 40):
        data = _get_json(YAHOO_QUOTE_URL, {"symbols": ",".join(group)})
        rows.extend(data.get("quoteResponse", {}).get("result", []))

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    wanted = {
        "symbol": "symbol",
        "shortName": "name",
        "longName": "long_name",
        "regularMarketPrice": "price",
        "regularMarketChange": "change",
        "regularMarketChangePercent": "change_pct",
        "regularMarketPreviousClose": "previous_close",
        "regularMarketVolume": "volume",
        "averageDailyVolume3Month": "avg_volume_3m",
        "marketCap": "market_cap",
        "fiftyTwoWeekHigh": "high_52w",
        "fiftyTwoWeekLow": "low_52w",
        "currency": "currency",
        "exchange": "exchange",
        "regularMarketTime": "market_time",
    }
    df = df[[column for column in wanted if column in df.columns]].rename(columns=wanted)

    for column in [
        "price",
        "change",
        "change_pct",
        "previous_close",
        "volume",
        "avg_volume_3m",
        "market_cap",
        "high_52w",
        "low_52w",
        "market_time",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=["symbol", "market_cap", "price", "change_pct"])
    df["market_time"] = pd.to_datetime(
        df["market_time"], unit="s", utc=True, errors="coerce"
    )
    df["refreshed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return df.sort_values("market_cap", ascending=False).reset_index(drop=True)


def fetch_price_history(symbols: list[str], months: int = 6) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    range_value = f"{max(1, math.ceil(months * 30 / 31))}mo"

    for symbol in symbols:
        data = _get_json(
            YAHOO_CHART_URL.format(symbol=symbol),
            {"range": range_value, "interval": "1d", "events": "history"},
        )
        result = data.get("chart", {}).get("result", [])
        if not result:
            continue

        chart = result[0]
        timestamps = chart.get("timestamp", [])
        quote = chart.get("indicators", {}).get("quote", [{}])[0]
        frame = pd.DataFrame(quote)
        if frame.empty or not timestamps:
            continue

        frame["date"] = pd.to_datetime(timestamps, unit="s", utc=True).date
        frame["symbol"] = symbol
        rows.append(frame[["symbol", "date", "open", "high", "low", "close", "volume"]])

    if not rows:
        return pd.DataFrame(
            columns=["symbol", "date", "open", "high", "low", "close", "volume"]
        )

    history = pd.concat(rows, ignore_index=True)
    for column in ["open", "high", "low", "close", "volume"]:
        history[column] = pd.to_numeric(history[column], errors="coerce")
    return history.dropna(subset=["close"]).reset_index(drop=True)


def prepare_database(db_path: Path = DB_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS top10_quotes (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            long_name TEXT,
            price REAL,
            change REAL,
            change_pct REAL,
            previous_close REAL,
            volume REAL,
            avg_volume_3m REAL,
            market_cap REAL,
            high_52w REAL,
            low_52w REAL,
            currency TEXT,
            exchange TEXT,
            market_time TEXT,
            refreshed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS price_history (
            symbol TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (symbol, date)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS refresh_log (
            refreshed_at TEXT PRIMARY KEY,
            symbols_checked INTEGER,
            top10_rows INTEGER,
            history_rows INTEGER,
            source_mode TEXT
        )
        """
    )
    return conn


def run_pipeline(db_path: Path = DB_PATH) -> PipelineResult:
    source_mode = "yahoo_screener"
    try:
        universe = fetch_yahoo_screener_symbols()
    except Exception:
        universe = FALLBACK_SYMBOLS
        source_mode = "fallback_large_cap_symbols"

    quotes = fetch_quotes(universe)
    if quotes.empty and source_mode != "fallback_large_cap_symbols":
        source_mode = "fallback_large_cap_symbols"
        universe = FALLBACK_SYMBOLS
        quotes = fetch_quotes(universe)

    if quotes.empty:
        raise RuntimeError("No Yahoo quote rows were returned.")

    top10 = quotes.head(10).copy()
    history = fetch_price_history(top10["symbol"].tolist())
    refreshed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if "market_time" in top10.columns:
        top10["market_time"] = top10["market_time"].astype(str)
    if not history.empty:
        history["date"] = history["date"].astype(str)

    conn = prepare_database(db_path)
    with conn:
        conn.execute("DELETE FROM top10_quotes")
        top10.to_sql("top10_quotes", conn, if_exists="append", index=False)
        history.to_sql("price_history", conn, if_exists="replace", index=False)
        conn.execute(
            """
            INSERT INTO refresh_log (
                refreshed_at, symbols_checked, top10_rows, history_rows, source_mode
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (refreshed_at, len(universe), len(top10), len(history), source_mode),
        )
    conn.close()

    return PipelineResult(
        symbols_checked=len(universe),
        top10_rows=len(top10),
        history_rows=len(history),
        refreshed_at=refreshed_at,
        source_mode=source_mode,
    )


def load_top10(db_path: Path = DB_PATH) -> pd.DataFrame:
    conn = prepare_database(db_path)
    try:
        return pd.read_sql_query("SELECT * FROM top10_quotes", conn)
    finally:
        conn.close()


def load_history(db_path: Path = DB_PATH) -> pd.DataFrame:
    conn = prepare_database(db_path)
    try:
        return pd.read_sql_query("SELECT * FROM price_history", conn)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh Taiwan top-10 stock data.")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite DB output path")
    args = parser.parse_args()
    result = run_pipeline(args.db)
    print(result)


if __name__ == "__main__":
    main()
