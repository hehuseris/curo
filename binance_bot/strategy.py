from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

import pandas as pd

from .indicators import ema, rsi, macd, atr


@dataclass
class StrategyParams:
	# Moving averages
	fast_ema: int = 20
	slow_ema: int = 50
	# RSI
	rsi_len: int = 14
	rsi_buy: int = 55
	rsi_sell: int = 45
	# MACD
	macd_fast: int = 12
	macd_slow: int = 26
	macd_signal: int = 9
	# Risk
	atr_len: int = 14
	stop_atr_mult: float = 2.5
	take_atr_mult: float = 4.0
	# Filters
	min_trend_strength: float = 0.0


def build_features(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
	feat = df.copy()
	feat["ema_fast"] = ema(feat["close"], p.fast_ema)
	feat["ema_slow"] = ema(feat["close"], p.slow_ema)
	feat["rsi"] = rsi(feat["close"], p.rsi_len)
	macd_df = macd(feat["close"], p.macd_fast, p.macd_slow, p.macd_signal)
	feat = pd.concat([feat, macd_df], axis=1)
	feat["atr"] = atr(feat["high"], feat["low"], feat["close"], p.atr_len)
	feat["trend"] = (feat["ema_fast"] - feat["ema_slow"]) / feat["close"]
	return feat


def generate_signals(feat: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
	sig = feat.copy()
	# Long entries when EMAs aligned, RSI confirms, MACD positive
	sig["long_entry"] = (
		(sig["ema_fast"] > sig["ema_slow"]) &
		(sig["rsi"] >= p.rsi_buy) &
		(sig["macd"] > sig["signal"]) &
		(sig["trend"] >= p.min_trend_strength)
	)
	# Exits when RSI falls or MACD crosses down
	sig["long_exit_signal"] = (
		(sig["rsi"] <= p.rsi_sell) |
		(sig["macd"] < sig["signal"]) |
		(sig["ema_fast"] < sig["ema_slow"])
	)
	return sig

