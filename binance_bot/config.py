from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class ExchangeConfig:
	api_key: str = ""
	api_secret: str = ""
	base_url: str = "https://api.binance.com"
	testnet: bool = True


@dataclass
class BacktestConfig:
	timeframe: str = "4h"
	start_date: str = "2021-01-01"
	end_date: str = "2025-01-01"
	initial_balance_usd: float = 1000.0
	commission: float = 0.00075
	max_positions: int = 1
	quote_asset: str = "USDT"


@dataclass
class OptimizationConfig:
	population_size: int = 40
	generations: int = 25
	cv_folds: int = 3
	max_workers: int = os.cpu_count() or 4


@dataclass
class PaperTradeConfig:
	initial_balance_usd: float = 1000.0
	duration_days: int = 14
	quote_asset: str = "USDT"


@dataclass
class LiveTradeConfig:
	quote_asset: str = "USDT"
	max_position_size_pct: float = 0.2
	max_open_positions: int = 3
	stop_on_drawdown_pct: float = 20.0


@dataclass
class BotConfig:
	exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
	backtest: BacktestConfig = field(default_factory=BacktestConfig)
	opt: OptimizationConfig = field(default_factory=OptimizationConfig)
	paper: PaperTradeConfig = field(default_factory=PaperTradeConfig)
	live: LiveTradeConfig = field(default_factory=LiveTradeConfig)
	symbols: List[str] = field(default_factory=list)

	def resolve_symbols(self, top_n: int = 50) -> List[str]:
		if self.symbols:
			return self.symbols
		# Default to top market-cap tickers; in practice fetched via API. Placeholder list for USDT pairs.
		default = [
			"BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","TRXUSDT","TONUSDT","AVAXUSDT",
			"SHIBUSDT","DOTUSDT","LINKUSDT","MATICUSDT","BCHUSDT","NEARUSDT","UNIUSDT","LTCUSDT","APTUSDT","ATOMUSDT",
			"XLMUSDT","INJUSDT","OKBUSDT","SUIUSDT","FDUSDUSDT","ETCUSDT","IMXUSDT","ARBUSDT","OPUSDT","HBARUSDT",
			"FILUSDT","RNDRUSDT","TIAUSDT","KASUSDT","MNTUSDT","AAVEUSDT","ALGOUSDT","FLOWUSDT","VETUSDT","GRTUSDT",
			"EGLDUSDT","SANDUSDT","MANAUSDT","AXSUSDT","FTMUSDT","ROSEUSDT","JTOUSDT","PYTHUSDT","WIFUSDT","JUPUSDT",
		]
		return default[:top_n]


def load_config() -> BotConfig:
	return BotConfig()

