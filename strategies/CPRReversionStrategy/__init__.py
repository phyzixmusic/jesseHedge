import numpy as np
import jesse.indicators as ta
from jesse.strategies import Strategy
from jesse.enums import sides
from jesse import utils
from datetime import datetime, timezone

# -----------------------------------------------------------------------------
# Helper functions (pure python – no Jesse state)
# -----------------------------------------------------------------------------

def compute_cpr(high: float, low: float, close: float):
    """Return (pivot, bc_val, tc_val) for the given daily OHLC, ensuring tc_val > bc_val."""
    pivot = (high + low + close) / 3
    bc = (high + low) / 2
    tc = 2 * pivot - bc
    
    # Ensure bc_val is the lower boundary and tc_val is the upper boundary
    bc_val = min(pivot, bc, tc)
    tc_val = max(pivot, bc, tc)
    
    return pivot, bc_val, tc_val


def delta_from_closest_cpr_bound(open_price: float, bc_val: float, tc_val: float):
    """Calculate delta from the closest CPR boundary (BC_val or TC_val)."""
    # Closest bound is tc_val if price is above CPR, or bc_val if price is below CPR
    if open_price > tc_val:
        closest_bound = tc_val
    elif open_price < bc_val:
        closest_bound = bc_val
    else: # Should not happen if this is called after price is outside CPR range
        return 0 
        
    return abs(open_price - closest_bound) / open_price


def is_cpr_descending(curr_pivot: float, prev_pivot: float):
    """Determine if CPR is descending (True) or ascending (False)."""
    return curr_pivot < prev_pivot


# -----------------------------------------------------------------------------
# Main strategy
# -----------------------------------------------------------------------------
class CPRReversionStrategy(Strategy):
    # Class variables for cross-ticker coordination
    _daily_ticker_analysis = {}  # Shared analysis across all ticker instances
    _selected_tickers = []       # Top 3 selected tickers for the day
    _analysis_date = None        # Date of current analysis
    _analysis_complete = False   # Flag to indicate analysis is done
    _pending_entries = {}        # Dict: {ticker: 'LONG'/'SHORT'} for selected tickers to enter
    _last_reset_logged = None    # Track last day reset was logged to prevent spam
    def __init__(self):
        super().__init__()
        self.prev_cpr = None  # (pivot, bc_val, tc_val) for day before yesterday
        self.curr_cpr = None  # (pivot, bc_val, tc_val) for yesterday's candle (used for today)
        self.curr_cpr_date = None # Timestamp of the date for which curr_cpr was calculated
        self.position_opened_at = None # Track when position was opened for max time exit
        self.should_enter_long = False  # Flag for long entry
        self.should_enter_short = False  # Flag for short entry
        self.entry_data = None  # Store entry data for go_long/go_short methods
        
        # Pre-calculated CPR for next day (calculated at 23:59)
        self.next_day_cpr = None  # CPR values for tomorrow
        self.next_day_cpr_date = None  # Date for which next_day_cpr was calculated
        
        # Multi-ticker selection
        self.is_selected_for_entry = False  # Flag if this ticker is selected in top 3
        self.all_ticker_analysis = {}  # Store analysis for all tickers (shared across instances)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def _construct_current_day_candle(self):
        """Manually build current day's OHLCV from minute candles since 00:00 UTC."""
        current_timestamp = self.current_candle[0]
        dt = datetime.fromtimestamp(current_timestamp / 1000, tz=timezone.utc)
        
        # Calculate start of current day (00:00 UTC)
        day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start_ts = int(day_start.timestamp() * 1000)
        
        # Get all 1-minute candles from recent history
        candles_1m = self.get_candles(self.exchange, self.symbol, "1m")
        
        if candles_1m is None or len(candles_1m) == 0:
            self.log("[CPR Strategy] No 1-minute candles available for day construction", log_type='info')
            return None
        
        # Filter candles for current day only
        day_candles = [c for c in candles_1m if c[0] >= day_start_ts and c[0] <= current_timestamp]
        
        if not day_candles:
            self.log(f"[CPR Strategy] No candles found for current day starting {day_start}", log_type='info')
            return None
            
        # Construct daily OHLCV
        day_open = day_candles[0][1]      # Open of first candle
        day_high = max(c[3] for c in day_candles)  # Highest high
        day_low = min(c[4] for c in day_candles)   # Lowest low  
        day_close = day_candles[-1][2]    # Close of last candle
        day_volume = sum(c[5] for c in day_candles)  # Total volume
        
        self.log(f"[CPR Strategy] Constructed day candle from {len(day_candles)} 1m candles: O={day_open:.4f}, H={day_high:.4f}, L={day_low:.4f}, C={day_close:.4f}", log_type='info')
        
        return [day_start_ts, day_open, day_close, day_high, day_low, day_volume]

    def _is_analysis_window(self) -> bool:
        """Check if current time is 23:59 UTC for next day's CPR analysis."""
        current_timestamp = self.current_candle[0] / 1000
        dt = datetime.fromtimestamp(current_timestamp, tz=timezone.utc)
        
        is_analysis_time = dt.hour == 23 and dt.minute == 59
        
        if is_analysis_time:
            self.log(f"[CPR Strategy] 🔍 CPR ANALYSIS WINDOW at {dt.strftime('%H:%M:%S')} UTC", log_type='info')
            
        return is_analysis_time

    def _is_entry_window(self) -> bool:
        """Check if current time is 00:00 or 00:01 UTC for position entries."""
        current_timestamp = self.current_candle[0] / 1000
        dt = datetime.fromtimestamp(current_timestamp, tz=timezone.utc)
        
        # Allow entries during 00:00 and 00:01 to accommodate selection timing
        is_entry_time = dt.hour == 0 and (dt.minute == 0 or dt.minute == 1)
        
        if is_entry_time:
            self.log(f"[CPR Strategy] ✅ ENTRY WINDOW at {dt.strftime('%H:%M:%S')} UTC", log_type='info')
        
        return is_entry_time

    def _precalculate_next_day_cpr(self):
        """At 23:59 UTC, calculate tomorrow's CPR and immediately analyze + place all entries."""
        if not self._is_analysis_window():
            return
            
        # Get today's manually constructed candle
        today_candle = self._construct_current_day_candle()
        if not today_candle:
            self.log("[CPR Strategy] Cannot pre-calculate CPR: Unable to construct today's candle", log_type='info')
            return
            
        ts, o, c_price, h, l, v = today_candle
        
        # Convert timestamps for logging
        today_date = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
        current_timestamp = self.current_candle[0] / 1000
        tomorrow_date = datetime.fromtimestamp(current_timestamp + 86400, tz=timezone.utc).strftime('%Y-%m-%d')
        
        # Calculate tomorrow's CPR using today's H, L, C
        tomorrow_cpr = compute_cpr(h, l, c_price)
        tomorrow_date_epoch = (self.current_candle[0] // 86_400_000) + 1
        
        # Store for tomorrow's use
        self.next_day_cpr = tomorrow_cpr
        self.next_day_cpr_date = tomorrow_date_epoch
        
        self.log(f"[CPR Strategy] PRE-CALCULATED CPR at 23:59 UTC using {today_date} candle for {tomorrow_date} trading", log_type='info')
        self.log(f"[CPR Strategy] Today's candle: O={o:.4f}, H={h:.4f}, L={l:.4f}, C={c_price:.4f}", log_type='info')
        self.log(f"[CPR Strategy] Tomorrow's CPR: Pivot={tomorrow_cpr[0]:.4f}, BC={tomorrow_cpr[1]:.4f}, TC={tomorrow_cpr[2]:.4f}", log_type='info')
        
        # Immediately analyze and place all entries for tomorrow
        self._analyze_and_place_entries_for_tomorrow()

    def _analyze_and_place_entries_for_tomorrow(self):
        """At 23:59, analyze all tickers and immediately place entries using tomorrow's open price."""
        if self.next_day_cpr is None:
            return
            
        current_day_epoch = (self.current_candle[0] // 86_400_000) + 1  # Tomorrow's epoch
        ticker = f"{self.symbol}"
        
        # Only reset analysis once per day when the first ticker arrives
        if CPRReversionStrategy._analysis_date != current_day_epoch:
            CPRReversionStrategy._daily_ticker_analysis = {}
            CPRReversionStrategy._selected_tickers = []
            CPRReversionStrategy._pending_entries = {}
            CPRReversionStrategy._analysis_complete = False
            CPRReversionStrategy._analysis_date = current_day_epoch  # Set immediately to prevent other tickers from resetting
            self.log(f"[CPR Strategy] 🔄 RESET ANALYSIS for day {current_day_epoch}", log_type='info')
        
        # Get tomorrow's opening price (use current close as proxy)
        entry_price = self.close  # 23:59 close ≈ 00:00 open
        curr_pivot, curr_bc, curr_tc = self.next_day_cpr
        
        # Analyze entry opportunity for this ticker
        entry_signal = None
        delta = 0
        target_price = 0
        
        # Check SHORT conditions (price above CPR range)
        if entry_price > curr_tc:
            delta = delta_from_closest_cpr_bound(entry_price, curr_bc, curr_tc)
            if delta >= self.min_delta:
                entry_signal = 'SHORT'
                target_price = curr_tc if self.target_selection == 'closest' else curr_bc
                
        # Check LONG conditions (price below CPR range)
        elif entry_price < curr_bc:
            delta = delta_from_closest_cpr_bound(entry_price, curr_bc, curr_tc)
            if delta >= self.min_delta:
                entry_signal = 'LONG'
                target_price = curr_bc if self.target_selection == 'closest' else curr_tc
        
        # Store analysis
        CPRReversionStrategy._daily_ticker_analysis[ticker] = {
            'open_price': entry_price,
            'curr_bc': curr_bc,
            'curr_tc': curr_tc,
            'curr_pivot': curr_pivot,
            'entry_signal': entry_signal,
            'delta': delta,
            'target_price': target_price,
        }
        
        self.log(f"[CPR Strategy] {ticker} 23:59 Analysis: Signal={entry_signal}, Delta={delta:.6f} ({delta*100:.3f}%), Price={entry_price:.4f}", log_type='info')
        
        # Perform selection once all tickers analyzed
        self._perform_ticker_selection_at_2359(current_day_epoch)

    def _perform_ticker_selection_at_2359(self, current_day_epoch):
        """At 23:59, rank all tickers by delta and select top 3 for immediate entry."""
        # Only perform selection once per day
        if (CPRReversionStrategy._analysis_date == current_day_epoch and 
            CPRReversionStrategy._analysis_complete):
            return
            
        # Wait for all 4 tickers to complete analysis
        expected_tickers = {'SOL-USDT', 'DOGE-USDT', 'CRV-USDT', 'XRP-USDT'}
        analyzed_tickers = set(CPRReversionStrategy._daily_ticker_analysis.keys())
        
        if not expected_tickers.issubset(analyzed_tickers):
            # Not all tickers analyzed yet, wait
            return
            
        # All tickers analyzed - perform selection
        valid_candidates = []
        for ticker, analysis in CPRReversionStrategy._daily_ticker_analysis.items():
            if analysis['entry_signal'] and analysis['delta'] >= 0.001:  # 0.1% minimum
                valid_candidates.append({
                    'ticker': ticker,
                    'delta': analysis['delta'],
                    'signal': analysis['entry_signal']
                })
        
        # Sort by delta descending and take top 3
        valid_candidates.sort(key=lambda x: x['delta'], reverse=True)
        selected = valid_candidates[:3]  # Top 3
        
        CPRReversionStrategy._selected_tickers = [s['ticker'] for s in selected]
        CPRReversionStrategy._analysis_date = current_day_epoch
        CPRReversionStrategy._analysis_complete = True
        
        self.log(f"[CPR Strategy] 🎯 SELECTION COMPLETE AT 23:59: {len(selected)}/{len(valid_candidates)} selected", log_type='info')
        for s in selected:
            self.log(f"[CPR Strategy] ✅ SELECTED: {s['ticker']} {s['signal']} Delta={s['delta']*100:.3f}%", log_type='info')
        
        # Set pending entries for all selected tickers
        CPRReversionStrategy._pending_entries = {}
        for s in selected:
            CPRReversionStrategy._pending_entries[s['ticker']] = s['signal']
            self.log(f"[CPR Strategy] ⏳ PENDING ENTRY: {s['ticker']} {s['signal']}", log_type='info')

    def _check_and_enter_positions(self):
        """Legacy 00:00 entry logic - DISABLED. All entries now placed at 23:59."""
        # This method is now disabled - all entries placed at 23:59 UTC
        return


    def before(self):
        """Called before should_long/should_short on each candle."""
        self._precalculate_next_day_cpr()  # At 23:59 UTC - handles analysis and immediate entry
        self._reset_daily_analysis_if_new_day()
        self._check_pending_entries()  # Check if this ticker should enter based on selection
    
    def _check_pending_entries(self):
        """Check if this ticker has a pending entry and set entry flags."""
        ticker = f"{self.symbol}"
        
        # Check if this ticker has a pending entry
        if ticker in CPRReversionStrategy._pending_entries:
            signal = CPRReversionStrategy._pending_entries[ticker]
            
            # Only proceed if no position is open and we have analysis data
            if not self.position.is_open and ticker in CPRReversionStrategy._daily_ticker_analysis:
                self.entry_data = CPRReversionStrategy._daily_ticker_analysis[ticker]
                
                if signal == 'SHORT':
                    self.should_enter_short = True
                    self.log(f"[CPR Strategy] ✅ {ticker} PENDING ENTRY ACTIVATED for SHORT!", log_type='info')
                elif signal == 'LONG':
                    self.should_enter_long = True
                    self.log(f"[CPR Strategy] ✅ {ticker} PENDING ENTRY ACTIVATED for LONG!", log_type='info')
                
                # Remove from pending entries once flag is set
                del CPRReversionStrategy._pending_entries[ticker]
    
    def _reset_daily_analysis_if_new_day(self):
        """Reset cross-ticker analysis for new trading day (but not during 23:59 analysis)."""
        current_trading_day_epoch = self.current_candle[0] // 86_400_000
        
        # Don't reset if we're in the 23:59 analysis window (it handles its own reset)
        if self._is_analysis_window():
            return
            
        # Reset once per day when moving to new day
        if CPRReversionStrategy._analysis_date != current_trading_day_epoch:
            CPRReversionStrategy._daily_ticker_analysis = {}
            CPRReversionStrategy._selected_tickers = []
            CPRReversionStrategy._pending_entries = {}
            CPRReversionStrategy._analysis_complete = False
            if hasattr(CPRReversionStrategy, '_wait_start_time'):
                delattr(CPRReversionStrategy, '_wait_start_time')
            
            # Only log reset once per day to avoid spam
            if CPRReversionStrategy._last_reset_logged != current_trading_day_epoch:
                CPRReversionStrategy._last_reset_logged = current_trading_day_epoch
                self.log(f"[CPR Strategy] 🔄 RESET for new trading day {current_trading_day_epoch}", log_type='info')

    # ------------------------------------------------------------------
    # Entry logic (now handled in before() method)
    # ------------------------------------------------------------------
    def should_long(self) -> bool:
        if self.should_enter_long:
            self.log(f"[CPR Strategy] should_long() TRUE for {self.symbol} - executing LONG entry", log_type='info')
            self.should_enter_long = False  # Reset flag
            return True
        return False

    def should_short(self) -> bool:
        if self.should_enter_short:
            self.log(f"[CPR Strategy] should_short() TRUE for {self.symbol} - executing SHORT entry", log_type='info')
            self.should_enter_short = False  # Reset flag
            return True
        return False

    # ------------------------------------------------------------------
    # Orders (mandatory methods - actual logic handled in before())
    # ------------------------------------------------------------------
    def go_long(self):
        self.log(f"[CPR Strategy] go_long() called for {self.symbol}. Entry data exists: {self.entry_data is not None}", log_type='info')
        if not self.entry_data:
            self.log(f"[CPR Strategy] go_long() ABORTED for {self.symbol}: No entry data", log_type='info')
            return
            
        entry_price = self.entry_data['open_price']
        curr_bc = self.entry_data['curr_bc']
        curr_tc = self.entry_data['curr_tc']
        target_price = self.entry_data['target_price']  # Pre-calculated target
            
        stop_price = entry_price * (1 - self.stop_loss_pct)
        
        # Calculate position size
        qty = utils.risk_to_qty(
            capital=self.available_margin,
            risk_per_capital=self.risk_per_trade,
            entry_price=entry_price,
            stop_loss_price=stop_price,
            fee_rate=self.fee_rate
        )
        
        # Market order for immediate execution at current price
        self.buy = qty, self.price
        self.log(f"[CPR Strategy] ✅ {self.symbol} LONG MARKET @ {entry_price:.4f}, target: {target_price:.4f} ({self.target_selection}), stop: {stop_price:.4f}, qty: {qty:.4f}", log_type='info')

    def go_short(self):
        self.log(f"[CPR Strategy] go_short() called for {self.symbol}. Entry data exists: {self.entry_data is not None}", log_type='info')
        if not self.entry_data:
            self.log(f"[CPR Strategy] go_short() ABORTED for {self.symbol}: No entry data", log_type='info')
            return
            
        entry_price = self.entry_data['open_price']
        curr_bc = self.entry_data['curr_bc']  
        curr_tc = self.entry_data['curr_tc']
        target_price = self.entry_data['target_price']  # Pre-calculated target
            
        stop_price = entry_price * (1 + self.stop_loss_pct)
        
        # Calculate position size
        qty = utils.risk_to_qty(
            capital=self.available_margin,
            risk_per_capital=self.risk_per_trade,
            entry_price=entry_price,
            stop_loss_price=stop_price,
            fee_rate=self.fee_rate
        )
        
        # Market order for immediate execution at current price
        self.sell = qty, self.price
        self.log(f"[CPR Strategy] ✅ {self.symbol} SHORT MARKET @ {entry_price:.4f}, target: {target_price:.4f} ({self.target_selection}), stop: {stop_price:.4f}, qty: {qty:.4f}", log_type='info')

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------
    def on_open_position(self, order) -> None:
        self.position_opened_at = self.current_candle[0]
        
        # Use pre-calculated target price from entry data if available
        if self.entry_data and 'target_price' in self.entry_data:
            take_profit = self.entry_data['target_price']
        else:
            # Fallback to original logic
            curr_pivot, curr_bc, curr_tc = self.curr_cpr
            if self.is_long:
                take_profit = curr_bc if self.target_selection == 'closest' else curr_tc
            else:
                take_profit = curr_tc if self.target_selection == 'closest' else curr_bc
        
        # Calculate stop loss
        if self.is_long:
            stop_price = self.position.entry_price * (1 - self.stop_loss_pct)
        else:
            stop_price = self.position.entry_price * (1 + self.stop_loss_pct)
        
        self.take_profit = self.position.qty, take_profit
        self.stop_loss = self.position.qty, stop_price
        
        side = 'LONG' if self.is_long else 'SHORT'
        self.log(f"[CPR Strategy] {self.symbol} {side} position opened at {self.position.entry_price:.4f}. TP: {take_profit:.4f} ({self.target_selection}), SL: {stop_price:.4f}", log_type='info')


    def should_cancel_entry(self) -> bool:
        # Don't automatically cancel orders - let them execute
        return False


    def update_position(self):
        if not self.position.is_open or self.position_opened_at is None:
            return
        
        # Check if max position time has been exceeded
        current_time = self.current_candle[0]
        position_duration_hours = (current_time - self.position_opened_at) / (1000 * 60 * 60)
        
        if position_duration_hours >= self.max_position_hours:
            self.log(f"[CPR Strategy] Max position time ({self.max_position_hours}h) reached. Closing position.", log_type='info')
            self.liquidate()
            return

    # ------------------------------------------------------------------
    # Optimizer hyperparameters
    # ------------------------------------------------------------------
    @property
    def min_delta(self):
        """Minimum delta (percentage) from CPR bound required to enter position."""
        return self.hp.get('min_delta', 0.0005)

    @property
    def risk_per_trade(self):
        """Risk percentage of available capital per trade."""
        return self.hp.get('risk_per_trade', 3.0)

    @property
    def stop_loss_pct(self):
        """Stop loss percentage from entry price."""
        return self.hp.get('stop_loss_pct', 0.05)

    @property
    def target_selection(self):
        """Target selection strategy: 'closest' (safest) or 'furthest' (more aggressive)."""
        return self.hp.get('target_selection', 'closest')

    @property
    def max_position_hours(self):
        """Maximum hours to hold position before force close."""
        return self.hp.get('max_position_hours', 24)

    def on_close_position(self, order) -> None:
        """Reset position tracking when position is closed."""
        self.position_opened_at = None
        side = 'LONG' if order.side == sides.BUY else 'SHORT'
        self.log(f"[CPR Strategy] {side} position closed. PnL: {self.position.pnl:.2f}", log_type='info')

    def watch_list(self) -> list:
        """Return list of values to monitor during live trading."""
        # Use next_day_cpr if available (pre-calculated), otherwise fall back to curr_cpr
        active_cpr = self.next_day_cpr if self.next_day_cpr else self.curr_cpr
        
        if not active_cpr:
            return [('CPR Status', 'Not calculated')]
        
        curr_pivot, curr_bc, curr_tc = active_cpr
        
        # Calculate delta using open price (same as entry logic)
        delta_open = 0
        if self.open > curr_tc:
            delta_open = delta_from_closest_cpr_bound(self.open, curr_bc, curr_tc)
        elif self.open < curr_bc:
            delta_open = delta_from_closest_cpr_bound(self.open, curr_bc, curr_tc)
        
        # Show which window we're in
        current_timestamp = self.current_candle[0] / 1000
        dt = datetime.fromtimestamp(current_timestamp, tz=timezone.utc)
        window_status = "Analysis (23:59)" if dt.hour == 23 and dt.minute == 59 else "Entry (00:00)" if dt.hour == 0 and dt.minute == 0 else "Waiting"
        
        return [
            ('Open Price', self.open),
            ('Close Price', self.price),
            ('CPR Pivot', curr_pivot),
            ('CPR BC', curr_bc),
            ('CPR TC', curr_tc),
            ('Delta % (Open)', f"{delta_open * 100:.3f}%"),
            ('Window Status', window_status),
            ('CPR Source', 'Pre-calc' if self.next_day_cpr else 'Legacy'),
            ('Position Time (h)', f"{((self.current_candle[0] - self.position_opened_at) / (1000 * 60 * 60)):.1f}" if self.position_opened_at else 'N/A'),
        ]

    def hyperparameters(self) -> list:
        """Parameters exposed to Jesse's genetic optimizer."""
        return [
            {
                'name': 'min_delta',
                'type': float,
                'min': 0.0001,  # 0.01% minimum delta
                'max': 0.02,    # 2% maximum delta (increased for crypto volatility)
                'step': 0.0001,
                'default': 0.001,  # 0.1% default (doubled from 0.05%)
            },
            {
                'name': 'risk_per_trade',
                'type': float,
                'min': 0.5,   # Lower minimum for conservative testing
                'max': 40.0,  # Up to 40% risk per trade as requested
                'step': 0.5,  # Wider steps for higher range
                'default': 3.0,
            },
            {
                'name': 'stop_loss_pct',
                'type': float,
                'min': 0.005,  # 0.5% minimum (tighter stops)
                'max': 1.0,    # 100% maximum (complete position loss allowed)
                'step': 0.01,  # 1% steps for wider range
                'default': 0.20,  # 20% default (reasonable starting point)
            },
            {
                'name': 'target_selection',
                'type': 'categorical',
                'options': ['closest', 'furthest'],
                'default': 'closest',
            },
            {
                'name': 'max_position_hours',
                'type': int,
                'min': 2,    # Minimum 2 hours
                'max': 72,   # Up to 3 days
                'step': 2,   # 2-hour increments
                'default': 24,
            },
        ]