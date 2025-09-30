# Hedge Mode - Phase 1 Complete! 🎉

## ✅ What We Built

We've successfully implemented the **core infrastructure** for hedge mode in Jesse. All changes are backwards compatible - existing one-way mode functionality is preserved.

### 1. Configuration Layer ✅
**File:** `jesse/config.py`

Added `futures_position_mode` option:
- Default: `'one-way'` (backwards compatible)
- New option: `'hedge'` (for dual positions)
- Integrated throughout config system

**Usage:**
```python
config = {
    'futures_leverage': 2,
    'futures_leverage_mode': 'cross',
    'futures_position_mode': 'hedge',  # NEW!
}
```

### 2. Position Model ✅
**File:** `jesse/models/Position.py`

Added optional `side` parameter:
- `side=None` → one-way mode (existing behavior)
- `side='long'` → hedge mode long position
- `side='short'` → hedge mode short position

Added `is_hedge_mode` property for convenience.

### 3. PositionPair Wrapper ✅
**File:** `jesse/models/PositionPair.py` (NEW)

Manages both long and short positions simultaneously:
- `long_position` - Position with side='long'
- `short_position` - Position with side='short'
- `net_qty` - Net exposure across both sides
- `total_pnl` - Combined PNL
- `get_position(side)` - Access specific side

### 4. State Management ✅
**File:** `jesse/store/state_positions.py`

Updated to support both modes:
- Checks `futures_position_mode` config
- Creates `Position` for one-way mode
- Creates `PositionPair` for hedge mode
- `count_open_positions()` handles both types

---

## 📊 Test Results

### All New Tests Passing:
```bash
✅ tests/test_config_position_mode.py - Config layer
✅ tests/test_position_side.py - Position model  
✅ tests/test_position_pair.py - PositionPair wrapper
✅ tests/test_state_positions_hedge.py - State management
```

### Test Coverage:
- ✅ Backwards compatibility (one-way mode still works)
- ✅ Hedge mode position creation
- ✅ Independent long/short positions
- ✅ Net quantity calculations
- ✅ PNL calculations
- ✅ State management for both modes

---

## 🔧 Files Modified

```
jesse/config.py                      | +5 lines
jesse/models/Position.py             | +8 lines
jesse/models/PositionPair.py         | +105 lines (NEW)
jesse/store/state_positions.py       | +14 lines
jesse/testing_utils.py               | +9 lines

tests/test_config_position_mode.py   | +94 lines (NEW)
tests/test_position_side.py          | +125 lines (NEW)
tests/test_position_pair.py          | +178 lines (NEW)
tests/test_state_positions_hedge.py  | +152 lines (NEW)
tests/test_hedge_mode_basics.py      | +167 lines (NEW framework)
```

**Total:**  
- Core code: ~140 lines added
- Test code: ~710 lines added
- All changes backwards compatible ✅

---

## 🎯 What Works Now

### One-Way Mode (Existing Behavior - Still Works):
```python
# Create position the old way
position = Position('Sandbox', 'BTC-USDT')
position.qty = 1.0  # Positive = long, Negative = short
```

### Hedge Mode (New Capability):
```python
# Create position pair
pair = PositionPair('Sandbox', 'BTC-USDT')

# Access long position
long_pos = pair.get_position('long')
long_pos.qty = 1.0

# Access short position  
short_pos = pair.get_position('short')
short_pos.qty = -0.5

# Check net exposure
print(pair.net_qty)  # 0.5 (1.0 - 0.5)

# Check combined PNL
print(pair.total_pnl)  # Sum of both positions
```

### State Management:
```python
# In your config
config['env']['exchanges']['Sandbox']['futures_position_mode'] = 'hedge'

# Jesse automatically creates PositionPair for hedge mode
from jesse.services import selectors
position = selectors.get_position('Sandbox', 'BTC-USDT')
# Returns PositionPair in hedge mode, Position in one-way mode
```

---

## 🚀 What's Next (Phase 2)

The infrastructure is ready! Next steps:

### 1. Order Routing (Critical)
- Update `Order` model to include `position_side`
- Modify `Sandbox` driver to route orders to correct position
- Update order execution logic

### 2. Broker Updates
- Add `side` parameter to broker methods
- `self.buy(..., side='long')` 
- `self.sell(..., side='short')`

### 3. Strategy API
- Add hedge mode methods:
  - `should_long_hedge()`
  - `should_short_hedge()`
  - `go_long_hedge()`
  - `go_short_hedge()`
- Access positions: `self.long_position`, `self.short_position`

### 4. Live Trading Integration
- Bybit API integration
- Position mode switching (`/v5/position/switch-mode`)
- Order submission with `positionIdx`

### 5. Testing & Validation
- Integration tests with order execution
- Backtest accuracy tests
- Live trading simulation

---

## 💡 Design Decisions Made

1. **Backwards Compatibility**: Default to 'one-way', no breaking changes
2. **Simple First**: Start with core infrastructure, add features incrementally
3. **Test-Driven**: Write tests as we build (710 lines of tests!)
4. **Minimal Changes**: Only modify what's necessary
5. **Clear Separation**: PositionPair wraps two Positions, clean abstraction

---

## 📝 Example: Simple Hedge Strategy (Future)

Once order routing is complete, you'll be able to do:

```python
class MyHedgeStrategy(Strategy):
    def should_long_hedge(self):
        return self.ema_cross == 'bullish'
    
    def should_short_hedge(self):
        return self.rsi < 30
    
    def go_long_hedge(self):
        qty = self.position_size
        self.buy = qty, self.price, 'long'  # Specify side
    
    def go_short_hedge(self):
        qty = self.position_size
        self.sell = qty, self.price, 'short'  # Specify side
```

---

## 🎉 Success Metrics

- ✅ All new tests passing (100%)
- ✅ Backwards compatible (existing code unaffected)
- ✅ Clean architecture (PositionPair wrapper)
- ✅ Documented and tested
- ✅ Ready for Phase 2

---

## 📊 Quick Start Guide

### Enable Hedge Mode in Backtest:
```python
from jesse import research

config = {
    'starting_balance': 10_000,
    'type': 'futures',
    'futures_leverage': 2,
    'futures_leverage_mode': 'cross',
    'futures_position_mode': 'hedge',  # Enable hedge mode
}

# Position state will automatically use PositionPair
```

### Check Position Mode:
```python
from jesse.services import selectors

position = selectors.get_position('Sandbox', 'BTC-USDT')

if isinstance(position, PositionPair):
    print("Hedge mode active!")
    print(f"Long: {position.long_position.qty}")
    print(f"Short: {position.short_position.qty}")
    print(f"Net: {position.net_qty}")
else:
    print("One-way mode active")
    print(f"Position: {position.qty}")
```

---

## 🙏 Next Session

Ready to continue with **Phase 2: Order Routing**!

This will enable actual trading in hedge mode by:
1. Adding `position_side` to orders
2. Routing orders to correct position (long vs short)
3. Updating order execution logic

**Estimated time:** 2-3 hours

---

**Phase 1 completed:** 2025-09-30  
**Status:** ✅ Infrastructure ready, tested, and documented  
**Next:** Order routing and execution



