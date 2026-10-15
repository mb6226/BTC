# BTCUSDT Grid Spacing Comparison

- Data file: `data/spot/btcusdt/1m/BTCUSDT-1m-2025-10-15_2026-10-14.csv.gz`
- Period: 1760486400000000 to 1792022340000000
- Candles: 525,600
- Each entry: $100 spot notional; leverage 1; fees/slippage excluded.
- For each variant, TP equals its grid spacing (2.5% or 5%).
- Grid is anchored to the first close and adds buys at geometrically spaced lower levels.
- OHLC ambiguity: within each candle, low is processed before high; results can be optimistic when both a buy and TP are touched in the same minute.

| Metric | 2.5% spacing / TP | 5% spacing / TP |
|---|---:|---:|
| Start price | $113,014.05 | $113,014.05 |
| End price | $81,682.01 | $81,682.01 |
| Grid levels reached below anchor | 26 | 13 |
| Total entries | 181 | 41 |
| Closed trades | 169 | 34 |
| Realized profit | $422.50 | $170.00 |
| Unrealized P/L at end | $-173.63 | $-106.80 |
| Net P/L incl. open positions | $248.87 | $63.20 |
| Peak concurrent positions | 26 | 14 |
| Peak capital required (open notional) | $2,600.00 | $1,400.00 |
| Capital tied up at end | $1,200.00 | $700.00 |
| Max equity drawdown | $567.55 | $312.01 |

## Interpretation

- Peak capital required is the maximum simultaneous $100 positions open, multiplied by $100. It is a minimum cash estimate before fees and any reserve.
- Realized profit excludes the value/P&L of positions still open at the end; net P/L includes their mark-to-market P/L.
- This is a research backtest, not a guarantee of future returns. The grid is long-only and has no stop-loss, so prolonged declines can lock up substantial capital.

Detailed trades and minute-by-minute equity curves are in the adjacent CSV files.
