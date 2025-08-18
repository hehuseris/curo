from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import List, Dict, Any

import pandas as pd
import numpy as np


def _to_datetime(ms: int) -> pd.Timestamp:
	return pd.to_datetime(ms, unit="ms", utc=True)


@dataclass
class CandleFeed:
	client: Any

	def fetch_klines(self, symbol: str, interval: str, start: str, end: str) -> pd.DataFrame:
		# Lazy import to avoid hard dependency during tests
		from binance.client import Client
		start_ts = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
		end_ts = int(pd.Timestamp(end, tz="UTC").timestamp() * 1000)
		klines: List[List[Any]] = self.client.get_historical_klines(symbol, interval, start_ts, end_ts)
		cols = [
			"open_time","open","high","low","close","volume","close_time","quote_asset_volume",
			"number_of_trades","taker_buy_base","taker_buy_quote","ignore"
		]
		df = pd.DataFrame(klines, columns=cols)
		df["open_time"] = df["open_time"].astype(np.int64).apply(_to_datetime)
		df["close_time"] = df["close_time"].astype(np.int64).apply(_to_datetime)
		for c in ["open","high","low","close","volume"]:
			df[c] = df[c].astype(float)
		df = df.set_index("close_time").sort_index()
		return df[["open","high","low","close","volume"]]


def load_csv_klines(path: str) -> pd.DataFrame:
	"""Load klines from a CSV with columns: open_time,open,high,low,close,volume,close_time.
	Index by close_time in UTC.
	"""
	df = pd.read_csv(path)
	if "close_time" in df.columns:
		df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
		df = df.set_index("close_time").sort_index()
	for c in ["open","high","low","close","volume"]:
		df[c] = df[c].astype(float)
	return df[["open","high","low","close","volume"]]


def generate_synthetic_klines(num_bars: int = 500, timeframe: str = "4h", start: str = "2022-01-01", seed: int = 42) -> pd.DataFrame:
	rng = np.random.default_rng(seed)
	start_ts = pd.Timestamp(start, tz="UTC")
	step = pd.Timedelta(timeframe)
	index = [start_ts + i * step for i in range(num_bars)]
	returns = rng.normal(loc=0.0005, scale=0.01, size=num_bars)
	price = 100 * np.exp(np.cumsum(returns))
	high = price * (1 + rng.uniform(0.0, 0.01, size=num_bars))
	low = price * (1 - rng.uniform(0.0, 0.01, size=num_bars))
	open_ = np.concatenate([[price[0]], price[:-1]])
	volume = rng.uniform(100, 1000, size=num_bars)
	df = pd.DataFrame({
		"open": open_,
		"high": np.maximum.reduce([open_, price, high]),
		"low": np.minimum.reduce([open_, price, low]),
		"close": price,
		"volume": volume,
	}, index=pd.Index(index, name="close_time"))
	return df

