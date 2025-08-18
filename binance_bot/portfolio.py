from __future__ import annotations

from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd

from .backtest import run_backtest
from .strategy import StrategyParams


def run_portfolio_backtest(
	data_by_symbol: Dict[str, pd.DataFrame],
	params_by_symbol: Dict[str, StrategyParams],
	initial_balance: float,
	commission: float = 0.00075,
	risk_per_trade_pct: float = 1.0,
	slippage_bps: float = 0.0,
) -> Dict[str, Any]:
	if not data_by_symbol:
		return {"final_balance": initial_balance, "equity_index": [], "equity": []}
	per_symbol_cash = initial_balance / max(len(data_by_symbol), 1)
	portfolio_equity: pd.Series | None = None
	results_by_symbol: Dict[str, Any] = {}
	for sym, df in data_by_symbol.items():
		p = params_by_symbol.get(sym)
		if p is None:
			continue
		res = run_backtest(
			df, p, per_symbol_cash,
			commission=commission,
			risk_per_trade_pct=risk_per_trade_pct,
			slippage_bps=slippage_bps,
		)
		results_by_symbol[sym] = res
		if res.get("equity") and res.get("equity_index"):
			series = pd.Series(res["equity"], index=pd.to_datetime(res["equity_index"]))
			portfolio_equity = series if portfolio_equity is None else portfolio_equity.add(series, fill_value=0.0)

	if portfolio_equity is None:
		final_balance = initial_balance
		equity_index: list[str] = []
		equity_vals: list[float] = []
		sharpe = 0.0
		max_dd = 0.0
	else:
		final_balance = float(portfolio_equity.iloc[-1])
		equity_index = [ts.isoformat() for ts in portfolio_equity.index]
		equity_vals = [float(x) for x in portfolio_equity.values]
		returns = portfolio_equity.pct_change().fillna(0.0)
		sharpe = float(np.sqrt(252 * 6) * returns.mean() / (returns.std() + 1e-9))
		max_dd = float(((portfolio_equity / portfolio_equity.cummax()) - 1.0).min())

	return {
		"results_by_symbol": results_by_symbol,
		"final_balance": final_balance,
		"profit": float(final_balance - initial_balance),
		"sharpe": sharpe,
		"max_drawdown": max_dd,
		"equity_index": equity_index,
		"equity": equity_vals,
	}

