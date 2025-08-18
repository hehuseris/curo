from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

import time
import pandas as pd

from .strategy import StrategyParams, build_features, generate_signals


@dataclass
class LiveState:
	quote_balance: float
	base_position: float = 0.0
	entry_price: float = 0.0
	stop_price: float = 0.0
	take_price: float = 0.0


def run_live_once(df: pd.DataFrame, p: StrategyParams, quote_balance: float) -> Dict[str, Any]:
	feat = build_features(df, p)
	sig = generate_signals(feat, p)
	row = sig.iloc[-1]
	return {
		"should_long": bool(row["long_entry"]),
		"should_exit": bool(row["long_exit_signal"]),
		"atr": float(row["atr"]),
		"price": float(row["close"]),
	}

