# Hedge Mode for Jesse - Complete Guide

## Overview

Hedge mode allows you to hold simultaneous long and short positions on the same symbol. This is useful for market-neutral strategies, hedging, and advanced trading techniques.

**Status**: ✅ Fully functional for backtesting on Jesse website and Python API

---

## Quick Start

### 1. Using Jesse Website (jesse.trade)

Since the Jesse website doesn't expose the `futures_position_mode` config in the UI, use the **HedgeModeTest** strategy which automatically enables hedge mode:

```python
# strategies/HedgeModeTest/__init__.py already handles this
# Just select "HedgeModeTest" strategy in the UI
```

The strategy enables hedge mode at module import time and forces the correct position type.

### 2. Using Python/Research API

```python
from jesse import research
import jesse.helpers as jh

config = {
    'starting_balance': 10_000,
    'fee': 0.0006,
    'type': 'futures',
    'futures_leverage': 2,
    'futures_leverage_mode': 'cross',
    'futures_position_mode': 'hedge',  # ← Enable hedge mode
    'exchange': 'Bybit USDT Perpetual',
}

routes = [{
    'exchange': 'Bybit USDT Perpetual',
    'strategy': 'YourStrategy',
    'symbol': 'ETH-USDT',
    'timeframe': '1h'
}]

result = research.backtest(config, routes, [], candles)
```

---

## Writing Hedge Mode Strategies

### Basic Pattern

```python
from jesse.strategies import Strategy
from jesse.models.PositionPair import PositionPair

class MyHedgeStrategy(Strategy):
    def should_long(self):
        # Entry condition for long position
        return self.index == 5

    def go_long(self):
        # Open long position - note the 3rd parameter
        qty = 1.0
        self.buy = qty, self.price, 'long'  # ← position_side

        # Optional: stop-loss and take-profit
        self.stop_loss = qty, self.price * 0.95, 'long'
        self.take_profit = qty, self.price * 1.05, 'long'

    def should_short(self):
        # Not used in hedge mode - use update_position() instead
        return False

    def go_short(self):
        pass

    def update_position(self):
        # Manage short position independently
        # Can open short while long is open!

        if self.index == 10 and self.some_condition:
            qty = 0.5
            # Use broker directly for hedge positions
            self.broker.sell_at_market(qty, position_side='short')

        # Close long position at specific time
        if self.index == 20 and self.position.long_position.is_open:
            qty = self.position.long_position.qty
            self.broker.sell_at_market(qty, position_side='long')

        # Close short position at specific time
        if self.index == 25 and self.position.short_position.is_open:
            qty = abs(self.position.short_position.qty)
            self.broker.buy_at_market(qty, position_side='short')

    def should_cancel_entry(self):
        return False
```

### Accessing Position Data

```python
# Check if in hedge mode
if isinstance(self.position, PositionPair):
    # Access individual positions
    long_qty = self.position.long_position.qty
    short_qty = abs(self.position.short_position.qty)  # Take abs (stored as negative)

    # Net position
    net_qty = self.position.net_qty

    # Individual PNL
    long_pnl = self.position.long_position.pnl if long_qty > 0 else 0
    short_pnl = self.position.short_position.pnl if short_qty > 0 else 0

    # Total PNL
    total_pnl = self.position.total_pnl

    # Check if positions are open
    if self.position.long_position.is_open:
        print(f"Long position: {long_qty} @ {self.position.long_position.entry_price}")

    if self.position.short_position.is_open:
        print(f"Short position: {short_qty} @ {self.position.short_position.entry_price}")
```

---

## Order Submission in Hedge Mode

### Using position_side Parameter

All orders in hedge mode need to specify which position they affect:

```python
# Opening/Adding to Long Position
self.buy = qty, price, 'long'
self.broker.buy_at_market(qty, position_side='long')
self.broker.buy_at(qty, price, position_side='long')

# Opening/Adding to Short Position
self.sell = qty, price, 'short'
self.broker.sell_at_market(qty, position_side='short')
self.broker.sell_at(qty, price, position_side='short')

# Closing Long Position (sell from long)
self.sell = qty, price, 'long'
self.broker.sell_at_market(qty, position_side='long')

# Closing Short Position (buy back short)
self.buy = qty, price, 'short'
self.broker.buy_at_market(qty, position_side='short')
```

### Stop-Loss and Take-Profit

```python
# For long position
self.stop_loss = qty, stop_price, 'long'
self.take_profit = qty, target_price, 'long'

# For short position
self.stop_loss = qty, stop_price, 'short'
self.take_profit = qty, target_price, 'short'
```

---

## How Hedge Mode Works

### Position Structure

**One-Way Mode (default)**:
```
Position (single object)
  ├─ qty: Can be positive (long) or negative (short)
  └─ One position at a time
```

**Hedge Mode**:
```
PositionPair (wrapper)
  ├─ long_position: Position(side='long')
  ├─ short_position: Position(side='short')
  └─ Both can be open simultaneously
```

### Order Routing

When an order executes:
1. Order has `position_side` attribute ('long' or 'short')
2. PositionPair routes order to correct sub-position
3. Only that position gets updated
4. Other position remains unchanged

### Trade Recording

The system tracks long and short trades separately:
- Each position (long/short) generates its own `ClosedTrade` record
- Trades are stored independently in `tempt_trades_long` and `tempt_trades_short`
- Final trades list shows both long and short trades with accurate PNL

---

## What Works

✅ **Simultaneous long + short positions** - Both can be open at the same time
✅ **Independent position management** - Each position tracks its own entry, PNL, etc.
✅ **Order routing** - Orders correctly route to the specified position
✅ **Trade recording** - Long and short trades recorded separately with accurate PNL
✅ **Net position calculation** - `net_qty = long_qty - short_qty`
✅ **Combined PNL** - `total_pnl = long_pnl + short_pnl`
✅ **Backtest results** - Trades show up correctly in results
✅ **Jesse website** - Works via HedgeModeTest strategy pattern

---

## What Doesn't Work Yet

❌ **Live Trading** - Not implemented (backtest only)
❌ **UI Config Field** - Jesse website doesn't expose `futures_position_mode` dropdown
⚠️ **Short qty sign** - Stored as negative, use `abs()` when reading

---

## Example Strategy: HedgeModeTest

The included test strategy demonstrates hedge mode:

**Timeline**:
- Candle 5: Open long position (1.0 contracts)
- Candle 10: Open short position (0.5 contracts) ← Long still open
- Candle 10-20: Both positions open simultaneously
- Candle 20: Close long position
- Candle 25: Close short position

**Expected Output**:
```
[2023-10-02T00:06:00] OPENED long position: qty: 1.0
[2023-10-02T00:11:00] OPENED short position: qty: 0.5
[2023-10-02T00:11:00] Long qty: 1.0, Short qty: 0.5, Net qty: 0.5  ← BOTH OPEN!
[2023-10-02T00:21:00] CLOSED a long trade: qty: 1.0, PNL: -1.64 (-0.95%)
[2023-10-02T00:26:00] CLOSED a short trade: qty: 0.5, PNL: 1.38 (1.59%)
```

---

## Implementation Details

### Files Modified

**Core Implementation**:
- `jesse/models/Position.py` - Added `side` parameter and trade recording with `position_side`
- `jesse/models/PositionPair.py` - New wrapper class managing dual positions
- `jesse/store/state_completed_trades.py` - Separate trade tracking for long/short
- `jesse/store/state_positions.py` - Creates PositionPair in hedge mode
- `jesse/services/broker.py` - Added `position_side` parameter to all methods
- `jesse/strategies/Strategy.py` - Order submission with position_side
- `jesse/config.py` - Added `futures_position_mode` config option

**Test Strategy**:
- `strategies/HedgeModeTest/__init__.py` - Example hedge mode strategy

### Configuration Option

```python
# In exchange config
config = {
    'futures_position_mode': 'hedge',  # or 'one-way' (default)
}
```

---

## Troubleshooting

### Problem: "Hedge Mode: False" in logs

**Cause**: Config doesn't have `futures_position_mode: 'hedge'`

**Solution**:
- Use HedgeModeTest strategy (auto-enables hedge mode)
- Or add `'futures_position_mode': 'hedge'` to config

### Problem: Short position opens but long closes

**Cause**: Running in one-way mode (default behavior)

**Solution**: Enable hedge mode in config

### Problem: Orders not executing in update_position()

**Cause**: Using `self.buy`/`self.sell` properties instead of broker

**Solution**: Use broker directly:
```python
self.broker.sell_at_market(qty, position_side='short')
```

### Problem: Short qty showing as negative

**Expected**: Short positions store qty as negative internally

**Solution**: Use `abs()` when reading:
```python
short_qty = abs(self.position.short_position.qty)
```

---

## Technical Architecture

For detailed technical implementation, see: `HEDGE_MODE_IMPLEMENTATION_PLAN.md`

For current status and known issues, see: `HEDGE_MODE_CURRENT_STATUS.md`

---

## Summary

Hedge mode is **fully functional for backtesting**. You can:
- Test hedge strategies on Jesse website using HedgeModeTest pattern
- Run backtests via Python API with `futures_position_mode: 'hedge'`
- Hold simultaneous long + short positions
- Track PNL independently for each position
- View accurate trade reports with both long and short trades

Live trading implementation is not included (backtest only).