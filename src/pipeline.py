            )
    return pd.DataFrame(rows)


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

    try:
        quotes = fetch_quotes(universe)
    except Exception:
        quotes = pd.DataFrame()

    if quotes.empty and source_mode != "fallback_large_cap_symbols":
        source_mode = "fallback_large_cap_symbols"
        universe = FALLBACK_SYMBOLS
        try:
            quotes = fetch_quotes(universe)
        except Exception:
            quotes = pd.DataFrame()

    if quotes.empty:
        source_mode = "seed_data_yahoo_unavailable"
        universe = [row["symbol"] for row in SEED_TOP10]
        quotes = build_seed_quotes()

    top10 = quotes.head(10).copy()
    try:
        history = fetch_price_history(top10["symbol"].tolist())
    except Exception:
        history = pd.DataFrame()
    if history.empty:
        history = build_seed_history(top10)
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
