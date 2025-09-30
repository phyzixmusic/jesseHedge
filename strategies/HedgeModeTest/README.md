# HedgeModeTest Strategy

## Purpose

This is a **test strategy** designed to verify that hedge mode (simultaneous long + short positions) works correctly in the Jesse framework.

## What It Does

1. **Candle 5**: Opens a LONG position (1.0 contracts)
2. **Candle 10**: Opens a SHORT position (0.5 contracts) **while long is still open**
3. **Candle 10-20**: Both positions exist simultaneously
4. **Candle 20**: Closes the LONG position
5. **Candle 25**: Closes the SHORT position

## How to Use on Jesse Website

### Step 1: Upload Strategy

Upload this strategy to the Jesse website.

### Step 2: Run Backtest

Simply select `HedgeModeTest` as your strategy and run the backtest normally.

**No special configuration needed!** The strategy automatically enables hedge mode when it's imported.

### Step 3: Verify Hedge Mode is Active

Check the logs for:

```
[HedgeModeTest] ✅ Enabled hedge mode for: Bybit USDT Perpetual
[2023-XX-XXT00:06:00] Hedge Mode: True  ← Should show True
```

### Step 4: Verify Simultaneous Positions

Look for logs like:

```
[2023-XX-XXT00:10:00] === OPENING SHORT (HEDGE) POSITION ===
[2023-XX-XXT00:10:00] Long qty: 1.0
[2023-XX-XXT00:10:00] Short qty to open: 0.5

[2023-XX-XXT00:15:00] --- Position Status (Index 15) ---
[2023-XX-XXT00:15:00] Long: 1.0, Short: 0.5  ← BOTH OPEN!
[2023-XX-XXT00:15:00] Net: 0.5
[2023-XX-XXT00:15:00] Total PNL: $XX.XX
```

## Key Feature: Auto-Enable Hedge Mode

This strategy uses a special technique to enable hedge mode without modifying the backtest configuration:

```python
def _enable_hedge_mode_for_all_exchanges():
    """Enable hedge mode for all futures exchanges in the config"""
    for exchange_name, exchange_config in config['env']['exchanges'].items():
        if exchange_config.get('type') == 'futures':
            exchange_config['futures_position_mode'] = 'hedge'

# Execute at module import time (before strategy is instantiated)
_enable_hedge_mode_for_all_exchanges()
```

This runs **at module load time**, before the strategy object is created, ensuring hedge mode is enabled before positions are initialized.

## Expected Results

### Trade Summary

You should see **2 separate trades**:

1. **Long Trade**:
   - Entry: Candle 5
   - Exit: Candle 20
   - Result: Depends on price movement

2. **Short Trade**:
   - Entry: Candle 10
   - Exit: Candle 25
   - Result: Depends on price movement

### Position Chart

The position chart should show:
- Long qty line going from 0 → 1.0 → back to 0
- Short qty line going from 0 → 0.5 → back to 0
- **Overlapping period** where both are non-zero (candles 10-20)

## Applying This to Your Own Strategies

To enable hedge mode in your own strategy, add this code at the **module level** (before the class definition):

```python
from jesse.config import config

# Enable hedge mode for all futures exchanges
for exchange_name, exchange_config in config['env']['exchanges'].items():
    if exchange_config.get('type') == 'futures':
        exchange_config['futures_position_mode'] = 'hedge'
        print(f"[{__name__}] Enabled hedge mode for: {exchange_name}")

class YourStrategy(Strategy):
    # Your strategy code...
```

Then in your strategy methods:

```python
def go_long(self):
    # For hedge mode, specify position_side as 3rd parameter
    if self.is_hedge_mode:
        self.buy = qty, price, 'long'
    else:
        self.buy = qty, price

def update_position(self):
    # Open a short hedge while long is still open
    if self.is_hedge_mode and self.long_position_qty > 0:
        self.sell = qty, price, 'short'  # Opens short position
```

## Troubleshooting

### "Hedge Mode: False" in logs

**Problem**: Strategy wasn't imported correctly, or module-level code didn't run.

**Solution**: Make sure you're using the latest version of the strategy file.

---

### Short position closes long instead of opening separately

**Problem**: Hedge mode isn't actually enabled.

**Solution**: Check for the "[HedgeModeTest] ✅ Enabled hedge mode" message in logs.

---

### Only seeing 1 trade instead of 2

**Problem**: Running in one-way mode.

**Solution**: Verify "Hedge Mode: True" appears in the logs.

---

## Notes

- This strategy is for **testing purposes only**, not for actual trading
- It uses simple index-based triggers, not real technical analysis
- The goal is to verify hedge mode infrastructure works correctly