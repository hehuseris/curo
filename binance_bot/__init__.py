"""Binance multi-confirmation trading bot package.

This package provides tools to:
- Build multi-confirmation strategies
- Backtest across multiple symbols (4h timeframe)
- Optimize per-coin configurations
- Run paper trading on Binance testnet
- Deploy to live trading on Binance
"""

__all__ = [
	"config",
	"data",
	"indicators",
	"strategy",
	"backtest",
	"optimizer",
	"paper_trade",
	"live_trade",
	"report",
	"cli",
]

