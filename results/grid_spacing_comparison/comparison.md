# BTCUSDT Grid Spacing Comparison

- Data: `data/spot/btcusdt/1m/BTCUSDT-1m-2025-10-15_2026-10-14.csv.gz`
- Period: 1760486400000000 to 1792022340000000
- Candles: 525,600
- Spot long-only, leverage 1; each buy is $100 notional.
- Separate tests: grid spacing and take-profit are both 2.5%, or both 5%.
- Grid is anchored to the first candle close; levels extend downward geometrically.
- No fees, spread, slippage, funding, or stop-loss included.
- OHLC convention: process each minute's low (entries) before its high (take-profits); this can overstate results if both occur in one minute.

| Metric | 2.5% grid/TP | 5% grid/TP |
|---|---:|---:|
| Start price | $113,014.05 | $113,014.05 |
| End price | $81,682.01 | $81,682.01 |
| Deepest grid level reached | 26 | 13 |
| Total entries | 181 | 41 |
| Closed trades | 169 | 34 |
| Realized profit | $422.50 | $170.00 |
| Unrealized P/L at end | $-173.63 | $-106.80 |
| Net P/L incl. open positions | $248.87 | $63.20 |
| Peak concurrent positions | 26 | 14 |
| Peak capital required | $2,600.00 | $1,400.00 |
| Capital tied up at end | $1,200.00 | $700.00 |
| Max equity drawdown | $567.55 | $312.01 |

## How to read capital requirements

Peak capital required = maximum simultaneous open positions × $100. This is the minimum cash tied up in open position notional before fees and reserve.
Realized profit excludes still-open positions. Net P/L includes mark-to-market P/L on open positions at the final close.
A long-only grid without a stop-loss can accumulate positions during a sustained decline; required capital and drawdown matter as much as profit.
Detailed trade lists and minute-by-minute equity curves are saved as CSV files.
