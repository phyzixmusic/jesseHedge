# Phase 2: Order Routing - Progress Update

## ✅ Completed So Far

### 1. Order Model ✅
**File:** `jesse/models/Order.py`
- Added `position_side` field (CharField, nullable)
- Backwards compatible (None for one-way mode)
- Test: `tests/test_order_attribute_only.py` ✅

### 2. Exchange Interface ✅
**File:** `jesse/exchanges/exchange.py`
- Updated all order methods with `position_side` parameter
- Default value: `None` (backwards compatible)

### 3. Sandbox Driver ✅
**File:** `jesse/exchanges/sandbox/Sandbox.py`
- Updated `market_order()` to accept `position_side`
- Updated `limit_order()` to accept `position_side`
- Updated `stop_order()` to accept `position_side`
- All pass `position_side` to Order creation

## 🔄 In Progress

### API Layer
**File:** `jesse/services/api.py`
- Need to update to pass `position_side` parameter

### Broker Layer
**File:** `jesse/services/broker.py`
- Need to add `side` parameter to order methods

### Position Execution
**File:** `jesse/models/Position.py`
- Need to update `_on_executed_order()` to route to correct position in hedge mode

## 📊 Files Modified (Phase 2)

```
jesse/models/Order.py                  | +2 lines
jesse/exchanges/exchange.py            | +3 lines  
jesse/exchanges/sandbox/Sandbox.py     | +6 lines
tests/test_order_attribute_only.py     | +58 lines (NEW)
tests/test_order_position_side.py      | +183 lines (NEW, needs setup fix)
```

## 🎯 Next Steps

1. ✅ Update API layer
2. ✅ Update Broker methods
3. ✅ Update Position execution logic
4. ✅ Test order routing
5. ✅ Create integration test

**Status:** 50% complete - Core infrastructure ready, need to wire it all together!

---

**Last updated:** 2025-09-30 (Phase 2 in progress)



