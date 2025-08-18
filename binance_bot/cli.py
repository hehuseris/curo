from __future__ import annotations

import argparse
import os
from typing import Dict, Any

import pandas as pd

from .config import load_config
from .data import CandleFeed, load_csv_klines, generate_synthetic_klines
from .strategy import StrategyParams
from .backtest import run_backtest
from .optimizer import grid_search
from .report import summarize_backtest, plot_equity
from .storage import save_json, load_json
from .paper_trade import run_paper_session
from .walkforward import walk_forward


def make_client(testnet: bool = False):
	from binance.client import Client
	api_key = os.getenv("BINANCE_API_KEY", "")
	api_secret = os.getenv("BINANCE_API_SECRET", "")
	client = Client(api_key, api_secret, testnet=testnet)
	return client


def cmd_backtest(args: argparse.Namespace) -> None:
	cfg = load_config()
	data_by_symbol: Dict[str, pd.DataFrame] = {}
	if args.offline:
		# Use synthetic or CSV data
		if args.csv_dir:
			import os
			for fname in os.listdir(args.csv_dir):
				if not fname.endswith(".csv"):
					continue
				symbol = fname.replace(".csv", "").upper()
				data_by_symbol[symbol] = load_csv_klines(os.path.join(args.csv_dir, fname))
		else:
			# Generate synthetic for requested symbols
			for sym in cfg.resolve_symbols(args.top):
				data_by_symbol[sym] = generate_synthetic_klines(600, cfg.backtest.timeframe, cfg.backtest.start_date)
	else:
		client = make_client(testnet=False)
		feed = CandleFeed(client)
		symbols = cfg.resolve_symbols(args.top)
		for sym in symbols:
			try:
				data_by_symbol[sym] = feed.fetch_klines(sym, cfg.backtest.timeframe, cfg.backtest.start_date, cfg.backtest.end_date)
			except Exception:
				continue

	p = StrategyParams()
	results: Dict[str, Any] = {}
	for sym, df in data_by_symbol.items():
		results[sym] = run_backtest(df, p, cfg.backtest.initial_balance_usd)

	print(f"Backtested {len(results)} symbols with baseline params.")
	for sym, res in list(results.items())[:10]:
		print(sym)
		print(summarize_backtest(res))


def cmd_optimize(args: argparse.Namespace) -> None:
	cfg = load_config()
	data_by_symbol: Dict[str, pd.DataFrame] = {}
	if args.offline:
		for sym in cfg.resolve_symbols(args.top):
			data_by_symbol[sym] = generate_synthetic_klines(600, cfg.backtest.timeframe, cfg.backtest.start_date)
	else:
		client = make_client(testnet=False)
		feed = CandleFeed(client)
		symbols = cfg.resolve_symbols(args.top)
		for sym in symbols:
			try:
				data_by_symbol[sym] = feed.fetch_klines(sym, cfg.backtest.timeframe, cfg.backtest.start_date, cfg.backtest.end_date)
			except Exception:
				continue

	opt = grid_search(data_by_symbol, cfg.backtest.initial_balance_usd, max_workers=cfg.opt.max_workers)
	print(f"Optimized {len(opt)} symbols.")
	for sym, best in list(opt.items())[:10]:
		res = best["result"]
		print(sym)
		print(summarize_backtest(res))

	# Persist best params per symbol
	save_json("./binance_bot_outputs/best_params.json", opt)
	print("Saved best parameters to ./binance_bot_outputs/best_params.json")


def cmd_calibrate(args: argparse.Namespace) -> None:
	# Alias for optimize for now
	cmd_optimize(args)


def cmd_paper(args: argparse.Namespace) -> None:
	cfg = load_config()
	client = make_client(testnet=False)
	feed = CandleFeed(client)
	best = load_json("./binance_bot_outputs/best_params.json")

	symbol = args.symbol
	df = feed.fetch_klines(symbol, cfg.backtest.timeframe, cfg.backtest.start_date, cfg.backtest.end_date)
	params_dict = best.get(symbol, {}).get("params")
	if not params_dict:
		print(f"No optimized params for {symbol}. Run optimize first.")
		return
	p = StrategyParams(**params_dict)
	res = run_paper_session(df, p, cfg.paper.initial_balance_usd)
	save_json(f"./binance_bot_outputs/paper_{symbol}.json", res)
	print(f"Paper result {symbol}: final ${res['final_balance']:.2f}")


def cmd_walkforward(args: argparse.Namespace) -> None:
	cfg = load_config()
	if args.offline:
		from .data import generate_synthetic_klines
		df = generate_synthetic_klines(1200, cfg.backtest.timeframe, cfg.backtest.start_date)
	else:
		client = make_client(testnet=False)
		feed = CandleFeed(client)
		df = feed.fetch_klines(args.symbol, cfg.backtest.timeframe, cfg.backtest.start_date, cfg.backtest.end_date)
	res = walk_forward(df, cfg.backtest.initial_balance_usd, args.train_bars, args.test_bars)
	save_json(f"./binance_bot_outputs/wf_{args.symbol}.json", res)
	plot_equity(res, f"./binance_bot_outputs/wf_{args.symbol}.png")
	print(f"Walk-forward {args.symbol}: final ${res['final_balance']:.2f}, sharpe {res['sharpe']:.2f}")


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Binance multi-confirmation trading bot")
	sub = parser.add_subparsers(dest="cmd", required=True)

	p_back = sub.add_parser("backtest", help="Run baseline backtests")
	p_back.add_argument("--top", type=int, default=50, help="Top N symbols to include")
	p_back.add_argument("--offline", action="store_true", help="Run without Binance API using synthetic/CSV data")
	p_back.add_argument("--csv-dir", help="Directory of CSV klines per symbol")
	p_back.set_defaults(func=cmd_backtest)

	p_opt = sub.add_parser("optimize", help="Optimize per-symbol parameters")
	p_opt.add_argument("--top", type=int, default=50, help="Top N symbols to include")
	p_opt.add_argument("--offline", action="store_true", help="Run without Binance API using synthetic data")
	p_opt.set_defaults(func=cmd_optimize)

	p_cal = sub.add_parser("calibrate", help="Alias for optimize; future: walk-forward calibration")
	p_cal.set_defaults(func=cmd_calibrate)

	p_paper = sub.add_parser("paper", help="Run paper trading over historical window for a symbol using best params")
	p_paper.add_argument("symbol", help="Symbol like BTCUSDT")
	p_paper.set_defaults(func=cmd_paper)

	p_wf = sub.add_parser("walkforward", help="Walk-forward calibration on one symbol")
	p_wf.add_argument("symbol", help="Symbol like BTCUSDT")
	p_wf.add_argument("--offline", action="store_true", help="Use synthetic data instead of Binance API")
	p_wf.add_argument("--train-bars", type=int, default=300)
	p_wf.add_argument("--test-bars", type=int, default=100)
	p_wf.set_defaults(func=cmd_walkforward)


	return parser


def main() -> None:
	parser = build_parser()
	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()

