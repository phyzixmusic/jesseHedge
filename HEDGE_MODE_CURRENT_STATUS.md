# Hedge Mode - Current Status

## ✅ What Works

### 1. Simultaneous Long + Short Positions
**CONFIRMED WORKING** - The backtest logs prove it:

```
[2023-10-02T00:06:00] OPENED long position: qty: 1.0
[2023-10-02T00:11:00] OPENED short position: qty: 0.5
[2023-10-02T00:11:00] Long qty: 1.0, Short qty: 0.5, Net qty: 0.5  ← BOTH OPEN!
```

### 2. Independent Position Management
- Long opened at candle 5 ✅
- Short opened at candle 10 (while long still open) ✅
- Long closed at candle 20 ✅
- Short closed at candle 25 ✅

### 3. Order Routing
Orders properly route to the correct position based on `position_side`:
- `position_side='long'` → Routes to long position ✅
- `position_side='short'` → Routes to short position ✅

### 4. PNL Tracking (Per Position)
Each position tracks its own PNL independently ✅

### 5. Net Position Calculation
Net qty = Long qty - Short qty (works correctly) ✅

---

## ⚠️ What Doesn't Work (Yet)

### 1. Trade Reporting System
**Issue**: Trades are recorded incorrectly or not at all.

**Evidence**:
```
[2023-10-02T00:21:00] CLOSED a short trade for Bybit USDT Perpetual-ETH-USDT:
qty: 1.5, entry_price: 1729.44, exit_price: 1730.17, PNL: -2.02
```

This should be recorded as a LONG trade, but it's showing as SHORT with wrong quantities.

**Root Cause**: The `CompletedTrades` system was designed for one-way mode and doesn't understand PositionPair. It's aggregating both positions into a single trade.

**Impact**:
- Trade reports show incorrect data
- Metrics (win rate, total trades, etc.) are wrong
- Can't properly analyze backtest performance

### 2. Metrics Calculation
Because trades aren't recorded properly:
- Total trades: Incorrect
- Win/loss ratio: Incorrect
- Average PNL: Incorrect
- Sharpe ratio: Incorrect

### 3. Short Position Quantity Sign
Short positions store qty as negative (-0.5) instead of positive (0.5).

**Workaround**: Use `abs(self.position.short_position.qty)`

---

## 🔧 Required Fixes for Full Hedge Mode Support

### Priority 1: Trade Recording

Need to modify `/jesse/store/state_completed_trades.py` to:

1. Detect when position is PositionPair
2. Track long and short trades separately
3. Record each trade when its specific position closes

**Current Code**:
```python
def close_trade(self, position: Position) -> None:
    # Only handles single Position
    # Doesn't understand PositionPair
```

**Needed**:
```python
def close_trade(self, position: Union[Position, PositionPair], position_side: str = None) -> None:
    if isinstance(position, PositionPair):
        if position_side == 'long':
            # Close long trade only
        elif position_side == 'short':
            # Close short trade only
    else:
        # Existing one-way logic
```

### Priority 2: Metrics System

Update metrics calculation in `/jesse/research/backtest.py` to:
- Count long and short trades separately
- Calculate combined PNL correctly
- Handle PositionPair in all metric calculations

### Priority 3: Position Quantity Consistency

Fix short position to store qty as positive:
- Update `Position._on_executed_order()` for short positions in hedge mode
- Ensure `short_position.qty` is always positive
- Update display logic if needed

---

## 🎯 Current Use Case

**Hedge mode currently works for:**
- ✅ Live monitoring of positions
- ✅ Testing hedge strategies
- ✅ Verifying position logic
- ✅ Calculating live PNL

**Hedge mode does NOT work for:**
- ❌ Accurate backtest reports
- ❌ Strategy optimization (metrics are wrong)
- ❌ Performance analysis
- ❌ Trade-by-trade review

---

## 💡 Workaround for Now

Until trade recording is fixed, you can:

1. **Monitor via Logs**: Check the strategy logs to see actual position behavior
2. **Calculate PNL Manually**:
   ```python
   long_pnl = self.position.long_position.pnl if self.long_position_qty > 0 else 0
   short_pnl = self.position.short_position.pnl if self.short_position_qty > 0 else 0
   total_pnl = long_pnl + short_pnl
   ```
3. **Track Positions Yourself**: Log position changes and calculate metrics externally

---

## 📋 Testing Checklist

### What to Verify ✅
- [x] Can open long position
- [x] Can open short position while long is open
- [x] Both positions show correct quantities
- [x] Can close long independently
- [x] Can close short independently
- [x] Orders route to correct position
- [x] Net position calculates correctly

### What's Broken ❌
- [ ] Trade report shows correct trades
- [ ] Metrics are accurate
- [ ] Can analyze backtest performance
- [ ] Short qty is positive (not negative)

---

## 🚀 Next Steps

### For Basic Usage (Current State)
The hedge mode **DOES work** for testing and understanding position behavior. You can:
1. Test hedge strategies
2. See positions open simultaneously
3. Monitor live PNL per position
4. Verify your strategy logic

### For Production Use
Need to fix trade recording before using for:
1. Strategy optimization
2. Performance analysis
3. Production deployment

### Recommended Approach
1. Continue testing strategies in hedge mode
2. Validate position logic works correctly
3. File issue or implement trade recording fixes
4. Re-test with proper metrics

---

## Summary

**Hedge mode core functionality: ✅ WORKING**
- Simultaneous positions work perfectly
- Order routing works correctly
- PNL tracking works per position

**Trade reporting: ❌ NEEDS WORK**
- Trades recorded incorrectly
- Metrics are wrong
- Can't properly analyze backtests

The infrastructure is solid, but the analytics layer needs updates to understand PositionPair.