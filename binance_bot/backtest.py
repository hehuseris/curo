from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd

from .strategy import StrategyParams, build_features, generate_signals


@dataclass
class Trade:
	entry_time: pd.Timestamp
	entry_price: float
	qty: float
	stop_price: float
	take_price: float
	exit_time: pd.Timestamp | None = None
	exit_price: float | None = None
	profit: float | None = None


def run_backtest(df: pd.DataFrame, p: StrategyParams, initial_balance: float, commission: float = 0.00075,
					max_positions: int = 1) -> Dict[str, Any]:
	feat = build_features(df, p)
	sig = generate_signals(feat, p)

	balance = initial_balance
	position: Trade | None = None
	trades: List[Trade] = []
	equity_curve = []

	for ts, row in sig.iterrows():
		price = float(row["close"])
		if position is None:
			if bool(row.get("long_entry", False)):
				qty = (balance * (1 - commission)) / price
				stop_price = price - row["atr"] * p.stop_atr_mult if not np.isnan(row["atr"]) else price * 0.95
				take_price = price + row["atr"] * p.take_atr_mult if not np.isnan(row["atr"]) else price * 1.05
				position = Trade(entry_time=ts, entry_price=price, qty=qty, stop_price=stop_price, take_price=take_price)
				balance = 0.0
		else:
			# Check stops/takes first
			if row["low"] <= position.stop_price:
				exit_price = position.stop_price
				fee = exit_price * position.qty * commission
				balance = exit_price * position.qty - fee
				position.exit_time = ts
				position.exit_price = exit_price
				position.profit = balance - initial_balance
				trades.append(position)
				position = None
			elif row["high"] >= position.take_price:
				exit_price = position.take_price
				fee = exit_price * position.qty * commission
				balance = exit_price * position.qty - fee
				position.exit_time = ts
				position.exit_price = exit_price
				position.profit = balance - initial_balance
				trades.append(position)
				position = None
			elif bool(row.get("long_exit_signal", False)):
				exit_price = price
				fee = exit_price * position.qty * commission
				balance = exit_price * position.qty - fee
				position.exit_time = ts
				position.exit_price = exit_price
				position.profit = balance - initial_balance
				trades.append(position)
				position = None

		equity_curve.append(balance if position is None else position.qty * price)

	# Close any open position at last price
	if position is not None:
		last_price = float(sig.iloc[-1]["close"])
		fee = last_price * position.qty * commission
		balance = last_price * position.qty - fee
		position.exit_time = sig.index[-1]
		position.exit_price = last_price
		position.profit = balance - initial_balance
		trades.append(position)

	equity = pd.Series(equity_curve, index=sig.index)
	returns = equity.pct_change().fillna(0.0)
	sharpe = np.sqrt(252 * 6) * returns.mean() / (returns.std() + 1e-9)
	max_dd = ((equity / equity.cummax()) - 1.0).min()

	result = {
		"trades": trades,
		"final_balance": float(balance),
		"profit": float(balance - initial_balance),
		"num_trades": len(trades),
		"win_rate": float(np.mean([1.0 if t.profit and t.profit > 0 else 0.0 for t in trades]) if trades else 0.0),
		"sharpe": float(sharpe),
		"max_drawdown": float(max_dd),
	}
	return result

