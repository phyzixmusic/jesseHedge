# Prevent Forced Position Closure at Backtest End

## Problem

By default, Jesse automatically closes all open positions at the end of backtests. This converts **unrealized PNL** into **realized PNL**, which can distort backtest results.

**Example**:
- Your strategy enters a long position
- Exit conditions are not met before backtest ends
- Jesse force-closes the position (e.g., at a loss)
- The loss is counted as **realized** instead of **unrealized**

This makes it difficult to evaluate strategies that hold positions beyond the backtest period.

## Solution

We've added a `prevent_forced_closure` flag to strategies. When set to `True`, Jesse will:
1. **NOT** automatically close open positions at backtest end
2. Count the position PNL as **unrealized**
3. Still include it in `total_open_pl` for tracking

## Usage

### In Your Strategy

Add the flag to your strategy's `__init__`:

```python
class MyStrategy(Strategy):
    def __init__(self):
        super().__init__()
        # Prevent Jesse from force-closing positions at backtest end
        self.prevent_forced_closure = True  # Set to False for default behavior
```

### Example: TamaTrendAW

```python
class TamaTrendAW(Strategy):
    def __init__(self):
        super().__init__()
        self.isBullish = True
        # Keep positions open at backtest end (don't realize losses/gains)
        self.prevent_forced_closure = False  # Set to True to enable
```

## Behavior Comparison

### Default Behavior (`prevent_forced_closure = False`)

```
[2023-10-02T23:59:00] Closed open Bybit USDT Perpetual-ETH-USDT position
                       at 1850.0 with PNL: -150.0 (-7.5%)
                       because we reached the end of the backtest session.
```

- Position is **closed**
- Loss is **realized** (counts against total profit)
- Trade appears in closed trades list

### With Prevention (`prevent_forced_closure = True`)

```
[2023-10-02T23:59:00] Keeping open Bybit USDT Perpetual-ETH-USDT position
                       at 1850.0 with UNREALIZED PNL: -150.0 (-7.5%)
                       (prevent_forced_closure=True)
```

- Position remains **open**
- Loss is **unrealized** (doesn't count against total profit)
- Trade does NOT appear in closed trades list
- Still counted in `total_open_pl` for analysis

## Logging Unrealized Positions

Override `before_terminate()` to log detailed info about unrealized positions:

```python
def before_terminate(self):
    """Log unrealized position details at backtest end"""
    if self.prevent_forced_closure and self.is_open:
        self.log(f"=== UNREALIZED POSITION AT BACKTEST END ===")
        self.log(f"Position: {self.position.qty} @ {self.position.entry_price}")
        self.log(f"Current Price: {self.price}")
        self.log(f"Unrealized PNL: {self.position.pnl:.2f} ({self.position.pnl_percentage:.2f}%)")
```

### Hedge Mode Example

```python
def before_terminate(self):
    """Log unrealized positions in hedge mode"""
    if self.prevent_forced_closure and self.is_open:
        if self.is_hedge_mode and isinstance(self.position, PositionPair):
            long_pnl = self.position.long_position.pnl if self.position.long_position.is_open else 0
            short_pnl = self.position.short_position.pnl if self.position.short_position.is_open else 0

            self.log(f"=== UNREALIZED POSITIONS AT BACKTEST END ===")
            if self.position.long_position.is_open:
                self.log(f"Long: {self.long_position_qty} @ {self.position.long_position.entry_price} | PNL: {long_pnl:.2f}")
            if self.has_hedge:
                self.log(f"Short: {self.short_position_qty} @ {self.hedge_entry_price} | PNL: {short_pnl:.2f}")
            self.log(f"Total Unrealized PNL: {long_pnl + short_pnl:.2f}")
```

## Implementation Details

### Changes to Jesse Core

**File**: `jesse/strategies/Strategy.py` (lines 1051-1075)

```python
if self.position.is_open:
    # Check if strategy wants to prevent forced closure
    if hasattr(self, 'prevent_forced_closure') and self.prevent_forced_closure:
        # Count as unrealized, don't close the position
        store.app.total_open_trades += 1
        store.app.total_open_pl += self.position.pnl
        logger.info(
            f"Keeping open {self.exchange}-{self.symbol} position at {self.position.current_price} "
            f"with UNREALIZED PNL: {round(self.position.pnl, 4)}({round(self.position.pnl_percentage, 2)}%) "
            f"(prevent_forced_closure=True)"
        )
        self.terminate()
        return

    # Default behavior: force close position
    # ... (original code)
```

### How It Works

1. At backtest end, `_terminate()` is called
2. Before force-closing, it checks for `prevent_forced_closure` attribute
3. If `True`:
   - Logs the position as **UNREALIZED**
   - Adds to `total_open_trades` and `total_open_pl`
   - Skips the `broker.reduce_position_at()` call
   - Calls `terminate()` hook
4. If `False` or not set:
   - Uses original behavior (force close)

## Use Cases

### 1. Long-Term Strategies

```python
# Strategy that holds positions for months
class LongTermTrend(Strategy):
    def __init__(self):
        super().__init__()
        self.prevent_forced_closure = True  # Don't force close at backtest end
```

**Why**: Your exit conditions might trigger weeks/months after backtest ends. Forced closure would create false losses.

### 2. Hedge Mode Strategies

```python
# Strategy with complex hedge positions
class MarketNeutral(Strategy):
    def __init__(self):
        super().__init__()
        self.prevent_forced_closure = True  # Keep both long and short open
```

**Why**: Closing positions at arbitrary backtest end point doesn't reflect real strategy performance with hedges.

### 3. DCA Strategies

```python
# Strategy that dollar-cost-averages into positions
class DCAStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.prevent_forced_closure = True  # Don't realize losses too early
```

**Why**: DCA strategies intentionally hold through drawdowns. Forced closure penalizes this approach.

## Metrics Impact

### With Forced Closure (Default)

```
Total Trades: 25
Win Rate: 52%
Total PNL: $1,250.00
Open Positions: 0
```

All positions closed → All PNL realized

### Without Forced Closure

```
Total Trades: 23 (2 kept open)
Win Rate: 56%
Total PNL: $1,450.00 (from closed trades only)
Open Positions: 2
Unrealized PNL: -$150.00
```

Open positions not counted in trades → More accurate win rate for completed trades

## Best Practices

1. **Use for Long-Term Strategies**: Enable when backtest period < typical holding period
2. **Analyze Unrealized PNL**: Always check `total_open_pl` in results
3. **Log Detailed Info**: Override `before_terminate()` to log position details
4. **Compare Both Modes**: Test with both `True` and `False` to understand impact
5. **Consider Hedge Mode**: Especially important for strategies with hedges

## Backward Compatibility

- **Default behavior unchanged**: Positions still force-close unless you explicitly set the flag
- **No breaking changes**: Existing strategies work exactly as before
- **Opt-in feature**: You must explicitly enable it in your strategy

## Example Output

### Without Prevention (Default)

```
[2023-12-31T23:59:00] Terminating ETH-USDT...
[2023-12-31T23:59:00] Closed open Bybit USDT Perpetual-ETH-USDT position at 1850.0
                       with PNL: -120.50 (-6.02%) because we reached the end of the backtest session.

Total Trades: 15
Net Profit: $1,230.50
```

### With Prevention Enabled

```
[2023-12-31T23:59:00] Terminating ETH-USDT...
[2023-12-31T23:59:00] === UNREALIZED POSITION AT BACKTEST END ===
[2023-12-31T23:59:00] Position: 10.5 @ 1970.0
[2023-12-31T23:59:00] Unrealized PNL: -120.50 (-6.02%)
[2023-12-31T23:59:00] Keeping open Bybit USDT Perpetual-ETH-USDT position at 1850.0
                       with UNREALIZED PNL: -120.50 (-6.02%) (prevent_forced_closure=True)

Total Trades: 14 (1 position kept open)
Net Profit: $1,351.00 (from closed trades only)
Unrealized PNL: -$120.50
```

## Notes

- Works with both **one-way mode** and **hedge mode**
- In hedge mode, both long and short positions remain open
- Unrealized PNL still tracked in `store.app.total_open_pl`
- Useful for analyzing strategy behavior beyond backtest window
- Does not affect live trading (live trading never terminates)

## Related Files

- **Jesse Core**: `jesse/strategies/Strategy.py` (lines 1051-1075)
- **Example**: `strategies/TamaTrendAW/__init__.py` (lines 36-37, 544-567)
- **Documentation**: This file