# DOL (Decisive Operating Line) Strategy

A mechanical trading strategy based on analyzing the last two candles to determine a decisive operating line (DOL) and directional bias, with structure-based entries and risk management.

## Strategy Logic

### 1. DOL and Bias Calculation (updates every bar)

Analyzes the last two fully closed candles: C[-2] then C[-1].

**Priority rule (sweep-failure overrides everything):**
- **Bearish sweep-failure**: if H[-1] > H[-2] and C[-1] <= C[-2] → bias = short, DOL = L[-1]
- **Bullish sweep-failure**: if L[-1] < L[-2] and C[-1] >= C[-2] → bias = long, DOL = H[-1]

**If no sweep-failure:**
- **Body momentum up**: if C[-1] > C[-2] → bias = long, DOL = H[-1]
- **Body momentum down**: if C[-1] < C[-2] → bias = short, DOL = L[-1]  
- **If C[-1] == C[-2]**: skip (no trade until next bar gives a bias)

### 2. Entry Triggers

Deterministic and backtest-friendly:
- **LONG**: only if bias = long and current bar closes above DOL after being below it (open < DOL and close > DOL)
- **SHORT**: only if bias = short and current bar closes below DOL after being above it (open > DOL and close < DOL)

### 3. Stop-Loss (Structure-based)

Fully mechanical and anchored to the two-candle micro-structure:
- **LONG SL**: min(L[-1], DOL) - buffer
- **SHORT SL**: max(H[-1], DOL) + buffer

Buffer = k * tick_size (configurable, default k = 2)

### 4. Take-Profit and Trade Management

- **TP1**: 1.5R (take 50% and move SL to breakeven)
- **TP2**: 3R (close remaining 50%)
- **Time stop**: exit remaining position after M bars if neither TP2 nor SL hit (prevents capital drift)
- **Flip exit**: if opposite entry signal appears while in trade, close and flip (optional toggle)

Where R = |entry - stop|

### 5. Position Sizing

Two modes available:
- **Percentage risk**: risk r% of account per trade (default 0.5%)
- **Fixed cash risk**: risk fixed $X per trade (default $5)

Formula: qty = risk_amount / |entry - stop|

## Configuration Parameters

- `buffer_ticks`: Stop-loss buffer in ticks (default: 2)
- `tick_size`: Minimum price movement (default: 0.01)  
- `tp1_multiplier`: TP1 distance in R multiples (default: 1.5)
- `tp2_multiplier`: TP2 distance in R multiples (default: 3.0)
- `risk_mode`: 'percentage' or 'fixed_cash' (default: 'percentage')
- `risk_percent`: Risk percentage for percentage mode (default: 0.5%)
- `fixed_risk_amount`: Fixed dollar risk amount (default: $5)
- `flip_exit_enabled`: Allow position flipping on opposite signals (default: true)
- `time_stop_enabled`: Enable time-based exit (default: true)
- `max_hold_bars`: Maximum bars to hold position (default: 20)

## Key Features

- **Mechanical entries**: No discretionary decisions, fully backtestable
- **Structure-based stops**: Logical invalidation levels based on price action
- **Scalable risk management**: Works with both percentage and fixed cash risk
- **Flexible profit-taking**: Partial closes with breakeven stop moves
- **Time management**: Prevents capital from being tied up indefinitely
- **Position flipping**: Can reverse on strong opposite signals

This strategy is designed for scalping and short-term trading on any timeframe, with particular effectiveness on lower timeframes where the two-candle pattern analysis can capture quick reversals and momentum shifts.