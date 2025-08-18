from __future__ import annotations

from typing import Dict, Any, List, Tuple

import pandas as pd

from .optimizer import grid_search
from .strategy import StrategyParams
from .backtest import run_backtest


def walk_forward(df: pd.DataFrame, initial_balance: float, train_bars: int = 300, test_bars: int = 100) -> Dict[str, Any]:
	segments: List[Dict[str, Any]] = []
	combined_equity_times: List[pd.Timestamp] = []
	combined_equity_values: List[float] = []
	current_balance = initial_balance

	idx = df.index
	start = train_bars
	while start + test_bars <= len(idx):
		train_df = df.iloc[start - train_bars:start]
		test_df = df.iloc[start:start + test_bars]
		# Optimize on train
		best_map = grid_search({"SYMBOL": train_df}, initial_balance)
		best = best_map["SYMBOL"]
		params = StrategyParams(**best["params"])
		# Test on next window using rolling equity
		res = run_backtest(test_df, params, current_balance)
		segments.append({"start": test_df.index[0].isoformat(), "end": test_df.index[-1].isoformat(), "params": best["params"], "result": res})
		current_balance = res["final_balance"]
		# Extend combined equity
		combined_equity_times.extend(pd.to_datetime(res["equity_index"]))
		combined_equity_values.extend(res["equity"])
		start += test_bars

	# Aggregate metrics
	if combined_equity_values:
		equity_series = pd.Series(combined_equity_values, index=pd.to_datetime(combined_equity_times))
		returns = equity_series.pct_change().fillna(0.0)
		sharpe = (returns.mean() / (returns.std() + 1e-9)) * (252 * 6) ** 0.5
		max_dd = ((equity_series / equity_series.cummax()) - 1.0).min()
	else:
		sharpe = 0.0
		max_dd = 0.0

	return {
		"segments": segments,
		"final_balance": float(current_balance),
		"profit": float(current_balance - initial_balance),
		"sharpe": float(sharpe),
		"max_drawdown": float(max_dd),
		"equity_index": [t.isoformat() for t in pd.to_datetime(combined_equity_times)],
		"equity": [float(x) for x in combined_equity_values],
	}

