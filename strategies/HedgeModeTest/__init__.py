"""
Simple test strategy to verify hedge mode functionality.

This strategy:
1. Opens a long position at index 5
2. Opens a short position at index 10 (while long is still open)
3. Closes long at index 20
4. Closes short at index 25

This demonstrates simultaneous long+short positions and validates
that the backtest properly tracks and reports both positions.

IMPORTANT: This strategy FORCES hedge mode to be enabled, regardless of
the backtest configuration. This is necessary because the Jesse website
doesn't have a UI field for futures_position_mode.
"""
from jesse.strategies import Strategy
import jesse.helpers as jh
from jesse.models.PositionPair import PositionPair
from jesse.config import config

# ============================================================================
# FORCE HEDGE MODE ON - This must happen at MODULE load time
# ============================================================================
# This code runs when the strategy module is imported, BEFORE any Strategy
# objects are created. This ensures hedge mode is enabled before positions
# are initialized.
#
# This is necessary because the Jesse website doesn't expose
# futures_position_mode in the backtest configuration UI.
# ============================================================================
def _enable_hedge_mode_for_all_exchanges():
    """Enable hedge mode for all futures exchanges in the config"""
    try:
        for exchange_name, exchange_config in config['env']['exchanges'].items():
            if exchange_config.get('type') == 'futures':
                # Set hedge mode
                exchange_config['futures_position_mode'] = 'hedge'
                print(f"[HedgeModeTest] ✅ Enabled hedge mode for: {exchange_name}")
    except Exception as e:
        print(f"[HedgeModeTest] ❌ Error enabling hedge mode: {e}")

# Execute the function at module import time
_enable_hedge_mode_for_all_exchanges()
# ============================================================================


class HedgeModeTest(Strategy):
    def __init__(self):
        super().__init__()
        self.long_opened = False
        self.short_opened = False
        self.long_closed = False
        self.short_closed = False
        self._position_pair_forced = False  # Track if we've tried to force PositionPair

    def _force_position_pair(self):
        """
        Replace the Position object with PositionPair if hedge mode is active
        but Position was created (timing issue).

        This is a workaround for when the config is set too late.
        """
        # Only try once
        if self._position_pair_forced:
            return

        self._position_pair_forced = True

        from jesse.store import store
        from jesse.models import Position

        # Check if we should be in hedge mode
        position_mode = config['env']['exchanges'].get(self.exchange, {}).get('futures_position_mode', 'one-way')

        self.log(f"🔍 Checking position type...")
        self.log(f"   Config futures_position_mode: {position_mode}")
        self.log(f"   Current position type: {type(self.position).__name__}")
        self.log(f"   Is Position instance: {isinstance(self.position, Position)}")
        self.log(f"   Is PositionPair instance: {isinstance(self.position, PositionPair)}")

        # Check if we need to replace (hedge mode but wrong type)
        if position_mode == 'hedge' and isinstance(self.position, Position) and not isinstance(self.position, PositionPair):
            self.log("⚠️  Position was created as Position instead of PositionPair")
            self.log("🔧 FORCING replacement with PositionPair...")

            # Create a new PositionPair
            new_position = PositionPair(self.exchange, self.symbol)

            # CRITICAL: Set the strategy reference on both sub-positions
            new_position.long_position.strategy = self
            new_position.short_position.strategy = self

            # Copy current price and any existing position data
            if hasattr(self.position, 'current_price'):
                new_position.current_price = self.position.current_price

            # Copy strategy reference from old position
            if hasattr(self.position, 'strategy'):
                new_position.strategy = self.position.strategy

            # If there's an existing position, migrate it
            if self.position.qty != 0:
                if self.position.qty > 0:  # Was long
                    new_position.long_position.qty = self.position.qty
                    new_position.long_position.entry_price = self.position.entry_price
                else:  # Was short
                    new_position.short_position.qty = abs(self.position.qty)
                    new_position.short_position.entry_price = self.position.entry_price

            # Replace in strategy
            self.position = new_position

            # Replace in store
            key = f'{self.exchange}-{self.symbol}'
            store.positions.storage[key] = new_position

            # Update broker reference
            self.broker.position = new_position

            self.log(f"✅ Successfully replaced with PositionPair!")
            self.log(f"New position type: {type(self.position).__name__}")
        elif position_mode == 'hedge' and isinstance(self.position, PositionPair):
            self.log("✅ Position is already PositionPair - no replacement needed!")
        else:
            self.log(f"ℹ️  No replacement needed (mode: {position_mode})")

    def before(self) -> None:
        """Log hedge mode status and force position pair replacement"""
        # Only run once at the beginning
        if self.index == 0:
            # Try to force PositionPair replacement before logging
            self._force_position_pair()

            self.log("=" * 80)
            self.log("🔧 HEDGE MODE TEST STRATEGY INITIALIZED")
            self.log("=" * 80)
            self.log(f"Hedge Mode Active: {self.is_hedge_mode}")
            self.log(f"Exchange: {self.exchange}")
            self.log(f"Symbol: {self.symbol}")

            if self.is_hedge_mode:
                self.log("✅ HEDGE MODE IS ENABLED - Can open long + short simultaneously")
                self.log(f"Position type: {type(self.position).__name__}")
            else:
                self.log("❌ ONE-WAY MODE - Only one direction at a time")

            self.log("=" * 80)

    @property
    def is_hedge_mode(self) -> bool:
        """Check if exchange is configured for hedge mode"""
        return jh.get_config(f'env.exchanges.{self.exchange}.futures_position_mode') == 'hedge'

    @property
    def long_position_qty(self) -> float:
        """Get long position quantity"""
        if self.is_hedge_mode and isinstance(self.position, PositionPair):
            return self.position.long_position.qty
        elif not self.is_hedge_mode and self.is_long:
            return self.position.qty
        return 0

    @property
    def short_position_qty(self) -> float:
        """Get short position quantity (always positive)"""
        if self.is_hedge_mode and isinstance(self.position, PositionPair):
            # Short qty might be stored as negative, so take absolute value
            return abs(self.position.short_position.qty)
        return 0

    def should_long(self) -> bool:
        # Open long at index 5
        return self.index == 5 and not self.long_opened

    def should_short(self) -> bool:
        # We never use should_short for entry in hedge mode
        # Instead, we manage positions in update_position()
        return False

    def go_long(self):
        """Open initial long position"""
        qty = 1.0

        self.log(f"=== OPENING LONG POSITION ===")
        self.log(f"Index: {self.index}, Price: {self.price}")
        self.log(f"Hedge Mode: {self.is_hedge_mode}")

        if self.is_hedge_mode:
            self.buy = qty, self.price, 'long'
        else:
            self.buy = qty, self.price

        self.long_opened = True
        self.log(f"Long position order submitted")

    def go_short(self):
        # Not used - we manage short positions in update_position()
        pass

    def should_cancel_entry(self) -> bool:
        return False

    def on_open_position(self, order) -> None:
        """Called when a position is opened"""
        self.log(f"=== POSITION OPENED (on_open_position callback) ===")
        self.log(f"Order side: {order.side}")
        self.log(f"Order qty: {order.qty}")
        if hasattr(order, 'position_side'):
            self.log(f"Position side: {order.position_side}")
        else:
            self.log(f"⚠️  Order has NO position_side attribute!")

        if self.is_hedge_mode and isinstance(self.position, PositionPair):
            self.log(f"Long qty: {self.position.long_position.qty}")
            self.log(f"Short qty: {self.position.short_position.qty}")
            self.log(f"Net qty: {self.position.net_qty}")
        else:
            self.log(f"Position type: {type(self.position).__name__}")
            self.log(f"Position qty: {self.position.qty if hasattr(self.position, 'qty') else 'N/A'}")

    def update_position(self) -> None:
        """Manage hedge positions"""
        if not self.is_hedge_mode:
            return

        # Open short position at index 10 (while long is still open)
        if self.index == 10 and not self.short_opened and self.long_position_qty > 0:
            qty = 0.5  # Half the size of long position

            self.log(f"=== OPENING SHORT (HEDGE) POSITION ===")
            self.log(f"Index: {self.index}, Price: {self.price}")
            self.log(f"Long qty: {self.long_position_qty}")
            self.log(f"Short qty to open: {qty}")
            self.log(f"Using broker.sell_at_market() with position_side='short'")

            try:
                # Use broker directly to bypass the self.sell property validation
                order = self.broker.sell_at_market(qty, position_side='short')
                self.short_opened = True
                if order:
                    self.log(f"✅ Short order submitted directly via broker: {order.id}")
                else:
                    self.log(f"⚠️  Broker returned None - order may have been rejected")
            except Exception as e:
                self.log(f"❌ ERROR submitting short order via broker: {e}")
                import traceback
                self.log(f"Traceback: {traceback.format_exc()}")

        # Close long position at index 20
        elif self.index == 20 and not self.long_closed and self.long_position_qty > 0:
            qty = self.long_position_qty

            self.log(f"=== CLOSING LONG POSITION ===")
            self.log(f"Index: {self.index}, Price: {self.price}")
            self.log(f"Closing qty: {qty}")

            try:
                # Use broker directly to close long position
                order = self.broker.sell_at_market(qty, position_side='long')
                self.long_closed = True
                if order:
                    self.log(f"✅ Long close order submitted via broker: {order.id}")
                else:
                    self.log(f"⚠️  Broker returned None - order may have been rejected")
            except Exception as e:
                self.log(f"❌ ERROR closing long position: {e}")
                import traceback
                self.log(f"Traceback: {traceback.format_exc()}")

        # Close short position at index 25
        elif self.index == 25 and not self.short_closed and self.short_position_qty > 0:
            qty = self.short_position_qty

            self.log(f"=== CLOSING SHORT POSITION ===")
            self.log(f"Index: {self.index}, Price: {self.price}")
            self.log(f"Closing qty: {qty}")

            try:
                # Use broker directly to close short position
                order = self.broker.buy_at_market(qty, position_side='short')
                self.short_closed = True
                if order:
                    self.log(f"✅ Short close order submitted via broker: {order.id}")
                else:
                    self.log(f"⚠️  Broker returned None - order may have been rejected")
            except Exception as e:
                self.log(f"❌ ERROR closing short position: {e}")
                import traceback
                self.log(f"Traceback: {traceback.format_exc()}")

    def watch_list(self) -> list:
        """Display in watch list"""
        items = [
            ('Index', self.index),
            ('Hedge Mode', 'Yes' if self.is_hedge_mode else 'No'),
        ]

        if self.is_hedge_mode and isinstance(self.position, PositionPair):
            items.extend([
                ('Long Qty', f"{self.long_position_qty:.4f}"),
                ('Short Qty', f"{self.short_position_qty:.4f}"),
                ('Net Qty', f"{self.position.net_qty:.4f}"),
            ])

            if self.long_position_qty > 0:
                items.append(('Long PNL', f"${self.position.long_position.pnl:.2f}"))
            if self.short_position_qty > 0:
                items.append(('Short PNL', f"${self.position.short_position.pnl:.2f}"))
            if self.long_position_qty > 0 or self.short_position_qty > 0:
                items.append(('Total PNL', f"${self.position.total_pnl:.2f}"))
        else:
            items.extend([
                ('Position Qty', f"{self.position.qty:.4f}" if self.is_open else "0"),
                ('Position Type', self.position.type if self.is_open else 'closed'),
            ])

        return items

    def after(self) -> None:
        """Add visual indicators to charts"""
        if self.is_hedge_mode and isinstance(self.position, PositionPair):
            # Add position quantities to chart
            self.add_extra_line_chart('Positions', 'Long Qty', self.long_position_qty)
            self.add_extra_line_chart('Positions', 'Short Qty', self.short_position_qty)
            self.add_extra_line_chart('Positions', 'Net Qty', self.position.net_qty)

            # Add PNL tracking
            if self.long_position_qty > 0 or self.short_position_qty > 0:
                self.add_extra_line_chart('PNL', 'Total PNL', self.position.total_pnl)
                if self.long_position_qty > 0:
                    self.add_extra_line_chart('PNL', 'Long PNL', self.position.long_position.pnl)
                if self.short_position_qty > 0:
                    self.add_extra_line_chart('PNL', 'Short PNL', self.position.short_position.pnl)
