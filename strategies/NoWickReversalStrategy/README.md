# No-Wick Reversal Strategy

A trading strategy based on price reversals at no-wick candle levels with optional Fair Value Gap (FVG) confirmation.

## Strategy Concept

This strategy identifies candles with no wicks (where open equals low for bullish candles, or open equals high for bearish candles) and waits for price to "tap" back into these levels for potential reversal trades.

### Key Features

1. **No-Wick Detection**: Identifies candles where:
   - Bullish: Open ≈ Low (no bottom wick)
   - Bearish: Open ≈ High (no top wick)

2. **Level Management**: Tracks and manages no-wick levels with configurable expiration

3. **Tap Detection**: Monitors price action for taps into stored levels

4. **FVG Confirmation**: Optional Fair Value Gap confluence for higher probability setups

5. **Risk Management**: 
   - ATR-based dynamic stop losses (1-4x ATR multiplier)
   - 2:1 risk-reward ratio
   - Position sizing based on risk percentage

## Strategy Logic

### Entry Conditions

**Long Entry:**
- Price taps a bullish no-wick level (previous candle's open/low)
- Optional FVG confluence in the same direction
- No existing position

**Short Entry:**
- Price taps a bearish no-wick level (previous candle's open/high)  
- Optional FVG confluence in the same direction
- No existing position

### Exit Conditions

- **Stop Loss**: 1-4x ATR from entry (configurable)
- **Take Profit**: 2:1 risk-reward ratio (configurable)

## Hyperparameters

| Parameter | Type | Range | Default | Description |
|-----------|------|-------|---------|-------------|
| lookback_candles | int | 10-50 | 20 | Candles to scan for no-wick patterns |
| max_level_age | int | 12-72 | 24 | Hours before levels expire |
| wick_tolerance | float | 0.00005-0.0005 | 0.0001 | Tolerance for no-wick detection |
| tap_tolerance | float | 0.0001-0.001 | 0.0005 | Tolerance for level tap detection |
| stop_loss_atr_multiplier | float | 1.0-4.0 | 2.0 | Stop loss distance as ATR multiplier |
| risk_reward_ratio | float | 1.5-3.0 | 2.0 | Risk to reward ratio |
| risk_percent | float | 1.0-5.0 | 2.0 | Risk per trade as % of margin |
| margin_percent | float | 25.0-100.0 | 50.0 | Margin allocation percentage |
| use_fvg_confirmation | bool | True/False | False | Enable FVG confirmation |
| min_atr_threshold | float | 0.1-2.0 | 0.5 | Minimum ATR to allow trading |
| max_atr_threshold | float | 3.0-10.0 | 5.0 | Maximum ATR to allow trading |
| min_level_distance | float | 0.0005-0.005 | 0.001 | Min distance from price to trade level |
| max_significant_level_age | int | 6-24 | 12 | Max age for significant levels (hours) |

## Target Markets

- **Primary**: NASDAQ 1-hour timeframe
- **Secondary**: Any liquid market with clear price action
- **Timeframes**: 1H (primary), 4H (alternative)

## Implementation Notes

1. **Level Storage**: Maintains a dynamic list of no-wick levels with automatic cleanup
2. **FVG Detection**: Implements 3-candle FVG pattern detection for confluence
3. **Pip Calculation**: Adapts pip values based on symbol type (Forex, Indices)
4. **Position Management**: Uses Jesse's built-in risk management utilities

## Usage

```python
# The strategy can be used directly with Jesse framework
# Hyperparameters can be optimized using Jesse's genetic algorithm
# Backtesting can be performed on 1H NASDAQ data
```

## Risk Warnings

- This strategy is designed for backtesting and optimization
- Always test thoroughly before live trading
- Past performance does not guarantee future results
- Consider market conditions and volatility when using this strategy