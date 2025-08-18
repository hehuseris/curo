from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Tuple

import itertools
import concurrent.futures as cf
import numpy as np

from .strategy import StrategyParams
from .backtest import run_backtest


def _score(result: Dict[str, Any]) -> float:
	# Composite score: prioritize profit and penalize drawdown; include Sharpe
	profit = result["profit"]
	sharpe = result["sharpe"]
	dd = abs(result["max_drawdown"]) + 1e-6
	return profit * 0.7 + sharpe * 100.0 - dd * 500.0


def grid_search(df_by_symbol: Dict[str, Any], initial_balance: float, max_workers: int = 4) -> Dict[str, Dict[str, Any]]:
	# A pragmatic grid over key parameters
	fast_emas = [10, 20, 30]
	slow_emas = [40, 60, 90]
	rsi_buys = [50, 55, 60]
	rsi_sells = [40, 45, 50]
	atr_mults = [(2.0, 4.0), (2.5, 4.5), (3.0, 5.0)]
	trend_filters = [0.0, 0.002, 0.005]

	param_space = list(itertools.product(fast_emas, slow_emas, rsi_buys, rsi_sells, atr_mults, trend_filters))

	def evaluate(symbol: str) -> Tuple[str, Dict[str, Any]]:
		best_score = -1e18
		best = None
		df = df_by_symbol[symbol]
		for (f,s,rb,rs,(sat,tat),tf) in param_space:
			if f >= s:
				continue
			p = StrategyParams(
				fast_ema=f, slow_ema=s,
				rsi_len=14, rsi_buy=rb, rsi_sell=rs,
				atr_len=14, stop_atr_mult=sat, take_atr_mult=tat,
				min_trend_strength=tf
			)
			res = run_backtest(df, p, initial_balance)
			s = _score(res)
			if s > best_score:
				best_score = s
				best = {"params": asdict(p), "result": res}
		return symbol, best

	results: Dict[str, Dict[str, Any]] = {}
	with cf.ThreadPoolExecutor(max_workers=max_workers) as pool:
		for symbol, best in pool.map(evaluate, df_by_symbol.keys()):
			results[symbol] = best
	return results