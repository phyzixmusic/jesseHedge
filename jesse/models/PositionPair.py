"""
PositionPair: Wrapper for hedge mode that manages both long and short positions
for the same symbol simultaneously.
"""
from typing import Union
import numpy as np
from jesse.models.Position import Position


class PositionPair:
    """
    Manages both long and short positions for hedge mode.
    
    In hedge mode, traders can hold both long and short positions
    on the same symbol simultaneously. This class wraps both positions
    and provides convenient access to either side.
    """
    
    def __init__(self, exchange_name: str, symbol: str, attributes: dict = None):
        self.exchange_name = exchange_name
        self.symbol = symbol
        self._strategy = None  # Store strategy reference
        
        # Create separate positions for long and short sides
        self.long_position = Position(exchange_name, symbol, attributes, side='long')
        self.short_position = Position(exchange_name, symbol, attributes, side='short')
    
    @property
    def strategy(self):
        """Get strategy reference."""
        return self._strategy
    
    @strategy.setter
    def strategy(self, value):
        """
        Set strategy reference for both positions.
        When position.strategy is set externally, propagate to both long and short.
        """
        self._strategy = value
        self.long_position.strategy = value
        self.short_position.strategy = value
    
    def get_position(self, side: str) -> Position:
        """
        Get position by side.
        
        Args:
            side: 'long' or 'short'
        
        Returns:
            Position object for the specified side
        """
        if side == 'long':
            return self.long_position
        elif side == 'short':
            return self.short_position
        else:
            raise ValueError(f"Invalid side: {side}. Must be 'long' or 'short'")
    
    @property
    def net_qty(self) -> float:
        """
        Net quantity across both positions (long qty - short qty).
        
        In hedge mode, you can have both long and short positions open.
        This returns the net exposure.
        
        Note: In hedge mode, both positions store qty as positive values,
        so short qty needs to be subtracted (not added as negative).
        """
        # In hedge mode, both sides store positive quantities
        # Long position: qty is positive
        # Short position: qty is also stored as positive (or negative, depends on implementation)
        # Net = long - |short|
        long_qty = self.long_position.qty if self.long_position.qty else 0
        short_qty = abs(self.short_position.qty) if self.short_position.qty else 0
        return long_qty - short_qty
    
    @property
    def total_pnl(self) -> float:
        """Combined PNL from both long and short positions."""
        return self.long_position.pnl + self.short_position.pnl
    
    @property
    def total_value(self) -> float:
        """Combined notional value of both positions."""
        long_value = self.long_position.value if self.long_position.value else 0
        short_value = abs(self.short_position.value) if self.short_position.value else 0
        return long_value + short_value
    
    @property
    def is_both_closed(self) -> bool:
        """Are both long and short positions closed?"""
        return self.long_position.is_close and self.short_position.is_close
    
    @property
    def has_any_open(self) -> bool:
        """Is at least one position (long or short) open?"""
        return self.long_position.is_open or self.short_position.is_open
    
    @property
    def is_open(self) -> bool:
        """
        Compatibility property for existing code that checks position.is_open.
        Returns True if either long or short position is open.
        """
        return self.has_any_open
    
    @property
    def is_close(self) -> bool:
        """
        Compatibility property for existing code that checks position.is_close.
        Returns True only if both positions are closed.
        """
        return self.is_both_closed
    
    @property
    def mode(self) -> str:
        """
        Compatibility property - return leverage mode of the exchange.
        Both positions share the same exchange and leverage mode.
        """
        return self.long_position.mode
    
    @property
    def current_price(self) -> float:
        """
        Compatibility property - return current price.
        Both positions share the same current price.
        """
        return self.long_position.current_price
    
    @current_price.setter
    def current_price(self, value: float):
        """Set current price for both positions."""
        self.long_position.current_price = value
        self.short_position.current_price = value
    
    @property
    def type(self) -> str:
        """
        Compatibility property - return position type.
        In hedge mode, if both positions are closed, return 'close'.
        Otherwise, return the type of the dominant position (based on net qty).
        """
        if self.is_both_closed:
            return 'close'
        
        # Return type based on net exposure
        if self.net_qty > 0:
            return 'long'
        elif self.net_qty < 0:
            return 'short'
        else:
            # Equal long/short positions
            return 'close'
    
    @property
    def qty(self) -> float:
        """
        Compatibility property - return net quantity.
        For compatibility with existing code that uses position.qty
        """
        return self.net_qty
    
    @property
    def exchange(self):
        """
        Compatibility property - return exchange object.
        Both positions share the same exchange.
        """
        return self.long_position.exchange
    
    @property
    def is_long(self) -> bool:
        """
        Compatibility property - is there an open long position?
        """
        return self.long_position.is_open
    
    @property
    def is_short(self) -> bool:
        """
        Compatibility property - is there an open short position?
        """
        return self.short_position.is_open
    
    @property
    def previous_qty(self) -> float:
        """
        Compatibility property - return net previous quantity.
        For simplicity, use long position's previous_qty minus short's.
        """
        long_prev = self.long_position.previous_qty if hasattr(self.long_position, 'previous_qty') else 0
        short_prev = abs(self.short_position.previous_qty) if hasattr(self.short_position, 'previous_qty') else 0
        return long_prev - short_prev
    
    @property
    def entry_price(self):
        """
        Compatibility property - return entry price.
        In hedge mode, return the weighted average entry price based on position sizes.
        """
        long_value = abs(self.long_position.qty * self.long_position.entry_price) if self.long_position.entry_price and self.long_position.qty else 0
        short_value = abs(self.short_position.qty * self.short_position.entry_price) if self.short_position.entry_price and self.short_position.qty else 0
        total_qty = abs(self.long_position.qty) + abs(self.short_position.qty)
        
        if total_qty == 0:
            return None
        
        return (long_value + short_value) / total_qty
    
    def __getattr__(self, name):
        """
        Fallback for compatibility: delegate unknown attributes to long_position.
        This allows PositionPair to work with existing code that expects Position attributes.
        """
        # Avoid recursion for internal attributes
        if name in ['long_position', 'short_position', '_strategy']:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        
        # Try to get from long_position (they share most attributes)
        if hasattr(self, 'long_position'):
            return getattr(self.long_position, name)
        
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    @property
    def to_dict(self) -> dict:
        """Export both positions as a dictionary."""
        return {
            'mode': 'hedge',
            'symbol': self.symbol,
            'exchange': self.exchange_name,
            'long': self.long_position.to_dict,
            'short': self.short_position.to_dict,
            'net_qty': self.net_qty,
            'total_pnl': self.total_pnl,
            'total_value': self.total_value,
        }
    
    def update_from_stream(self, data: dict, is_initial: bool) -> None:
        """
        Update positions from WebSocket stream (live trading only).
        
        Args:
            data: Dictionary with 'long' and/or 'short' position data
            is_initial: Whether this is the initial position load
        """
        if 'long' in data:
            self.long_position.update_from_stream(data['long'], is_initial)
        if 'short' in data:
            self.short_position.update_from_stream(data['short'], is_initial)
    
    def _on_executed_order(self, order) -> None:
        """
        Route executed order to the correct position based on position_side.

        In hedge mode, orders should specify which position (long/short) they target.
        For orders without position_side (e.g., auto-generated stop-loss), we route
        based on which position is open.

        Args:
            order: Order object with optional position_side attribute
        """
        if order.position_side == 'long':
            self.long_position._on_executed_order(order)
        elif order.position_side == 'short':
            self.short_position._on_executed_order(order)
        elif order.position_side is None:
            # No position_side specified - infer from order side and open positions
            # This handles auto-generated orders (stop-loss/take-profit) that don't have position_side
            from jesse.enums import sides
            if order.side == sides.BUY:
                # Route to long position (or close short if long not open)
                target = self.long_position if self.long_position.is_open or not self.short_position.is_open else self.short_position
                target._on_executed_order(order)
            else:  # SELL
                # Route to short position (or close long if short not open)
                target = self.short_position if self.short_position.is_open or not self.long_position.is_open else self.long_position
                target._on_executed_order(order)
        else:
            raise ValueError(
                f"In hedge mode, invalid position_side: {order.position_side}"
            )
