#!/usr/bin/env python3
"""Compare BTCUSDT spot grid backtests with 2.5% and 5% spacing / take-profit."""
import csv
import gzip
import json
import math
import os
from pathlib import Path

DATA_DIR = Path("data/spot/btcusdt/1m")
RESULT_DIR = Path("results/grid_spacing_comparison")
POSITION_USD = 100.0
SPACINGS = (0.025, 0.05)


def find_data():
    files = sorted(DATA_DIR.glob("*.csv.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(
            f"No .csv.gz dataset found in {DATA_DIR}. Run the one-year download workflow first."
        )
    return files[0]


def load_bars(path):
    bars = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"{path} has no CSV header")
        names = {n.strip().lower(): n for n in reader.fieldnames}
        needed = ("open_time", "high", "low", "close")
        missing = [n for n in needed if n not in names]
        if missing:
            raise ValueError(f"CSV missing required columns {missing}; found {reader.fieldnames}")
        for row in reader:
            try:
                bars.append({
                    "time": row[names["open_time"]],
                    "high": float(row[names["high"]]),
                    "low": float(row[names["low"]]),
                    "close": float(row[names["close"]]),
                })
            except (TypeError, ValueError):
                continue
    if len(bars) < 1000:
        raise ValueError(f"Only {len(bars)} usable rows found in {path}; dataset may be incomplete.")
    return bars


def run_backtest(bars, spacing):
    # Grid levels are anchored to the first close, spaced down geometrically.
    # Each level holds at most one $100 notional spot position at a time.
    # Each position takes profit at entry * (1 + spacing), then that level may
    # be re-entered on a later bar if price revisits it. No leverage, fees or slippage.
    anchor = bars[0]["close"]
    open_positions = {}  # level index -> {entry, qty, entry_time}
    closed_trades = []
    max_open = 0
    max_open_notional = 0.0
    max_level_seen = 0
    equity_curve = []
    realized = 0.0
    max_equity = 0.0
    max_drawdown = 0.0
    total_entries = 0

    def level_price(i):
        return anchor * ((1.0 - spacing) ** i)

    for bar in bars:
        # Low-first assumption for candles that touch both a buy level and a TP.
        # Open one $100 notional position at each crossed grid level.
        if bar["low"] < anchor:
            i = 1
            while level_price(i) >= bar["low"] and i < 100000:
                max_level_seen = max(max_level_seen, i)
                if i not in open_positions:
                    entry = level_price(i)
                    open_positions[i] = {
                        "entry": entry,
                        "qty": POSITION_USD / entry,
                        "entry_time": bar["time"],
                    }
                    total_entries += 1
                i += 1

        # Seed position at the first bar's close.
        if not open_positions and not closed_trades and total_entries == 0:
            open_positions[0] = {
                "entry": anchor,
                "qty": POSITION_USD / anchor,
                "entry_time": bar["time"],
            }
            total_entries += 1

        # Take profits for all positions touched by this bar's high.
        to_close = []
        for level, pos in open_positions.items():
            tp = pos["entry"] * (1.0 + spacing)
            if bar["high"] >= tp:
                pnl = pos["qty"] * (tp - pos["entry"])
                realized += pnl
                closed_trades.append({
                    "entry_time": pos["entry_time"],
                    "exit_time": bar["time"],
                    "level": level,
                    "entry_price": pos["entry"],
                    "exit_price": tp,
                    "notional_usd": POSITION_USD,
                    "pnl_usd": pnl,
                    "hold_minutes_approx": None,
                })
                to_close.append(level)
        for level in to_close:
            del open_positions[level]

        open_notional = len(open_positions) * POSITION_USD
        max_open = max(max_open, len(open_positions))
        max_open_notional = max(max_open_notional, open_notional)
        unrealized = sum(pos["qty"] * (bar["close"] - pos["entry"]) for pos in open_positions.values())
        equity = realized + unrealized
        max_equity = max(max_equity, equity)
        max_drawdown = max(max_drawdown, max_equity - equity)
        equity_curve.append({
            "time": bar["time"],
            "close": bar["close"],
            "open_positions": len(open_positions),
            "capital_locked_usd": open_notional,
            "realized_pnl_usd": realized,
            "unrealized_pnl_usd": unrealized,
            "total_pnl_usd": equity,
        })

    last_price = bars[-1]["close"]
    unrealized_end = sum(pos["qty"] * (last_price - pos["entry"]) for pos in open_positions.values())
    return {
        "spacing_pct": spacing * 100,
        "position_notional_usd": POSITION_USD,
        "bars": len(bars),
        "start_time": bars[0]["time"],
        "end_time": bars[-1]["time"],
        "start_price": anchor,
        "end_price": last_price,
        "grid_levels_reached_below_anchor": max_level_seen,
        "total_entries": total_entries,
        "closed_trades": len(closed_trades),
        "wins": sum(1 for t in closed_trades if t["pnl_usd"] > 0),
        "realized_profit_usd": realized,
        "open_positions_at_end": len(open_positions),
        "unrealized_pnl_at_end_usd": unrealized_end,
        "net_pnl_including_open_positions_usd": realized + unrealized_end,
        "peak_capital_required_usd": max_open_notional,
        "peak_concurrent_positions": max_open,
        "max_equity_drawdown_usd": max_drawdown,
        "open_position_cost_at_end_usd": len(open_positions) * POSITION_USD,
        "trades": closed_trades,
        "equity_curve": equity_curve,
    }


def money(x):
    return f"${x:,.2f}"


def main():
    data_path = find_data()
    bars = load_bars(data_path)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    results = [run_backtest(bars, s) for s in SPACINGS]

    # Save detailed results, trades, and a concise comparison report.
    summary = []
    for r in results:
        trades_path = RESULT_DIR / f"trades_{r['spacing_pct']:g}pct.csv"
        with trades_path.open("w", encoding="utf-8", newline="") as f:
            fields = ["entry_time", "exit_time", "level", "entry_price", "exit_price", "notional_usd", "pnl_usd"]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for trade in r["trades"]:
                w.writerow({k: trade[k] for k in fields})
        curve_path = RESULT_DIR / f"equity_{r['spacing_pct']:g}pct.csv"
        with curve_path.open("w", encoding="utf-8", newline="") as f:
            fields = ["time", "close", "open_positions", "capital_locked_usd", "realized_pnl_usd", "unrealized_pnl_usd", "total_pnl_usd"]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(r["equity_curve"])
        summary.append({k: v for k, v in r.items() if k not in ("trades", "equity_curve")})

    payload = {
        "data_file": str(data_path),
        "model": {
            "market": "Binance BTCUSDT spot",
            "position_notional_usd": POSITION_USD,
            "spacing_and_take_profit": "same percentage; 2.5% or 5%",
            "leverage": 1,
            "fees_and_slippage": "not included",
            "intrabar_assumption": "low is processed before high",
            "grid_anchor": "first candle close; grid levels extend downward geometrically",
            "reentry": "a level may be bought again on a later bar after its prior position closes",
        },
        "results": summary,
    }
    json_path = RESULT_DIR / "summary.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# BTCUSDT Grid Spacing Comparison",
        "",
        f"- Data file: `{data_path}`",
        f"- Period: {bars[0]['time']} to {bars[-1]['time']}",
        f"- Candles: {len(bars):,}",
        "- Each entry: $100 spot notional; leverage 1; fees/slippage excluded.",
        "- For each variant, TP equals its grid spacing (2.5% or 5%).",
        "- Grid is anchored to the first close and adds buys at geometrically spaced lower levels.",
        "- OHLC ambiguity: within each candle, low is processed before high; results can be optimistic when both a buy and TP are touched in the same minute.",
        "",
        "| Metric | 2.5% spacing / TP | 5% spacing / TP |",
        "|---|---:|---:|",
    ]
    fields = [
        ("Start price", "start_price", lambda x: f"${x:,.2f}"),
        ("End price", "end_price", lambda x: f"${x:,.2f}"),
        ("Grid levels reached below anchor", "grid_levels_reached_below_anchor", lambda x: f"{x:,}"),
        ("Total entries", "total_entries", lambda x: f"{x:,}"),
        ("Closed trades", "closed_trades", lambda x: f"{x:,}"),
        ("Realized profit", "realized_profit_usd", money),
        ("Unrealized P/L at end", "unrealized_pnl_at_end_usd", money),
        ("Net P/L incl. open positions", "net_pnl_including_open_positions_usd", money),
        ("Peak concurrent positions", "peak_concurrent_positions", lambda x: f"{x:,}"),
        ("Peak capital required (open notional)", "peak_capital_required_usd", money),
        ("Capital tied up at end", "open_position_cost_at_end_usd", money),
        ("Max equity drawdown", "max_equity_drawdown_usd", money),
    ]
    by_spacing = {r["spacing_pct"]: r for r in summary}
    for label, key, fmt in fields:
        lines.append(f"| {label} | {fmt(by_spacing[2.5][key])} | {fmt(by_spacing[5.0][key])} |")
    lines += [
        "",
        "## Interpretation",
        "",
        "- Peak capital required is the maximum simultaneous $100 positions open, multiplied by $100. It is a minimum cash estimate before fees and any reserve.",
        "- Realized profit excludes the value/P&L of positions still open at the end; net P/L includes their mark-to-market P/L.",
        "- This is a research backtest, not a guarantee of future returns. The grid is long-only and has no stop-loss, so prolonged declines can lock up substantial capital.",
        "",
        "Detailed trades and minute-by-minute equity curves are in the adjacent CSV files.",
    ]
    report_path = RESULT_DIR / "comparison.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report_path.read_text(encoding="utf-8"))
    print(f"Saved detailed output under {RESULT_DIR}")


if __name__ == "__main__":
    main()
