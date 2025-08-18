from __future__ import annotations

from typing import Dict, Any


def summarize_backtest(result: Dict[str, Any]) -> str:
	return (
		f"Profit: {result['profit']:.2f}\n"
		f"Final balance: {result['final_balance']:.2f}\n"
		f"Trades: {result['num_trades']} | Win rate: {result['win_rate']*100:.1f}%\n"
		f"Sharpe: {result['sharpe']:.2f} | Max DD: {result['max_drawdown']*100:.1f}%"
	)

