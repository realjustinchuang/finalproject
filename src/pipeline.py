from __future__ import annotations

import argparse
import math
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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

SEED_TOP10 = [
    {
        "symbol": "2330.TW",
        "name": "台積電",
        "long_name": "Taiwan Semiconductor Manufacturing Company Limited",
        "price": 979.0,
        "change": 8.0,
        "change_pct": 0.82,
        "previous_close": 971.0,
        "volume": 36_500_000,
        "avg_volume_3m": 42_000_000,
        "market_cap": 25_400_000_000_000,
        "high_52w": 1080.0,
