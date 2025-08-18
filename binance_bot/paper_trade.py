from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any

import time
import pandas as pd

from .strategy import StrategyParams, build_features, generate_signals


@dataclass
class PaperState:
	balance_usd: float
	position_qty: float = 0.0
	entry_price: float = 0.0
	stop_price: float = 0.0
	take_price: float = 0.0


def run_paper_session(df: pd.DataFrame, p: StrategyParams, starting_balance: float) -> Dict[str, Any]:
	feat = build_features(df, p)
	sig = generate_signals(feat, p)
	state = PaperState(balance_usd=starting_balance)
	trades = []

	for ts, row in sig.iterrows():
		price = float(row["close"])
		if state.position_qty == 0.0 and bool(row["long_entry"]):
			state.position_qty = state.balance_usd / price
			state.entry_price = price
			state.stop_price = price - row["atr"] * p.stop_atr_mult
			state.take_price = price + row["atr"] * p.take_atr_mult
		elif state.position_qty > 0.0:
			if row["low"] <= state.stop_price or row["high"] >= state.take_price or bool(row["long_exit_signal"]):
				exit_price = state.stop_price if row["low"] <= state.stop_price else (state.take_price if row["high"] >= state.take_price else price)
				state.balance_usd = state.position_qty * exit_price
				trades.append({
					"entry_time": ts, "entry": state.entry_price, "exit": exit_price,
					"profit": state.balance_usd - starting_balance
				})
				state.position_qty = 0.0

	return {"final_balance": state.balance_usd, "trades": trades}

