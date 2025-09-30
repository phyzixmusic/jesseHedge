from jesse.strategies import Strategy
import jesse.indicators as ta
from jesse import utils

class TemaTrendFollowing(Strategy):
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
        # Check if all conditions for long trade are met
        return (
            self.short_term_trend == 1 and
            self.long_term_trend == 1 and
            self.adx > self.hp['adx_threshold'] and
            self.cmo > self.hp['cmo_upper']
        )

    def should_short(self) -> bool:
        # Check if all conditions for short trade are met (opposite of long)
        return (
            self.short_term_trend == -1 and
            self.long_term_trend == -1 and
            self.adx > self.hp['adx_threshold'] and
            self.cmo < self.hp['cmo_lower']
        )

    def go_long(self):
        # Calculate entry, stop and position size
        entry_price = self.price - (self.atr * self.hp['atr_entry'])  # Limit order below current price
        stop_loss_price = entry_price - (self.atr * self.hp['atr_stop'])  # Stop loss below entry

        # Risk percentage of available margin
        qty = utils.risk_to_qty(self.available_margin, self.hp['risk_percent'], entry_price, stop_loss_price, fee_rate=self.fee_rate)

        # Place the order
        self.buy = qty * self.hp['qty_multiplier'], entry_price

    def go_short(self):
        # Calculate entry, stop and position size
        entry_price = self.price + (self.atr * self.hp['atr_entry'])  # Limit order above current price
        stop_loss_price = entry_price + (self.atr * self.hp['atr_stop'])  # Stop loss above entry

        # Risk percentage of available margin
        qty = utils.risk_to_qty(self.available_margin, self.hp['risk_percent'], entry_price, stop_loss_price, fee_rate=self.fee_rate)

        # Place the order
        self.sell = qty * self.hp['qty_multiplier'], entry_price

    def should_cancel_entry(self) -> bool:
        return True

    def on_open_position(self, order) -> None:
        if self.is_long:
            # Set stop loss and take profit for long position
            self.stop_loss = self.position.qty, self.position.entry_price - (self.atr * self.hp['atr_stop'])
            self.take_profit = self.position.qty, self.position.entry_price + (self.atr * self.hp['atr_take_profit'])
        elif self.is_short:
            # Set stop loss and take profit for short position
            self.stop_loss = self.position.qty, self.position.entry_price + (self.atr * self.hp['atr_stop'])
            self.take_profit = self.position.qty, self.position.entry_price - (self.atr * self.hp['atr_take_profit'])

    def hyperparameters(self) -> list:
        return [
            {'name': 'tema_short', 'type': int, 'min': 3, 'max': 50, 'step': 1, 'default': 10},
            {'name': 'tema_long', 'type': int, 'min': 30, 'max': 200, 'step': 2, 'default': 80},
            {'name': 'tema_4h_short', 'type': int, 'min': 5, 'max': 60, 'step': 1, 'default': 20},
            {'name': 'tema_4h_long', 'type': int, 'min': 40, 'max': 150, 'step': 2, 'default': 70},
            {'name': 'adx_threshold', 'type': int, 'min': 15, 'max': 80, 'step': 1, 'default': 40},
            {'name': 'cmo_upper', 'type': int, 'min': 10, 'max': 80, 'step': 1, 'default': 40},
            {'name': 'cmo_lower', 'type': int, 'min': -80, 'max': -10, 'step': 1, 'default': -40},
            {'name': 'atr_entry', 'type': float, 'min': 0.1, 'max': 3.0, 'step': 0.05, 'default': 1.0},
            {'name': 'atr_stop', 'type': float, 'min': 1.0, 'max': 8.0, 'step': 0.1, 'default': 4.0},
            {'name': 'atr_take_profit', 'type': float, 'min': 1.0, 'max': 10.0, 'step': 0.1, 'default': 3.0},
            {'name': 'risk_percent', 'type': float, 'min': 0.5, 'max': 10.0, 'step': 0.1, 'default': 3.0},
            {'name': 'qty_multiplier', 'type': float, 'min': 0.5, 'max': 10.0, 'step': 0.25, 'default': 1.0},
        ]

    def after(self) -> None:
        # Add main indicators to the chart for debugging
        self.add_line_to_candle_chart('TEMA10', self.tema10)
        self.add_line_to_candle_chart('TEMA80', self.tema80)

        # Add extra charts for monitoring individual indicators
        self.add_extra_line_chart('ADX', 'ADX', self.adx)
        self.add_horizontal_line_to_extra_chart('ADX', 'ADX Threshold', 40, 'red')

        self.add_extra_line_chart('CMO', 'CMO', self.cmo)
        self.add_horizontal_line_to_extra_chart('CMO', 'CMO Upper Threshold', 40, 'green')
        self.add_horizontal_line_to_extra_chart('CMO', 'CMO Lower Threshold', -40, 'red')

    def dna(self):
    #     return 'eyJhZHhfdGhyZXNob2xkIjogNDEsICJhdHJfZW50cnkiOiAwLjksICJhdHJfc3RvcCI6IDIuNSwgImF0cl90YWtlX3Byb2ZpdCI6IDIuOTAwMDAwMDAwMDAwMDAwNCwgImNtb19sb3dlciI6IC00NSwgImNtb191cHBlciI6IDIxLCAicXR5X211bHRpcGxpZXIiOiA1LjAsICJyaXNrX3BlcmNlbnQiOiAxLjMsICJ0ZW1hXzRoX2xvbmciOiA2NSwgInRlbWFfNGhfc2hvcnQiOiAyMSwgInRlbWFfbG9uZyI6IDEwMCwgInRlbWFfc2hvcnQiOiAyOH0='

    # Rank 6, Trial Trial 1588, Fitness Ratio 0.33
          return 'eyJhZHhfdGhyZXNob2xkIjogMjQsICJhdHJfZW50cnkiOiAwLjY1LCAiYXRyX3N0b3AiOiAzLjQwMDAwMDAwMDAwMDAwMDQsICJhdHJfdGFrZV9wcm9maXQiOiA4LjgsICJjbW9fbG93ZXIiOiAtNTUsICJjbW9fdXBwZXIiOiAxNCwgInF0eV9tdWx0aXBsaWVyIjogNC43NSwgInJpc2tfcGVyY2VudCI6IDEuOTAwMDAwMDAwMDAwMDAwMSwgInRlbWFfNGhfbG9uZyI6IDY2LCAidGVtYV80aF9zaG9ydCI6IDE2LCAidGVtYV9sb25nIjogOTIsICJ0ZW1hX3Nob3J0IjogMTN9'