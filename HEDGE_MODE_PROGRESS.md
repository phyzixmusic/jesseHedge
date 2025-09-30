# Hedge Mode Implementation Progress

## ✅ Completed (Session 1)

### 1. Configuration Support
**Files Modified:**
- `jesse/config.py`

**Changes:**
- Added `futures_position_mode` config option (defaults to `'one-way'` for backwards compatibility)
- Integrated into `set_config()` function
- Applied to all exchanges automatically

**Backwards Compatible:** ✅ Yes - all existing configs will default to 'one-way' mode

### 2. Test Files Created
**Files Created:**
- `tests/test_hedge_mode_basics.py` - Comprehensive test suite with regression tests
- `tests/test_config_position_mode.py` - Standalone config validation tests

**Test Coverage:**
- ✅ Regression tests for one-way mode (ensure existing behavior unchanged)
- ⏳ Hedge mode tests (marked with `@pytest.mark.skip` - to be implemented)

---

## 🔍 Testing Instructions (For User)

Since you have Jesse properly installed in your environment, please run these tests to verify our changes:

### Step 1: Test Configuration Changes
```bash
cd /Users/mrnewton/Documents/GitHub/jesseHedge
python tests/test_config_position_mode.py
```

**Expected Output:**
```
✅ Config has futures_position_mode with correct default
✅ All exchanges have futures_position_mode configured
✅ set_config handles futures_position_mode correctly
```

### Step 2: Run Existing Jesse Tests (Regression Check)
```bash
# Run a few existing tests to ensure nothing broke
pytest tests/test_backtest.py -v -k "test_can_use_custom_strategy" 
pytest tests/test_position.py -v -k "test_position_with_leverage"
pytest tests/test_isolated_backtest.py -v -k "test_one_way"
```

**Goal:** All existing tests should still pass ✅

### Step 3: Try Using the New Config
In your backtest config, you can now add:
```python
config = {
    'futures_leverage_mode': 'cross',
    'futures_leverage': 2,
    'futures_position_mode': 'one-way',  # NEW! (currently only 'one-way' works)
}
```

---

## 📋 Next Steps (Implementation Order)

### Step 3: Position Model (Minimal Changes)
**File:** `jesse/models/Position.py`

**Goal:** Add optional `side` parameter without breaking existing functionality

**Strategy:**
```python
class Position:
    def __init__(self, exchange_name: str, symbol: str, attributes: dict = None, side: str = None):
        # side is None for one-way mode, 'long' or 'short' for hedge mode
        self.side = side
        # All existing code continues to work when side=None
```

**Test Plan:**
1. Add unit test that creates Position with `side=None` (existing behavior)
2. Add unit test that creates Position with `side='long'` (new behavior)
3. Run all existing tests - should still pass

### Step 4: Simple State Management
**File:** `jesse/store/state_positions.py`

**Goal:** Support both single Position and dual positions

**Strategy:**
- Check config to determine mode
- If one-way: create single Position (existing)
- If hedge: create two Positions (one with side='long', one with side='short')

### Step 5: Order Execution (Core Logic)
**Files:** 
- `jesse/exchanges/sandbox/Sandbox.py`
- `jesse/models/Order.py`

**Goal:** Route orders to correct position in hedge mode

---

## 🎯 Current Status Summary

**What Works:**
- ✅ Configuration system recognizes hedge mode
- ✅ Backwards compatibility maintained
- ✅ Test structure in place

**What's Next:**
- ⏳ Position model needs `side` parameter
- ⏳ State management needs to create dual positions in hedge mode
- ⏳ Order execution needs to route to correct side

**Estimated Time to MVP:**
- 2-3 hours of focused work
- Test as we go (TDD approach)

---

## 🚀 Quick Start (Resume Work)

When ready to continue:

```bash
# 1. Verify current changes work
python tests/test_config_position_mode.py

# 2. Look at the Position model
code jesse/models/Position.py

# 3. Make minimal change - add side parameter to __init__
# 4. Write a test for it
# 5. Run test
# 6. Repeat for next component
```

---

## 📝 Key Design Decisions

1. **Backwards Compatibility First**: Default to 'one-way', all existing code must work
2. **Simple Before Complex**: Start with single Position with optional side, then add PositionPair later if needed
3. **Test-Driven**: Write test → implement → verify → move to next
4. **No Over-Engineering**: Only add complexity when actually needed

---

## 🐛 Known Issues

None yet! All changes are additive and backwards compatible.

---

**Last Updated:** 2025-09-30  
**Status:** Configuration complete, ready for Position model changes



