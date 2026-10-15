# BTCUSDT Grid Comparison: 1.25% vs 2.5%

- Data: `data/spot/btcusdt/1m/BTCUSDT-1m-2025-10-15_2026-10-14.csv.gz`
- Period: 1760486400000000 to 1792022340000000
- Candles: 525,600
- Spot long-only, leverage 1; each buy is $100 notional.
- Independent tests: grid spacing and take-profit are both 1.25%, or both 2.5%.
- The 2.5% case is recomputed with this workflow's same engine and exact same dataset for a fair comparison.
- Grid anchored to first candle close; levels extend downward geometrically.
- No fees, spread, slippage, funding, or stop-loss included.
- OHLC convention: process each minute's low (entries) before its high (take-profits); this can overstate results if both occur in one minute.

| Metric | 1.25% grid/TP | 2.5% grid/TP |
|---|---:|---:|
| Start price | $113,014.05 | $113,014.05 |
| End price | $81,682.01 | $81,682.01 |
| Deepest grid level reached | 53 | 26 |
| Total entries | 636 | 182 |
| Closed trades | 609 | 169 |
| Realized profit | $761.25 | $422.50 |
| Unrealized P/L at end | $-390.82 | $-201.36 |
| Net P/L incl. open positions | $370.43 | $221.14 |
| Peak concurrent positions | 54 | 27 |
| Peak capital required | $5,400.00 | $2,700.00 |
| Capital tied up at end | $2,700.00 | $1,300.00 |
| Max equity drawdown | $1,177.79 | $600.96 |

## Reference to previous workflow result

- Previous workflow's reported 2.5% net P/L: $221.14; peak capital estimate: $2,700.00.
- The table above recomputes 2.5% side-by-side using the same current data and engine. Use that row for the cleanest comparison; differences from the prior report can occur if the engine/data changed.

## Capital and limitations

Peak capital required = maximum simultaneous open positions × $100, before fees/reserve.
Realized profit excludes still-open positions; net P/L includes their mark-to-market P/L at the final close.
Long-only grid has no stop-loss, so extended declines can accumulate open positions.
Detailed trades and minute-by-minute equity curves are saved as CSV files.
