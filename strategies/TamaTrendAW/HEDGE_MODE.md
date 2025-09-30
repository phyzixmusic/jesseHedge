# TamaTrendAW - Hedge Mode Implementation

## Overview

TamaTrendAW strategy now supports **true hedge mode** with simultaneous long and short positions on the same symbol. The strategy automatically detects if running in hedge mode and adjusts behavior accordingly.

## How It Works

### One-Way Mode vs Hedge Mode

**One-Way Mode (default)**:
- Only one position at a time (long OR short, never both)
- Opening a short while long is open → closes the long first
- Uses standard `self.buy` / `self.sell` properties

**Hedge Mode**:
- Can hold both long and short positions simultaneously
- Opening a short while long is open → both remain active
- Uses `broker` methods with `position_side` parameter
- Tracks positions independently via `PositionPair`

### Enabling Hedge Mode

#### Method 1: Config File (Recommended)
```python
# In your backtest config
config = {
    'futures_position_mode': 'hedge',  # Enable hedge mode
    'futures_leverage': 2,
    'futures_leverage_mode': 'cross',
    # ... other settings
}
```

#### Method 2: Auto-Enable (For Jesse Website)
Uncomment lines 15-26 in `__init__.py` to auto-enable hedge mode:
```python
def _enable_hedge_mode_for_all_exchanges():
    """Enable hedge mode for all futures exchanges in the config"""
    try:
        for exchange_name, exchange_config in config['env']['exchanges'].items():
            if exchange_config.get('type') == 'futures':
                exchange_config['futures_position_mode'] = 'hedge'
                print(f"[TamaTrendAW] ✅ Enabled hedge mode for: {exchange_name}")
    except Exception as e:
        print(f"[TamaTrendAW] ❌ Error enabling hedge mode: {e}")

# Execute at module import time
_enable_hedge_mode_for_all_exchanges()
```

## Strategy Logic

### Long Position Management
1. **Entry**: Opens when all bullish conditions met (TEMA crossovers, ADX, CMO)
2. **DCA**: Adds to position when conditions remain bullish (up to max % of balance)
3. **Exit**: Take-profit at entry + (ATR × multiplier)

### Hedge Position Management

#### Opening Hedge
Hedge opens when **both** conditions are met:
1. **Loss Threshold**: Long position is underwater by specified % (accounting for leverage)
2. **Bearish Signals**: Short-term trend, long-term trend, ADX, and CMO all bearish

**Hedge Size**: Configurable % of long position (default 50%)

#### Managing Hedge
The strategy monitors the hedge and closes it when:

**Condition 1: Profitable Hedge + Bullish Signals**
- Hedge is in profit AND
- All bullish signals appear (TEMA crossovers, ADX, CMO)
- **Action**: Close hedge and optionally rebalance long position

**Condition 2: Losing Hedge + Strong Long Recovery**
- Hedge is losing money BUT
- Long position profit can cover hedge loss + 10% buffer
- **Action**: Close hedge and optionally rebalance long position

#### Rebalancing (Optional)
When closing a profitable hedge:
1. Take % of hedge profits for rebalancing (default 80%)
2. Take % for profit realization (default 30%)
3. If long position still underwater:
   - Sell some underwater contracts
   - Rebuy same amount at current lower price
   - This improves average entry price using hedge profits

## Hedge Mode Implementation Details

### Key Changes

1. **Removed Manual Tracking** (lines 15-18 removed):
   ```python
   # OLD (removed):
   self.has_hedge = False
   self.hedge_contracts = 0
   self.hedge_entry_price = 0
   ```

2. **Added Property-Based Access**:
   ```python
   @property
   def has_hedge(self) -> bool:
       """Check if we have an actual hedge position"""
       return self.short_position_qty > 0

   @property
   def hedge_entry_price(self) -> float:
       """Get hedge entry price from PositionPair"""
       if self.is_hedge_mode and isinstance(self.position, PositionPair):
           if self.position.short_position.is_open:
               return self.position.short_position.entry_price
       return 0
   ```

3. **Updated Hedge Opening** (line 304-310):
   ```python
   # Open hedge using broker directly with position_side
   if self.is_hedge_mode:
       self.broker.sell_at_market(hedge_qty, position_side='short')
   else:
       # One-way mode: just sell to reduce position
       self.sell = hedge_qty, self.price
   ```

4. **Updated Hedge Closing** (line 381-387):
   ```python
   # Close the hedge position using broker with position_side
   if self.is_hedge_mode:
       self.broker.buy_at_market(hedge_qty, position_side='short')
   else:
       # One-way mode: buy to increase position
       self.buy = hedge_qty, self.price
   ```

5. **Updated Rebalancing** (lines 451-461):
   ```python
   # Sell underwater contracts at current price
   if self.is_hedge_mode:
       self.broker.sell_at_market(contracts_to_rebalance, position_side='long')
   else:
       self.sell = contracts_to_rebalance, self.price

   # Immediately rebuy the same amount at current price
   if self.is_hedge_mode:
       self.broker.buy_at_market(contracts_to_rebalance, position_side='long')
   else:
       self.buy = contracts_to_rebalance, self.price
   ```

### Backward Compatibility

The strategy **automatically detects** the mode and adjusts:
- In one-way mode: Uses standard order submission (`self.buy`, `self.sell`)
- In hedge mode: Uses broker methods with `position_side` parameter

**Result**: Strategy works in both modes without code changes!

## Hyperparameters

### Hedge-Specific Parameters
- `hedge_trigger_percent` (20-50%, default 30%): Loss threshold to trigger hedge
- `hedge_size_percent` (25-100%, default 50%): Hedge size as % of long position
- `profit_realization_percent` (10-40%, default 30%): % of hedge profit to realize
- `rebalance_percent` (60-90%, default 80%): % of hedge profit for rebalancing

### Position Sizing Parameters
- `initial_position_percent` (5-30%, default 20%): Initial position size
- `max_position_percent` (20-50%, default 30%): Maximum position size
- `dca_increment_percent` (2.5-15%, default 5%): DCA increment size

### Indicator Parameters
- `tema_short`, `tema_long`: Short-term TEMA periods
- `tema_4h_short`, `tema_4h_long`: Long-term (4h) TEMA periods
- `adx_threshold`: ADX strength threshold
- `cmo_upper`, `cmo_lower`: CMO overbought/oversold levels
- `atr_take_profit`: ATR multiplier for take-profit

## Watch List

The watch list shows:
- **Hedge Mode**: ON/OFF indicator (only shown if hedge mode active)
- **Market Sentiment**: Bullish/Bearish (manually set)
- **Short Term Trend**: 1 (up) or -1 (down)
- **Long Term Trend**: 1 (up) or -1 (down)
- **ADX**: Current ADX value
- **CMO**: Current CMO value
- **Has Hedge**: True/False (whether short position is open)
- **Long Contracts**: Current long position quantity
- **Hedge Contracts**: Current short position quantity

## Example Usage

### Python API
```python
from jesse import research
import jesse.helpers as jh

# Enable hedge mode
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
    'strategy': 'TamaTrendAW',
    'symbol': 'ETH-USDT',
    'timeframe': '1h'
}]

result = research.backtest(config, routes, [], candles)
```

### Jesse Website
1. Uncomment the auto-enable code (lines 15-26 in `__init__.py`)
2. Select TamaTrendAW strategy in UI
3. Run backtest - hedge mode will be automatically enabled

## Expected Behavior

### Hedge Mode Active
```
[2023-10-02T00:06:00] === ENTERING LONG POSITION (INITIAL) ===
[2023-10-02T00:06:00] Hedge Mode: True
[2023-10-02T00:06:00] Initial: 1.0 contracts ($2000.00 margin)

[2023-10-02T10:30:00] === OPENING HEDGE ===
[2023-10-02T10:30:00] Loss threshold reached: 32.5% >= 30.0%
[2023-10-02T10:30:00] Bearish signals confirmed
[2023-10-02T10:30:00] Hedge position opened successfully via broker (hedge mode)!

[2023-10-02T15:45:00] === CLOSING HEDGE ===
[2023-10-02T15:45:00] Hedge profitable + Bullish signals confirmed
[2023-10-02T15:45:00] Hedge closed via broker (hedge mode)
[2023-10-02T15:45:00] Rebalanced 15 contracts, improved position by $42.50
```

## Benefits of Hedge Mode

1. **Risk Protection**: Hedge short position protects against further downside
2. **Profit from Drops**: Make money on the way down via short position
3. **Better Average Entry**: Use hedge profits to rebalance long at better prices
4. **Flexibility**: Keep long position while market corrects
5. **No Forced Exits**: Don't have to close entire long position

## Notes

- Strategy works in both one-way and hedge modes
- Auto-detects mode and adjusts order submission accordingly
- Hedge only opens when both loss threshold and bearish signals met
- Hedge closes when either profitable + bullish OR losing but long recovered
- Rebalancing is optional and conservative (requires buffer)
- All positions tracked independently with accurate PNL

## Trade Recording

In hedge mode:
- Long trades recorded with correct type, quantity, and PNL
- Short trades recorded separately with correct type, quantity, and PNL
- Both appear in backtest results
- Metrics calculate correctly for both position types