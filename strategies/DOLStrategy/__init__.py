import numpy as np
from jesse.strategies import Strategy
from jesse.enums import sides
from jesse import utils
import jesse.indicators as ta

class DOLStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.dol = None  # Decisive Operating Line
        self.bias = None  # 'long' or 'short'
        self.entry_bars_count = 0  # Track bars since position opened for time stop
        
    def _calculate_dol_and_bias(self):
        """Calculate DOL and bias from last two fully closed candles."""
        if len(self.candles) < 3:
            return None, None
            
        # Get last two fully closed candles ([-2] and [-1])
        candle_2 = self.candles[-3]  # C[-2]
        candle_1 = self.candles[-2]  # C[-1]
        
        _, o2, c2, h2, l2, _ = candle_2
        _, o1, c1, h1, l1, _ = candle_1
        
        # Priority rule: sweep-failure overrides everything
        # Bearish sweep-failure: H[-1] > H[-2] and C[-1] <= C[-2]
        if h1 > h2 and c1 <= c2:
            return l1, 'short'  # DOL = L[-1], bias = short
            
        # Bullish sweep-failure: L[-1] < L[-2] and C[-1] >= C[-2]
        if l1 < l2 and c1 >= c2:
            return h1, 'long'   # DOL = H[-1], bias = long
            
        # No sweep-failure, check body momentum
        if c1 > c2:
            return h1, 'long'   # Body momentum up: bias = long, DOL = H[-1]
        elif c1 < c2:
            return l1, 'short'  # Body momentum down: bias = short, DOL = L[-1]
        else:
            return None, None   # C[-1] == C[-2], skip until next bar
    
    def _calculate_stop_loss(self, entry_price):
        """Calculate stop-loss using structure-based or ATR method."""
        if len(self.candles) < 2:
            return None
            
        if self.use_atr_stops:
            # Use ATR-based stop loss
            atr = ta.atr(self.candles, self.atr_period)
            if self.bias == 'long':
                sl_price = entry_price - (atr * self.atr_stop_multiplier)
            else:  # short
                sl_price = entry_price + (atr * self.atr_stop_multiplier)
        else:
            # Use structure-based stop loss (original method)
            candle_1 = self.candles[-2]  # C[-1]
            _, o1, c1, h1, l1, _ = candle_1
            
            buffer = self.buffer_ticks * self.tick_size
            
            if self.bias == 'long':
                # LONG SL: min(L[-1], DOL) - buffer
                sl_price = min(l1, self.dol) - buffer
            else:  # short
                # SHORT SL: max(H[-1], DOL) + buffer  
                sl_price = max(h1, self.dol) + buffer
            
        return sl_price
    
    def _calculate_position_size(self, entry_price, stop_loss_price):
        """Calculate position size optimized for backtesting."""
        
        # Validate inputs
        if not entry_price or not stop_loss_price:
            return 0
            
        risk_per_unit = abs(entry_price - stop_loss_price)
        if risk_per_unit <= 0:
            return 0
        
        # Check if using full balance mode
        if self.use_full_balance:
            # Use entire available margin with leverage multiplier
            capital = self.available_margin * self.leverage_multiplier
            qty = utils.size_to_qty(capital, entry_price, fee_rate=self.fee_rate)
        else:
            # Use percentage-based risk management
            qty = utils.risk_to_qty(
                capital=self.available_margin,
                risk_per_capital=self.risk_percent,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price,
                fee_rate=self.fee_rate
            )
            # Apply leverage multiplier to position size
            qty *= self.leverage_multiplier
        
        # Ensure quantity is positive and meets minimum requirements
        qty = abs(qty)
        
        # Minimum quantity check for backtesting
        if qty < 0.001:
            return 0
            
        return round(qty, 6)  # Round to 6 decimal places
    
    def before(self):
        """Called before should_long/should_short on each candle."""
        self.dol, self.bias = self._calculate_dol_and_bias()
        
        # Track bars since position opened for time stop
        if self.position.is_open:
            self.entry_bars_count += 1
    
    def should_long(self) -> bool:
        # Must have long bias and DOL calculated
        if self.bias != 'long' or self.dol is None:
            return False
            
        # No existing position (unless flip_exit enabled)
        if self.position.is_open and not self.flip_exit_enabled:
            return False
            
        # Entry trigger: current bar closes above DOL after being below it
        # (open < DOL and close > DOL)
        if self.open < self.dol and self.close > self.dol:
            # Optional momentum confirmation
            if self.require_momentum_confirmation:
                # Check if current candle has sufficient body ratio
                body_size = abs(self.close - self.open)
                total_range = self.high - self.low
                if total_range > 0:
                    body_ratio = body_size / total_range
                    if body_ratio < self.min_candle_body_ratio:
                        return False
            return True
            
        return False
    
    def should_short(self) -> bool:
        # Must have short bias and DOL calculated
        if self.bias != 'short' or self.dol is None:
            return False
            
        # No existing position (unless flip_exit enabled) 
        if self.position.is_open and not self.flip_exit_enabled:
            return False
            
        # Entry trigger: current bar closes below DOL after being above it
        # (open > DOL and close < DOL)
        if self.open > self.dol and self.close < self.dol:
            # Optional momentum confirmation
            if self.require_momentum_confirmation:
                # Check if current candle has sufficient body ratio
                body_size = abs(self.close - self.open)
                total_range = self.high - self.low
                if total_range > 0:
                    body_ratio = body_size / total_range
                    if body_ratio < self.min_candle_body_ratio:
                        return False
            return True
            
        return False
    
    def should_cancel_entry(self) -> bool:
        """Cancel pending orders if DOL/bias becomes invalid."""
        # Cancel entry if DOL or bias changes significantly or becomes None
        if self.dol is None or self.bias is None:
            return True
        return False
    
    def go_long(self):
        # Close existing short position if flip exit enabled
        if self.position.is_open and self.is_short and self.flip_exit_enabled:
            self.liquidate()
            
        entry_price = self.close
        stop_loss_price = self._calculate_stop_loss(entry_price)
        
        if stop_loss_price is None:
            return
            
        qty = self._calculate_position_size(entry_price, stop_loss_price)
        
        # Validate quantity before placing order
        if qty <= 0:
            return
            
        self.buy = qty, entry_price
        self.entry_bars_count = 0
        
    def go_short(self):
        # Close existing long position if flip exit enabled
        if self.position.is_open and self.is_long and self.flip_exit_enabled:
            self.liquidate()
            
        entry_price = self.close
        stop_loss_price = self._calculate_stop_loss(entry_price)
        
        if stop_loss_price is None:
            return
            
        qty = self._calculate_position_size(entry_price, stop_loss_price)
        
        # Validate quantity before placing order
        if qty <= 0:
            return
            
        self.sell = qty, entry_price
        self.entry_bars_count = 0
    
    def on_open_position(self, order) -> None:
        """Set initial stop-loss and take-profit levels."""
        entry_price = self.position.entry_price
        stop_loss_price = self._calculate_stop_loss(entry_price)
        
        if stop_loss_price is None:
            return
            
        # Set stop-loss
        self.stop_loss = self.position.qty, stop_loss_price
        
        # Calculate R (risk per unit)
        r = abs(entry_price - stop_loss_price)
        
        # Set take-profit levels
        if self.is_long:
            tp1_price = entry_price + (r * self.tp1_multiplier)
            tp2_price = entry_price + (r * self.tp2_multiplier)
        else:  # short
            tp1_price = entry_price - (r * self.tp1_multiplier) 
            tp2_price = entry_price - (r * self.tp2_multiplier)
            
        # Set TP1 for partial close (configurable percentage)
        tp1_qty = self.position.qty * self.tp1_close_percentage
        self.take_profit = tp1_qty, tp1_price
        
        # Store TP1 and TP2 for later use
        self.vars['tp1_price'] = tp1_price
        self.vars['tp2_price'] = tp2_price
        self.vars['tp2_qty'] = self.position.qty - tp1_qty
        self.vars['tp1_hit'] = False
        
    def update_position(self):
        """Handle trade management: TP1/TP2, breakeven SL, time stop."""
        if not self.position.is_open:
            return
            
        current_price = self.close
        entry_price = self.position.entry_price
        
        # Check if TP1 was hit and move SL to breakeven
        if not self.vars.get('tp1_hit', False):
            tp1_price = self.vars.get('tp1_price')
            if tp1_price is not None and ((self.is_long and current_price >= tp1_price) or 
                (self.is_short and current_price <= tp1_price)):
                # Move SL to breakeven
                self.stop_loss = self.position.qty, entry_price
                self.vars['tp1_hit'] = True
        
        # Check TP2 level for remaining position
        tp2_price = self.vars.get('tp2_price')
        tp2_qty = self.vars.get('tp2_qty', 0)
        
        if tp2_price and tp2_qty > 0:
            if ((self.is_long and current_price >= tp2_price) or
                (self.is_short and current_price <= tp2_price)):
                # Close remaining position at TP2
                if self.is_long:
                    self.sell = tp2_qty, tp2_price
                else:
                    self.buy = tp2_qty, tp2_price
                self.vars['tp2_qty'] = 0
        
        # Time stop: exit after max_hold_bars if neither TP2 nor SL hit
        if self.time_stop_enabled and self.entry_bars_count >= self.max_hold_bars:
            self.liquidate()
    
    # Configuration properties
    @property
    def buffer_ticks(self):
        return self.hp.get('buffer_ticks', 2)
    
    @property
    def tick_size(self):
        return self.hp.get('tick_size', 0.01)
        
    @property
    def tp1_multiplier(self):
        return self.hp.get('tp1_multiplier', 1.5)
        
    @property  
    def tp2_multiplier(self):
        return self.hp.get('tp2_multiplier', 3.0)
        
    @property
    def risk_percent(self):
        return self.hp.get('risk_percent', 1.0)
        
    @property
    def use_full_balance(self):
        return self.hp.get('use_full_balance', 0) == 1
        
    @property
    def leverage_multiplier(self):
        return self.hp.get('leverage_multiplier', 1.0)
        
    @property
    def flip_exit_enabled(self):
        return self.hp.get('flip_exit_enabled', 1) == 1
        
    @property
    def time_stop_enabled(self):
        return self.hp.get('time_stop_enabled', 1) == 1
        
    @property
    def max_hold_bars(self):
        return self.hp.get('max_hold_bars', 20)
        
    @property
    def tp1_close_percentage(self):
        return self.hp.get('tp1_close_percentage', 0.5)
        
    @property
    def require_momentum_confirmation(self):
        return self.hp.get('require_momentum_confirmation', 0) == 1
        
    @property
    def min_candle_body_ratio(self):
        return self.hp.get('min_candle_body_ratio', 0.3)
        
    @property
    def use_atr_stops(self):
        return self.hp.get('use_atr_stops', 0) == 1
        
    @property
    def atr_stop_multiplier(self):
        return self.hp.get('atr_stop_multiplier', 2.0)
        
    @property
    def atr_period(self):
        return self.hp.get('atr_period', 14)

    def hyperparameters(self) -> list:
        """Comprehensive parameters for genetic optimization."""
        return [
            # DOL Calculation Parameters
            {
                'name': 'buffer_ticks',
                'type': int,
                'min': 0,
                'max': 10,
                'default': 2,
            },
            {
                'name': 'tick_size',
                'type': float,
                'min': 0.001,
                'max': 0.1,
                'step': 0.001,
                'default': 0.01,
            },
            
            # Take Profit Parameters
            {
                'name': 'tp1_multiplier', 
                'type': float,
                'min': 0.5,
                'max': 4.0,
                'step': 0.1,
                'default': 1.5,
            },
            {
                'name': 'tp2_multiplier',
                'type': float, 
                'min': 1.0,
                'max': 8.0,
                'step': 0.2,
                'default': 3.0,
            },
            
            # Risk Management
            {
                'name': 'risk_percent',
                'type': float,
                'min': 0.1,
                'max': 3.0,
                'step': 0.1,
                'default': 1.0,
            },
            
            # Trade Management
            {
                'name': 'flip_exit_enabled',
                'type': int,
                'min': 0,
                'max': 1,
                'default': 1,
            },
            {
                'name': 'time_stop_enabled',
                'type': int,
                'min': 0,
                'max': 1,
                'default': 1,
            },
            {
                'name': 'max_hold_bars',
                'type': int,
                'min': 5,
                'max': 100,
                'default': 20,
            },
            
            # Position Sizing Options
            {
                'name': 'use_full_balance',
                'type': int,
                'min': 0,
                'max': 1,
                'default': 0,
            },
            {
                'name': 'leverage_multiplier',
                'type': float,
                'min': 1.0,
                'max': 5.0,
                'step': 0.5,
                'default': 1.0,
            },
            
            # TP1 Partial Close Options
            {
                'name': 'tp1_close_percentage',
                'type': float,
                'min': 0.2,
                'max': 0.8,
                'step': 0.1,
                'default': 0.5,
            },
            
            # Alternative Entry Modes
            {
                'name': 'require_momentum_confirmation',
                'type': int,
                'min': 0,
                'max': 1,
                'default': 0,
            },
            {
                'name': 'min_candle_body_ratio',
                'type': float,
                'min': 0.1,
                'max': 0.9,
                'step': 0.1,
                'default': 0.3,
            },
            
            # Stop Loss Variations
            {
                'name': 'use_atr_stops',
                'type': int,
                'min': 0,
                'max': 1,
                'default': 0,
            },
            {
                'name': 'atr_stop_multiplier',
                'type': float,
                'min': 1.0,
                'max': 4.0,
                'step': 0.2,
                'default': 2.0,
            },
            {
                'name': 'atr_period',
                'type': int,
                'min': 5,
                'max': 30,
                'default': 14,
            },
        ]
    
