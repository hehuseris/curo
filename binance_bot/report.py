from __future__ import annotations

from typing import Dict, Any


def summarize_backtest(result: Dict[str, Any]) -> str:
	return (
		f"Profit: {result['profit']:.2f}\n"
		f"Final balance: {result['final_balance']:.2f}\n"
		f"Trades: {result['num_trades']} | Win rate: {result['win_rate']*100:.1f}%\n"
		f"Sharpe: {result['sharpe']:.2f} | Max DD: {result['max_drawdown']*100:.1f}%"
	)


def plot_equity(result: Dict[str, Any], out_path: str) -> None:
	import matplotlib.pyplot as plt
	import pandas as pd
	if "equity" not in result or "equity_index" not in result:
		return
	dates = pd.to_datetime(result["equity_index"])
	values = result["equity"]
	plt.figure(figsize=(10,4))
	plt.plot(dates, values, label="Equity")
	plt.title("Equity Curve")
	plt.grid(True, alpha=0.25)
	plt.legend()
	plt.tight_layout()
	plt.savefig(out_path)
	plt.close()

