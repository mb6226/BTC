#!/usr/bin/env python3
"""Compare BTCUSDT long-only spot grid spacing/TP at 1.25% and 2.5%."""
import csv, gzip, json, math
from pathlib import Path

DATA_DIR = Path("data/spot/btcusdt/1m")
OUT = Path("results/grid_spacing_125_vs_25")
STAKE = 100.0
SPACINGS = (0.0125, 0.025)


def load_data():
    files = sorted(DATA_DIR.glob("*.csv.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No dataset in {DATA_DIR}; run the one-year download workflow first.")
    path = files[0]
    bars = []
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Dataset CSV has no header.")
        cols = {x.strip().lower(): x for x in reader.fieldnames}
        required = ("open_time", "high", "low", "close")
        if any(x not in cols for x in required):
            raise ValueError(f"Expected columns {required}; got {reader.fieldnames}")
        for row in reader:
            try:
                bars.append({"time": row[cols["open_time"]], "high": float(row[cols["high"]]),
                             "low": float(row[cols["low"]]), "close": float(row[cols["close"]])})
            except (TypeError, ValueError):
                continue
    if len(bars) < 1000:
        raise ValueError(f"Only {len(bars)} valid candles in {path}; data may be incomplete.")
    return path, bars


def backtest(bars, step):
    anchor = bars[0]["close"]
    open_pos = {0: {"entry": anchor, "qty": STAKE / anchor, "time": bars[0]["time"]}}
    trades, curve = [], []
    realized = 0.0
    max_open = 1
    max_dd = 0.0
    peak_equity = 0.0
    deepest_level = 0
    entries = 1

    def price(level):
        return anchor * ((1.0 - step) ** level)

    for idx, bar in enumerate(bars):
        if idx > 0 and bar["low"] < bars[idx - 1]["close"] and bar["low"] < anchor:
            prev = bars[idx - 1]["close"]
            if prev > anchor:
                first = 0
            elif prev == anchor:
                first = 1
            else:
                first = max(1, math.floor(math.log(prev / anchor) / math.log(1.0 - step)) + 1)
            deepest = max(0, math.floor(math.log(bar["low"] / anchor) / math.log(1.0 - step)))
            while deepest > 0 and price(deepest) < bar["low"]:
                deepest -= 1
            while price(deepest + 1) >= bar["low"]:
                deepest += 1
            deepest_level = max(deepest_level, deepest)
            for level in range(first, deepest + 1):
                if level not in open_pos:
                    p = price(level)
                    open_pos[level] = {"entry": p, "qty": STAKE / p, "time": bar["time"]}
                    entries += 1

        # Consistent OHLC convention: process entries at low before TPs at high.
        for level, pos in list(open_pos.items()):
            tp = pos["entry"] * (1.0 + step)
            if bar["high"] >= tp:
                pnl = pos["qty"] * (tp - pos["entry"])
                realized += pnl
                trades.append({"entry_time": pos["time"], "exit_time": bar["time"], "grid_level": level,
                               "entry_price": pos["entry"], "exit_price": tp,
                               "notional_usd": STAKE, "pnl_usd": pnl})
                del open_pos[level]

        open_notional = len(open_pos) * STAKE
        max_open = max(max_open, len(open_pos))
        unrealized = sum(p["qty"] * (bar["close"] - p["entry"]) for p in open_pos.values())
        equity_pnl = realized + unrealized
        peak_equity = max(peak_equity, equity_pnl)
        max_dd = max(max_dd, peak_equity - equity_pnl)
        curve.append({"time": bar["time"], "close": bar["close"], "open_positions": len(open_pos),
                      "capital_locked_usd": open_notional, "realized_pnl_usd": realized,
                      "unrealized_pnl_usd": unrealized, "total_pnl_usd": equity_pnl})

    end_price = bars[-1]["close"]
    unrealized_end = sum(p["qty"] * (end_price - p["entry"]) for p in open_pos.values())
    return {
        "spacing_pct": step * 100, "position_notional_usd": STAKE, "bars": len(bars),
        "start_time": bars[0]["time"], "end_time": bars[-1]["time"],
        "start_price": anchor, "end_price": end_price, "deepest_grid_level": deepest_level,
        "total_entries": entries, "closed_trades": len(trades), "realized_profit_usd": realized,
        "open_positions_at_end": len(open_pos), "unrealized_pnl_at_end_usd": unrealized_end,
        "net_pnl_including_open_positions_usd": realized + unrealized_end,
        "peak_concurrent_positions": max_open, "peak_capital_required_usd": max_open * STAKE,
        "capital_tied_up_at_end_usd": len(open_pos) * STAKE, "max_equity_drawdown_usd": max_dd,
        "trades": trades, "equity_curve": curve,
    }


def usd(v):
    return f"${v:,.2f}"


def main():
    data_path, bars = load_data()
    OUT.mkdir(parents=True, exist_ok=True)
    raw = [backtest(bars, s) for s in SPACINGS]
    results = []
    for r in raw:
        results.append({k: v for k, v in r.items() if k not in ("trades", "equity_curve")})
        tag = f"{r['spacing_pct']:g}pct"
        with (OUT / f"trades_{tag}.csv").open("w", newline="", encoding="utf-8") as f:
            fields = ["entry_time", "exit_time", "grid_level", "entry_price", "exit_price", "notional_usd", "pnl_usd"]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for t in r["trades"]:
                w.writerow(t)
        with (OUT / f"equity_{tag}.csv").open("w", newline="", encoding="utf-8") as f:
            fields = ["time", "close", "open_positions", "capital_locked_usd", "realized_pnl_usd", "unrealized_pnl_usd", "total_pnl_usd"]
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(r["equity_curve"])

    labels = {1.25: "1.25%", 2.5: "2.5%"}
    by = {r["spacing_pct"]: r for r in results}
    report = [
        "# BTCUSDT Grid Comparison: 1.25% vs 2.5%", "",
        f"- Data: `{data_path}`", f"- Period: {bars[0]['time']} to {bars[-1]['time']}",
        f"- Candles: {len(bars):,}", "- Spot long-only, leverage 1; each buy is $100 notional.",
        "- Independent tests: grid spacing and take-profit are both 1.25%, or both 2.5%.",
        "- The 2.5% case is recomputed with this workflow's same engine and exact same dataset for a fair comparison.",
        "- Grid anchored to first candle close; levels extend downward geometrically.",
        "- No fees, spread, slippage, funding, or stop-loss included.",
        "- OHLC convention: process each minute's low (entries) before its high (take-profits); this can overstate results if both occur in one minute.",
        "", "| Metric | 1.25% grid/TP | 2.5% grid/TP |", "|---|---:|---:|"
    ]
    metrics = [
        ("Start price", "start_price", usd), ("End price", "end_price", usd),
        ("Deepest grid level reached", "deepest_grid_level", lambda x: f"{x:,}"),
        ("Total entries", "total_entries", lambda x: f"{x:,}"),
        ("Closed trades", "closed_trades", lambda x: f"{x:,}"),
        ("Realized profit", "realized_profit_usd", usd),
        ("Unrealized P/L at end", "unrealized_pnl_at_end_usd", usd),
        ("Net P/L incl. open positions", "net_pnl_including_open_positions_usd", usd),
        ("Peak concurrent positions", "peak_concurrent_positions", lambda x: f"{x:,}"),
        ("Peak capital required", "peak_capital_required_usd", usd),
        ("Capital tied up at end", "capital_tied_up_at_end_usd", usd),
        ("Max equity drawdown", "max_equity_drawdown_usd", usd),
    ]
    for label, key, fmt in metrics:
        report.append(f"| {label} | {fmt(by[1.25][key])} | {fmt(by[2.5][key])} |")
    prior_net = 221.14
    prior_capital = 2700.00
    report += [
        "", "## Reference to previous workflow result", "",
        f"- Previous workflow's reported 2.5% net P/L: {usd(prior_net)}; peak capital estimate: {usd(prior_capital)}.",
        "- The table above recomputes 2.5% side-by-side using the same current data and engine. Use that row for the cleanest comparison; differences from the prior report can occur if the engine/data changed.",
        "", "## Capital and limitations", "",
        "Peak capital required = maximum simultaneous open positions × $100, before fees/reserve.",
        "Realized profit excludes still-open positions; net P/L includes their mark-to-market P/L at the final close.",
        "Long-only grid has no stop-loss, so extended declines can accumulate open positions.",
        "Detailed trades and minute-by-minute equity curves are saved as CSV files."
    ]
    (OUT / "comparison.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps({"data_file": str(data_path), "results": results,
                                                  "previous_workflow_2_5pct_reference": {
                                                      "net_pnl_including_open_positions_usd": prior_net,
                                                      "peak_capital_required_usd": prior_capital}}, indent=2), encoding="utf-8")
    print("\n".join(report))
    print(f"Detailed results saved in {OUT}")


if __name__ == "__main__":
    main()
