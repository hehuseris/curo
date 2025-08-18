from __future__ import annotations

import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
	return series.ewm(span=length, adjust=False, min_periods=length).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
	delta = series.diff()
	gain = (delta.where(delta > 0, 0.0)).rolling(length).mean()
	loss = (-delta.where(delta < 0, 0.0)).rolling(length).mean()
	rs = gain / (loss.replace(0, 1e-12))
	return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
	fast_ema = ema(series, fast)
	slow_ema = ema(series, slow)
	macd_line = fast_ema - slow_ema
	signal_line = ema(macd_line, signal)
	hist = macd_line - signal_line
	return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
	prev_close = close.shift(1)
	tr = pd.concat([
		high - low,
		(high - prev_close).abs(),
		(low - prev_close).abs()
	], axis=1).max(axis=1)
	return tr.rolling(length).mean()

