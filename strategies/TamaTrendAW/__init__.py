from jesse.strategies import Strategy
import jesse.indicators as ta
from jesse import utils



class TamaTrendAW(Strategy):
    # Position state tracking
    def __init__(self):
        super().__init__()
        # Market sentiment - manually set based on overall market analysis
        self.isBullish = True
        self.has_hedge = False
        self.hedge_contracts = 0
        self.hedge_entry_price = 0
    
    @property
    def short_term_trend(self):
        # Get short-term trend using TEMA crossover
        tema10 = ta.tema(self.candles, self.hp['tema_short'])
        tema80 = ta.tema(self.candles, self.hp['tema_long'])

        if tema10 > tema80:
            return 1  # Uptrend
        else:
            return -1  # Downtrend

    @property
    def long_term_trend(self):
        # Get long-term trend using TEMA crossover on 4h timeframe
        candles_4h = self.get_candles(self.exchange, self.symbol, '4h')
        tema20 = ta.tema(candles_4h, self.hp['tema_4h_short'])
        tema70 = ta.tema(candles_4h, self.hp['tema_4h_long'])

        if tema20 > tema70:
            return 1  # Uptrend
        else:
            return -1  # Downtrend

    @property
    def tema10(self):
        return ta.tema(self.candles, self.hp['tema_short'])

    @property
    def tema80(self):
        return ta.tema(self.candles, self.hp['tema_long'])

    @property
    def tema20_4h(self):
        candles_4h = self.get_candles(self.exchange, self.symbol, '4h')
        return ta.tema(candles_4h, self.hp['tema_4h_short'])

    @property
    def tema70_4h(self):
        candles_4h = self.get_candles(self.exchange, self.symbol, '4h')
        return ta.tema(candles_4h, self.hp['tema_4h_long'])

    @property
    def atr(self):
        return ta.atr(self.candles)

    @property
    def adx(self):
        return ta.adx(self.candles)

    @property
    def cmo(self):
        return ta.cmo(self.candles)

    def should_long(self) -> bool:
        # Check available margin first
        if self.available_margin <= 0:
            return False
            
        # Only enter longs when bullish
        if not self.isBullish:
            return False
            
        # Don't enter new longs if we have a hedge active
        if self.has_hedge:
            return False
            
        # Check if we can still add to position (max % of balance)
        if self.is_open:
            current_position_value = self.position.qty * self.price  # Use current price
            max_position_value = self.balance * (self.hp['max_position_percent'] / 100)
            
            if current_position_value >= max_position_value:
                return False  # Already at max position size
            
        # Check if all bullish conditions are met
        conditions_met = (
            self.short_term_trend == 1 and
            self.long_term_trend == 1 and
            self.adx > self.hp['adx_threshold'] and
            self.cmo > self.hp['cmo_upper']
        )
            
        return conditions_met

    def should_short(self) -> bool:
        # Shorts only happen as hedges, never as primary trades
        return False

    def go_long(self):
        # Use market order at current price
        entry_price = self.price
        
        # Check if we have sufficient margin
        if self.available_margin <= 0:
            self.log(f"Cannot enter long: Insufficient margin (${self.available_margin})")
            return
        
        # Log entry
        position_type = "DCA" if self.is_open else "INITIAL"
        self.log(f"=== ENTERING LONG POSITION ({position_type}) ===")
        self.log(f"Price: {self.price}, Balance: {self.balance}, Available Margin: {self.available_margin}")
        
        if self.is_open:
            # DCA: Add to existing position up to max % 
            current_position_value = self.position.qty * entry_price  # Use current price, not entry price
            max_position_value = self.balance * (self.hp['max_position_percent'] / 100)
            remaining_capacity = max_position_value - current_position_value
            
            # Calculate DCA increment as % of available margin
            dca_margin_size = self.available_margin * (self.hp['dca_increment_percent'] / 100)
            
            # Don't exceed remaining capacity
            if remaining_capacity > 0:
                dca_position_value = min(dca_margin_size * self.leverage, remaining_capacity)
                dca_margin_required = dca_position_value / self.leverage
                
                # Ensure we don't exceed available margin
                dca_margin_required = min(dca_margin_required, self.available_margin * 0.95)  # 5% buffer
                
                qty = utils.size_to_qty(dca_margin_required, entry_price, fee_rate=self.fee_rate)
                
                self.log(f"DCA: Adding {qty} contracts (${dca_margin_required:.2f} margin)")
            else:
                self.log(f"Cannot DCA: Max position reached")
                return
            
        else:
            # Initial position: Use % of available margin
            initial_margin_size = self.available_margin * (self.hp['initial_position_percent'] / 100)
            
            # Add safety buffer to avoid margin issues
            initial_margin_size = min(initial_margin_size, self.available_margin * 0.95)  # 5% buffer
            
            qty = utils.size_to_qty(initial_margin_size, entry_price, fee_rate=self.fee_rate)
            
            self.log(f"Initial: {qty} contracts (${initial_margin_size:.2f} margin)")
        
        # Final safety check
        required_margin = (qty * entry_price) / self.leverage
        if required_margin > self.available_margin:
            self.log(f"Order too large: Required ${required_margin:.2f} > Available ${self.available_margin:.2f}")
            return
        
        self.log(f"=== END LONG ENTRY ===")
        
        # Place the order
        self.buy = qty, entry_price

    def go_short(self):
        # This should never be called since should_short() always returns False
        # Hedge shorts are handled in update_position()
        pass

    def should_cancel_entry(self) -> bool:
        return False

    def on_open_position(self, order) -> None:
        if self.is_long:
            # Only set take profit for long positions (no stop loss)
            self.take_profit = self.position.qty, self.position.entry_price + (self.atr * self.hp['atr_take_profit'])
        # Hedge positions are managed manually in update_position()

    def update_position(self) -> None:
        if not self.is_open:
            # If main position is closed but we still have a hedge, close it
            if self.has_hedge:
                self._close_hedge("Main position closed")
            return
            
        # Main hedge management logic
        if self.is_long and not self.has_hedge:
            self._check_hedge_trigger()
        elif self.has_hedge:
            self._manage_hedge()
    
    def _check_hedge_trigger(self) -> None:
        """Check if we need to open a hedge position"""
        # Calculate if long is underwater (accounting for leverage)
        price_drop_percent = (self.position.entry_price - self.price) / self.position.entry_price
        leveraged_loss_percent = price_drop_percent * self.leverage  # Use actual leverage
        
        if leveraged_loss_percent >= (self.hp['hedge_trigger_percent'] / 100):  # Configurable loss threshold
            # Wait for bearish signal confirmation
            bearish_signal = (
                self.short_term_trend == -1 and
                self.long_term_trend == -1 and
                self.adx > self.hp['adx_threshold'] and
                self.cmo < self.hp['cmo_lower']
            )
            
            if bearish_signal:
                self.log(f"=== OPENING HEDGE ===")
                self.log(f"Loss threshold reached: {leveraged_loss_percent * 100:.2f}% >= {self.hp['hedge_trigger_percent']}%")
                self.log(f"Bearish signals confirmed - ST:{self.short_term_trend}, LT:{self.long_term_trend}, ADX:{self.adx}, CMO:{self.cmo}")
                self._open_hedge()
    
    def _open_hedge(self) -> None:
        """Open hedge position"""
        if self.available_margin <= 0:
            self.log(f"Cannot open hedge: Insufficient margin (${self.available_margin})")
            return
            
        # Calculate hedge quantity as % of long position
        target_hedge_qty = self.position.qty * (self.hp['hedge_size_percent'] / 100)
        
        # Calculate required margin for hedge
        required_margin = (target_hedge_qty * self.price) / self.leverage
        
        # Ensure we don't exceed available margin (with buffer)
        max_affordable_margin = self.available_margin * 0.95  # 5% buffer
        
        if required_margin > max_affordable_margin:
            # Reduce hedge size to fit available margin
            affordable_qty = (max_affordable_margin * self.leverage) / self.price
            hedge_qty = min(target_hedge_qty, affordable_qty)
            self.log(f"Reducing hedge size due to margin constraints: {target_hedge_qty:.4f} -> {hedge_qty:.4f}")
        else:
            hedge_qty = target_hedge_qty
        
        if hedge_qty <= 0:
            self.log(f"Cannot open hedge: Calculated quantity too small")
            return
        
        self.log(f"=== OPENING HEDGE ===")
        self.log(f"Long Position Qty: {self.position.qty}")
        self.log(f"Hedge Size %: {self.hp['hedge_size_percent']}%")
        self.log(f"Hedge Qty: {hedge_qty}")
        self.log(f"Required Margin: ${required_margin:.2f}")
        self.log(f"Available Margin: ${self.available_margin:.2f}")
        
        # Open hedge immediately at market price
        self.sell = hedge_qty, self.price
        
        # Update tracking
        self.has_hedge = True
        self.hedge_contracts = hedge_qty
        self.hedge_entry_price = self.price
        
        self.log(f"Hedge position opened successfully!")
        self.log(f"=== END OPENING HEDGE ===")
    
    def _manage_hedge(self) -> None:
        """Manage existing hedge position"""
        # Check if hedge is profitable
        hedge_profit = (self.hedge_entry_price - self.price) * self.hedge_contracts
        
        # Calculate overall position PnL (long + hedge)
        long_pnl = (self.price - self.position.entry_price) * self.position.qty
        total_pnl = long_pnl + hedge_profit
        
        # Condition 1: Close if hedge is profitable AND bullish signals appear
        if hedge_profit > 0:
            bullish_signal = (
                self.short_term_trend == 1 and
                self.long_term_trend == 1 and
                self.adx > self.hp['adx_threshold'] and
                self.cmo > self.hp['cmo_upper']
            )
            
            if bullish_signal:
                self.log(f"=== CLOSING HEDGE ===")
                self.log(f"Hedge profitable ({hedge_profit:.2f}) + Bullish signals confirmed")
                self.log(f"Total PnL: {total_pnl:.2f} (Long: {long_pnl:.2f} + Hedge: {hedge_profit:.2f})")
                self._close_hedge_and_rebalance(hedge_profit)
                return
        
        # Condition 2: Close losing hedge ONLY when long profit can cover hedge loss + buffer
        if hedge_profit < 0:
            # Add 10% buffer to ensure long profit comfortably covers hedge loss
            required_long_profit = abs(hedge_profit) * 1.1
            
            if long_pnl > required_long_profit:
                self.log(f"=== CLOSING HEDGE ===")
                self.log(f"Long profit ({long_pnl:.2f}) covers hedge loss ({hedge_profit:.2f}) + buffer")
                self.log(f"Total PnL: {total_pnl:.2f}")
                self._close_hedge_and_rebalance(hedge_profit)
                return
    
    def _close_hedge(self, reason: str) -> None:
        """Simple hedge closure without rebalancing"""
        if not self.has_hedge:
            return
            
        self.log(f"=== CLOSING HEDGE ===")
        self.log(f"Reason: {reason}")
        self.log(f"Closing {self.hedge_contracts} hedge contracts")
        
        # Close the hedge position
        self.buy = self.hedge_contracts, self.price  # Close short hedge with buy
        
        # Reset hedge tracking
        self.has_hedge = False
        self.hedge_contracts = 0
        self.hedge_entry_price = 0
        
        self.log(f"Hedge closed successfully!")
        self.log(f"=== END CLOSING HEDGE ===")
    
    def _close_hedge_and_rebalance(self, hedge_profit: float) -> None:
        """Close hedge and rebalance long position using hedge profits"""
        self.log(f"=== CLOSING HEDGE AND REBALANCING ===")
        self.log(f"Hedge Profit: {hedge_profit}")
        self.log(f"Hedge Contracts: {self.hedge_contracts}")
        
        # Close the hedge position first
        self.buy = self.hedge_contracts, self.price  # Close short hedge with buy
        
        # Reset hedge tracking
        self.has_hedge = False
        self.hedge_contracts = 0
        self.hedge_entry_price = 0
        
        # Only rebalance if hedge was profitable
        if hedge_profit > 0:
            # Calculate rebalance amounts
            rebalance_amount = hedge_profit * (self.hp['rebalance_percent'] / 100)
            realized_profit = hedge_profit * (self.hp['profit_realization_percent'] / 100)
            
            self.log(f"Rebalance Amount: {rebalance_amount:.2f}")
            self.log(f"Realized Profit: {realized_profit:.2f}")
            
            # Only rebalance if position is underwater and we have margin
            if self.available_margin > 0 and self.price < self.position.entry_price:
                price_diff = self.position.entry_price - self.price
                
                # Calculate how many contracts we can rebalance with the profit
                max_contracts_by_profit = rebalance_amount / price_diff if price_diff > 0 else 0
                max_contracts_by_position = self.position.qty * 0.3  # Max 30% of position
                
                contracts_to_rebalance = min(
                    max_contracts_by_profit,
                    max_contracts_by_position
                )
                
                contracts_to_rebalance = max(0, int(contracts_to_rebalance))  # Ensure positive integer
                
                self.log(f"Price diff: {price_diff:.2f}, Max by profit: {max_contracts_by_profit:.4f}")
                self.log(f"Contracts to rebalance: {contracts_to_rebalance}")
                
                if contracts_to_rebalance > 0:
                    # Check margin requirement
                    margin_needed = (contracts_to_rebalance * self.price) / self.leverage
                    
                    if margin_needed <= self.available_margin * 0.8:  # 20% buffer
                        # Sell underwater contracts at current price
                        self.sell = contracts_to_rebalance, self.price
                        
                        # Immediately rebuy the same amount at current price
                        # This effectively moves those contracts from higher entry to current lower price
                        self.buy = contracts_to_rebalance, self.price
                        
                        improvement = contracts_to_rebalance * price_diff
                        self.log(f"Rebalanced {contracts_to_rebalance} contracts, improved position by ${improvement:.2f}")
                    else:
                        self.log(f"Insufficient margin for rebalancing: Need ${margin_needed:.2f}, Available ${self.available_margin:.2f}")
                else:
                    self.log(f"No contracts to rebalance (calculated: {max_contracts_by_profit:.4f})")
            else:
                self.log(f"No rebalancing needed - Available margin: ${self.available_margin:.2f}, Underwater: {self.price < self.position.entry_price}")
        else:
            self.log(f"No rebalancing - hedge was not profitable (${hedge_profit:.2f})")
        
        self.log(f"=== END CLOSING HEDGE AND REBALANCING ===")

    def hyperparameters(self) -> list:
        return [
            # Original indicator parameters
            {'name': 'tema_short', 'type': int, 'min': 3, 'max': 50, 'step': 1, 'default': 15}, 
            {'name': 'tema_long', 'type': int, 'min': 30, 'max': 200, 'step': 2, 'default': 98},
            {'name': 'tema_4h_short', 'type': int, 'min': 5, 'max': 60, 'step': 1, 'default': 50},
            {'name': 'tema_4h_long', 'type': int, 'min': 40, 'max': 150, 'step': 2, 'default': 52},
            {'name': 'adx_threshold', 'type': int, 'min': 15, 'max': 80, 'step': 1, 'default': 40},
            {'name': 'cmo_upper', 'type': int, 'min': 10, 'max': 80, 'step': 1, 'default': 18},
            {'name': 'cmo_lower', 'type': int, 'min': -80, 'max': -10, 'step': 1, 'default': -21},
            {'name': 'atr_take_profit', 'type': float, 'min': 1.0, 'max': 10.0, 'step': 0.1, 'default': 3.2},
            
            # Position sizing parameters
            {'name': 'initial_position_percent', 'type': float, 'min': 5.0, 'max': 30.0, 'step': 5.0, 'default': 20.0},
            {'name': 'max_position_percent', 'type': float, 'min': 20.0, 'max': 50.0, 'step': 2.5, 'default': 30.0},
            {'name': 'dca_increment_percent', 'type': float, 'min': 2.5, 'max': 15.0, 'step': 1.25, 'default': 5.0},
            
            # Hedge trigger parameters
            {'name': 'hedge_trigger_percent', 'type': float, 'min': 20.0, 'max': 50.0, 'step': 2.5, 'default': 30.0},
            {'name': 'hedge_size_percent', 'type': float, 'min': 25.0, 'max': 100.0, 'step': 10.0, 'default': 50.0},
            
            # Profit realization parameters
            {'name': 'profit_realization_percent', 'type': float, 'min': 10.0, 'max': 40.0, 'step': 2.5, 'default': 30.0},
            {'name': 'rebalance_percent', 'type': float, 'min': 60.0, 'max': 90.0, 'step': 2.5, 'default': 80.0},
        ]

    def after(self) -> None:
        # Add main indicators to the chart for debugging
        self.add_line_to_candle_chart('TEMA15', self.tema10)
        self.add_line_to_candle_chart('TEMA98', self.tema80)
        self.add_line_to_candle_chart('TEMA50_4h', self.tema20_4h)
        self.add_line_to_candle_chart('TEMA52_4h', self.tema70_4h)

        # Add extra charts for monitoring individual indicators
        self.add_extra_line_chart('ADX', 'ADX', self.adx)
        self.add_horizontal_line_to_extra_chart('ADX', 'ADX Threshold', self.hp['adx_threshold'], 'red')

        self.add_extra_line_chart('CMO', 'CMO', self.cmo)
        self.add_horizontal_line_to_extra_chart('CMO', 'CMO Upper Threshold', self.hp['cmo_upper'], 'green')
        self.add_horizontal_line_to_extra_chart('CMO', 'CMO Lower Threshold', self.hp['cmo_lower'], 'red')
        
        # Add position status chart
        self.add_extra_line_chart('Position Status', 'Has Hedge', 1 if self.has_hedge else 0)
        self.add_extra_line_chart('Position Status', 'Market Sentiment', 1 if self.isBullish else -1)

    def watch_list(self) -> list:
        return [
            ('Market Sentiment', 'Bullish' if self.isBullish else 'Bearish'),
            ('Short Term Trend', self.short_term_trend),
            ('Long Term Trend', self.long_term_trend),
            ('ADX', self.adx),
            ('CMO', self.cmo),
            ('Has Hedge', self.has_hedge),
            ('Long Contracts', self.position.qty if self.is_open else 0),
            ('Hedge Contracts', self.hedge_contracts if self.has_hedge else 0),
        ]

    # def dna(self):
    #     return 'eyJhZHhfdGhyZXNob2xkIjogNDEsICJhdHJfZW50cnkiOiAwLjksICJhdHJfc3RvcCI6IDIuNSwgImF0cl90YWtlX3Byb2ZpdCI6IDIuOTAwMDAwMDAwMDAwMDAwNCwgImNtb19sb3dlciI6IC00NSwgImNtb191cHBlciI6IDIxLCAicXR5X211bHRpcGxpZXIiOiA1LjAsICJyaXNrX3BlcmNlbnQiOiAxLjMsICJ0ZW1hXzRoX2xvbmciOiA2NSwgInRlbWFfNGhfc2hvcnQiOiAyMSwgInRlbWFfbG9uZyI6IDEwMCwgInRlbWFfc2hvcnQiOiAyOH0='

	# Rank 3, Trial 2041, ETH-USDT, Fitness Ratio 0.51
    # return 'eyJhZHhfdGhyZXNob2xkIjogNDUsICJhdHJfZW50cnkiOiAxLjA1LCAiYXRyX3N0b3AiOiA0LjQsICJhdHJfdGFrZV9wcm9maXQiOiA1LjMsICJjbW9fbG93ZXIiOiAtNDgsICJjbW9fdXBwZXIiOiA3NCwgInF0eV9tdWx0aXBsaWVyIjogNi4yNSwgInJpc2tfcGVyY2VudCI6IDMuNiwgInRlbWFfNGhfbG9uZyI6IDgyLCAidGVtYV80aF9zaG9ydCI6IDksICJ0ZW1hX2xvbmciOiAxNDgsICJ0ZW1hX3Nob3J0IjogMjB9'

    # Rank 6, Trial Trial 1588, Fitness Ratio 0.33
    #       return 'eyJhZHhfdGhyZXNob2xkIjogMjQsICJhdHJfZW50cnkiOiAwLjY1LCAiYXRyX3N0b3AiOiAzLjQwMDAwMDAwMDAwMDAwMDQsICJhdHJfdGFrZV9wcm9maXQiOiA4LjgsICJjbW9fbG93ZXIiOiAtNTUsICJjbW9fdXBwZXIiOiAxNCwgInF0eV9tdWx0aXBsaWVyIjogNC43NSwgInJpc2tfcGVyY2VudCI6IDEuOTAwMDAwMDAwMDAwMDAwMSwgInRlbWFfNGhfbG9uZyI6IDY2LCAidGVtYV80aF9zaG9ydCI6IDE2LCAidGVtYV9sb25nIjogOTIsICJ0ZW1hX3Nob3J0IjogMTN9'
