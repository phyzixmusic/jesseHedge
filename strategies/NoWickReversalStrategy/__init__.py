import numpy as np
import jesse.indicators as ta
from jesse.strategies import Strategy
from jesse.enums import sides
from jesse import utils

class NoWickReversalStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.no_wick_levels = []  # Store detected no-wick levels
        self.last_processed_candle = None
        self.current_signal = None
        self.signal_candle_time = None

    def before(self):
        """Called before should_long/should_short on each candle."""
        self._update_no_wick_levels()
        # Reset signal cache for new candle
        current_time = self.current_candle[0]
        if self.signal_candle_time != current_time:
            self.current_signal = None
            self.signal_candle_time = current_time

    def _update_no_wick_levels(self):
        """Detect and store no-wick candle levels for potential reversals."""
        current_time = self.current_candle[0]

        # Skip if we already processed this candle
        if self.last_processed_candle == current_time:
            return

        self.last_processed_candle = current_time

        # Look back to find no-wick candles
        lookback = self.lookback_candles
        if len(self.candles) < lookback + 1:
            return

        # Clean old levels (older than max_level_age candles)
        cutoff_time = current_time - (self.max_level_age * 3600000)  # 1h = 3600000ms
        self.no_wick_levels = [level for level in self.no_wick_levels
                              if level['time'] > cutoff_time]

        # Check recent candles for no-wick patterns
        for i in range(1, min(lookback + 1, len(self.candles))):
            candle = self.candles[-i]
            timestamp, open_price, close_price, high, low, volume = candle

            # Skip if we already have this level
            if any(level['time'] == timestamp for level in self.no_wick_levels):
                continue

            # Check for bullish no-wick (open == low)
            if abs(open_price - low) <= self.wick_tolerance * open_price:
                if close_price > open_price:  # Bullish candle
                    level = {
                        'time': timestamp,
                        'price': open_price,
                        'type': 'bullish',
                        'tapped': False
                    }
                    self.no_wick_levels.append(level)
                    self.log(f"[NoWick] Found bullish no-wick level at {open_price:.5f}", log_type='info')

            # Check for bearish no-wick (open == high)
            elif abs(open_price - high) <= self.wick_tolerance * open_price:
                if close_price < open_price:  # Bearish candle
                    level = {
                        'time': timestamp,
                        'price': open_price,
                        'type': 'bearish',
                        'tapped': False
                    }
                    self.no_wick_levels.append(level)
                    self.log(f"[NoWick] Found bearish no-wick level at {open_price:.5f}", log_type='info')

    def _check_level_tap(self, level_price, tap_tolerance):
        """Check if current price is tapping a level."""
        current_price = self.price
        distance = abs(current_price - level_price) / level_price
        return distance <= tap_tolerance

    def _has_fvg_confluence(self, direction):
        """Check for Fair Value Gap confluence (optional confirmation)."""
        if not self.use_fvg_confirmation:
            return True

        # Look for FVG in the last few candles
        if len(self.candles) < 3:
            return False

        # Check last 3 candles for FVG pattern
        c1, c2, c3 = self.candles[-3:]

        if direction == 'long':
            # Bullish FVG: c1[4] (low) > c3[3] (high)
            if c1[4] > c3[3]:  # Gap exists
                gap_bottom = c3[3]
                gap_top = c1[4]
                current_price = self.price
                # Check if we're trading within or near the FVG
                if gap_bottom <= current_price <= gap_top:
                    self.log(f"[NoWick] Bullish FVG confluence found: {gap_bottom:.5f} - {gap_top:.5f}", log_type='info')
                    return True
        else:
            # Bearish FVG: c1[3] (high) < c3[4] (low)
            if c1[3] < c3[4]:  # Gap exists
                gap_bottom = c1[3]
                gap_top = c3[4]
                current_price = self.price
                # Check if we're trading within or near the FVG
                if gap_bottom <= current_price <= gap_top:
                    self.log(f"[NoWick] Bearish FVG confluence found: {gap_bottom:.5f} - {gap_top:.5f}", log_type='info')
                    return True

        return False

    def _get_trade_signal(self):
        """Determine trade signal ensuring no conflicts between long/short."""
        if self.position.is_open or not self.no_wick_levels:
            return None

        # Trade filtering: Only trade significant levels with good risk/reward
        if not self._trade_conditions_met():
            return None

        bullish_signals = []
        bearish_signals = []

        # Collect all valid signals from significant levels only
        for level in self.no_wick_levels:
            if (not level['tapped'] and
                self._check_level_tap(level['price'], self.tap_tolerance) and
                self._is_significant_level(level)):

                if level['type'] == 'bullish' and self._has_fvg_confluence('long'):
                    bullish_signals.append(level)
                elif level['type'] == 'bearish' and self._has_fvg_confluence('short'):
                    bearish_signals.append(level)

        # Priority: Choose the most recent signal (highest timestamp)
        if bullish_signals and bearish_signals:
            latest_bullish = max(bullish_signals, key=lambda x: x['time'])
            latest_bearish = max(bearish_signals, key=lambda x: x['time'])

            if latest_bullish['time'] >= latest_bearish['time']:
                latest_bullish['tapped'] = True
                self.log(f"[NoWick] LONG signal at level {latest_bullish['price']:.5f} (priority over bearish)", log_type='info')
                return 'long'
            else:
                latest_bearish['tapped'] = True
                self.log(f"[NoWick] SHORT signal at level {latest_bearish['price']:.5f} (priority over bullish)", log_type='info')
                return 'short'
        elif bullish_signals:
            latest_bullish = max(bullish_signals, key=lambda x: x['time'])
            latest_bullish['tapped'] = True
            self.log(f"[NoWick] LONG signal at level {latest_bullish['price']:.5f}", log_type='info')
            return 'long'
        elif bearish_signals:
            latest_bearish = max(bearish_signals, key=lambda x: x['time'])
            latest_bearish['tapped'] = True
            self.log(f"[NoWick] SHORT signal at level {latest_bearish['price']:.5f}", log_type='info')
            return 'short'

        return None

    def _trade_conditions_met(self):
        """Check if general trading conditions are favorable."""
        # Only trade when ATR is reasonable (not too low/high volatility)
        current_atr = self.atr
        if current_atr < self.min_atr_threshold or current_atr > self.max_atr_threshold:
            return False

        return True

    def _is_significant_level(self, level):
        """Check if a no-wick level is significant enough to trade."""
        current_price = self.price
        level_price = level['price']

        # Level should be at least min_level_distance away from current price
        distance = abs(current_price - level_price) / current_price
        if distance < self.min_level_distance:
            return False

        # Level should not be too old
        current_time = self.current_candle[0]
        level_age_hours = (current_time - level['time']) / 3600000
        if level_age_hours > self.max_significant_level_age:
            return False

        return True

    def should_long(self) -> bool:
        """Enter long when price taps bullish no-wick level."""
        if self.current_signal is None:
            self.current_signal = self._get_trade_signal()
        return self.current_signal == 'long'

    def should_short(self) -> bool:
        """Enter short when price taps bearish no-wick level."""
        if self.current_signal is None:
            self.current_signal = self._get_trade_signal()
        return self.current_signal == 'short'

    def go_long(self):
        """Execute long position with risk management."""
        entry_price = self.price
        stop_loss_price = entry_price - (self.atr * self.stop_loss_atr_multiplier)

        # Calculate position size using risk management
        # risk_to_qty already accounts for leverage in the calculation
        qty = utils.risk_to_qty(
            self.available_margin * (self.margin_percent / 100),
            self.risk_percent,
            entry_price,
            stop_loss_price,
            fee_rate=self.fee_rate
        )

        self.buy = qty, entry_price

    def go_short(self):
        """Execute short position with risk management."""
        entry_price = self.price
        stop_loss_price = entry_price + (self.atr * self.stop_loss_atr_multiplier)

        # Calculate position size using risk management
        # risk_to_qty already accounts for leverage in the calculation
        qty = utils.risk_to_qty(
            self.available_margin * (self.margin_percent / 100),
            self.risk_percent,
            entry_price,
            stop_loss_price,
            fee_rate=self.fee_rate
        )

        self.sell = qty, entry_price

    def on_open_position(self, order) -> None:
        """Set stop loss and take profit when position opens."""
        entry_price = self.position.entry_price

        if self.is_long:
            stop_loss_price = entry_price - (self.atr * self.stop_loss_atr_multiplier)
            take_profit_price = entry_price + (self.atr * self.stop_loss_atr_multiplier * self.risk_reward_ratio)
        else:
            stop_loss_price = entry_price + (self.atr * self.stop_loss_atr_multiplier)
            take_profit_price = entry_price - (self.atr * self.stop_loss_atr_multiplier * self.risk_reward_ratio)

        self.stop_loss = self.position.qty, stop_loss_price
        self.take_profit = self.position.qty, take_profit_price

        side = 'LONG' if self.is_long else 'SHORT'
        self.log(f"[NoWick] {side} position opened. Entry: {entry_price:.5f}, SL: {stop_loss_price:.5f}, TP: {take_profit_price:.5f}", log_type='info')

    def _get_pip_value(self):
        """Calculate pip value based on the symbol."""
        # For NASDAQ (US30, NAS100), 1 pip = 0.1 points
        # For forex pairs, 1 pip = 0.0001 (or 0.01 for JPY pairs)
        if 'NAS' in self.symbol or 'US30' in self.symbol:
            return 0.1
        elif 'JPY' in self.symbol:
            return 0.01
        else:
            return 0.0001

    def should_cancel_entry(self) -> bool:
        """Cancel entry orders if conditions change."""
        return False

    @property
    def atr(self):
        """Average True Range for dynamic stop losses."""
        return ta.atr(self.candles)

    # Hyperparameters
    @property
    def lookback_candles(self):
        """Number of candles to look back for no-wick patterns."""
        return self.hp.get('lookback_candles', 20)

    @property
    def max_level_age(self):
        """Maximum age of levels in hours before they expire."""
        return self.hp.get('max_level_age', 24)

    @property
    def wick_tolerance(self):
        """Tolerance for considering a candle as having no wick (as fraction of price)."""
        return self.hp.get('wick_tolerance', 0.0001)

    @property
    def tap_tolerance(self):
        """Tolerance for considering price as tapping a level (as fraction of price)."""
        return self.hp.get('tap_tolerance', 0.0005)

    @property
    def stop_loss_atr_multiplier(self):
        """Stop loss distance as ATR multiplier."""
        return self.hp.get('stop_loss_atr_multiplier', 2.0)

    @property
    def risk_reward_ratio(self):
        """Risk to reward ratio."""
        return self.hp.get('risk_reward_ratio', 2.0)

    @property
    def risk_percent(self):
        """Risk percentage per trade."""
        return self.hp.get('risk_percent', 2.0)

    @property
    def margin_percent(self):
        """Percentage of available margin to use."""
        return self.hp.get('margin_percent', 50.0)

    @property
    def use_fvg_confirmation(self):
        """Whether to use FVG as confirmation signal."""
        return self.hp.get('use_fvg_confirmation', False)

    @property
    def min_atr_threshold(self):
        """Minimum ATR to allow trading."""
        return self.hp.get('min_atr_threshold', 0.1)

    @property
    def max_atr_threshold(self):
        """Maximum ATR to allow trading."""
        return self.hp.get('max_atr_threshold', 10.0)

    @property
    def min_level_distance(self):
        """Minimum distance from current price to trade a level."""
        return self.hp.get('min_level_distance', 0.0001)

    @property
    def max_significant_level_age(self):
        """Maximum age in hours for a level to be considered significant."""
        return self.hp.get('max_significant_level_age', 24)

    @property
    def leverage(self):
        """Leverage multiplier for position sizing."""
        return self.hp.get('leverage', 10)

    # def dna(self):
        # """Optimized DNA parameters from the optimization results."""
        # return "eyJsb29rYmFja19jYW5kbGVzIjogMTgsICJtYXJnaW5fcGVyY2VudCI6IDEwMC4wLCAibWF4X2F0cl90aHJlc2hvbGQiOiA4LjAsICJtYXhfbGV2ZWxfYWdlIjogMjQsICJtYXhfc2lnbmlmaWNhbnRfbGV2ZWxfYWdlIjogOCwgIm1pbl9hdHJfdGhyZXNob2xkIjogMS41MDAwMDAwMDAwMDAwMDAyLCAibWluX2xldmVsX2Rpc3RhbmNlIjogMC4wMDA2MDAwMDAwMDAwMDAwMDAxLCAicmlza19wZXJjZW50IjogNC4wLCAicmlza19yZXdhcmRfcmF0aW8iOiAyLjgsICJzdG9wX2xvc3NfYXRyX211bHRpcGxpZXIiOiAxLjksICJ0YXBfdG9sZXJhbmNlIjogMC4wMDA4LCAidXNlX2Z2Z19jb25maXJtYXRpb24iOiBmYWxzZSwgIndpY2tfdG9sZXJhbmNlIjogMC4wMDA0NjAwMDAwMDAwMDAwMDAwN30="
        # return "eyJsZXZlcmFnZSI6IDEwMSwgImxvb2tiYWNrX2NhbmRsZXMiOiAyOCwgIm1hcmdpbl9wZXJjZW50IjogNDAuMCwgIm1heF9hdHJfdGhyZXNob2xkIjogNS41LCAibWF4X2xldmVsX2FnZSI6IDQ4LCAibWF4X3NpZ25pZmljYW50X2xldmVsX2FnZSI6IDIwLCAibWluX2F0cl90aHJlc2hvbGQiOiAwLjksICJtaW5fbGV2ZWxfZGlzdGFuY2UiOiAwLjAwMDYwMDAwMDAwMDAwMDAwMDEsICJyaXNrX3BlcmNlbnQiOiAzLjAsICJyaXNrX3Jld2FyZF9yYXRpbyI6IDIuNSwgInN0b3BfbG9zc19hdHJfbXVsdGlwbGllciI6IDEuNCwgInRhcF90b2xlcmFuY2UiOiAwLjAwMDcwMDAwMDAwMDAwMDAwMDEsICJ1c2VfZnZnX2NvbmZpcm1hdGlvbiI6IGZhbHNlLCAid2lja190b2xlcmFuY2UiOiAwLjAwMDEyMDAwMDAwMDAwMDAwMDAyfQ=="

    def hyperparameters(self) -> list:
        """Parameters for optimization."""
        return [
            {
                'name': 'lookback_candles',
                'type': int,
                'min': 10,
                'max': 50,
                'default': 20,
                'step': 1
            },
            {
                'name': 'max_level_age',
                'type': int,
                'min': 12,
                'max': 72,
                'default': 24,
                'step': 6
            },
            {
                'name': 'wick_tolerance',
                'type': float,
                'min': 0.00005,
                'max': 0.0005,
                'default': 0.0001,
                'step': 0.00001
            },
            {
                'name': 'tap_tolerance',
                'type': float,
                'min': 0.0001,
                'max': 0.001,
                'default': 0.0005,
                'step': 0.0001
            },
            {
                'name': 'stop_loss_atr_multiplier',
                'type': float,
                'min': 1.0,
                'max': 4.0,
                'default': 2.0,
                'step': 0.1
            },
            {
                'name': 'risk_reward_ratio',
                'type': float,
                'min': 1.5,
                'max': 3.0,
                'default': 2.0,
                'step': 0.1
            },
            {
                'name': 'risk_percent',
                'type': float,
                'min': 1.0,
                'max': 5.0,
                'default': 2.0,
                'step': 0.5
            },
            {
                'name': 'margin_percent',
                'type': float,
                'min': 25.0,
                'max': 100.0,
                'default': 50.0,
                'step': 5.0
            },
            {
                'name': 'use_fvg_confirmation',
                'type': 'categorical',
                'options': [True, False],
                'default': False
            },
            {
                'name': 'min_atr_threshold',
                'type': float,
                'min': 0.1,
                'max': 2.0,
                'default': 0.1,
                'step': 0.1
            },
            {
                'name': 'max_atr_threshold',
                'type': float,
                'min': 3.0,
                'max': 10.0,
                'default': 10.0,
                'step': 0.5
            },
            {
                'name': 'min_level_distance',
                'type': float,
                'min': 0.0005,
                'max': 0.005,
                'default': 0.0001,
                'step': 0.0001
            },
            {
                'name': 'max_significant_level_age',
                'type': int,
                'min': 6,
                'max': 24,
                'default': 24,
                'step': 2
            },
            {
                'name': 'leverage',
                'type': int,
                'min': 1,
                'max': 300,
                'default': 50,
                'step': 5
            }
        ]
