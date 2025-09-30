# Hedge Mode Implementation Plan for Jesse

## Executive Summary

This document outlines a comprehensive plan to add hedge mode (dual-directional position) support for Bybit perpetuals trading in the Jesse framework. Hedge mode allows traders to hold simultaneous long and short positions on the same symbol, which is essential for certain advanced trading strategies.

**Target Scope**: Backtest, Optimization, and Live Trading modes  
**Primary Exchange**: Bybit USDT/USDC Perpetuals  
**Estimated Complexity**: High - Core architectural changes required  
**Estimated Timeline**: 3-4 weeks for full implementation and testing

---

## Table of Contents

1. [Background & Motivation](#1-background--motivation)
2. [Current Architecture Analysis](#2-current-architecture-analysis)
3. [Proposed Architecture](#3-proposed-architecture)
4. [Implementation Phases](#4-implementation-phases)
5. [Detailed Implementation Steps](#5-detailed-implementation-steps)
6. [Testing Strategy](#6-testing-strategy)
7. [Migration & Backwards Compatibility](#7-migration--backwards-compatibility)
8. [Risks & Mitigation](#8-risks--mitigation)
9. [Performance Considerations](#9-performance-considerations)
10. [Future Extensions](#10-future-extensions)

---

## 1. Background & Motivation

### What is Hedge Mode?

Bybit (and other exchanges) offer two position modes for perpetual futures:

- **One-Way Mode** (Current): Can only hold a long OR short position at any given time
- **Hedge Mode** (Target): Can hold both long AND short positions simultaneously

### Use Cases for Hedge Mode

1. **Market-neutral strategies**: Simultaneously shorting overvalued assets while longing undervalued ones
2. **Spread trading**: Holding opposing positions to profit from convergence/divergence
3. **Risk management**: Hedging an existing position without closing it
4. **Complex algorithmic strategies**: Grid trading, delta-neutral strategies, etc.

### Key Differences

| Aspect | One-Way Mode | Hedge Mode |
|--------|-------------|------------|
| Position Count | 1 per symbol | 2 per symbol (long + short) |
| Order Behavior | Opposite side reduces position | Each side independent |
| PNL Calculation | Single calculation | Separate for each side |
| API Complexity | Simple | Requires `positionIdx` parameter |

---

## 2. Current Architecture Analysis

### 2.1 Position Model Limitations

**File**: `jesse/models/Position.py`

**Current Design**:
```python
class Position:
    def __init__(self, exchange_name: str, symbol: str, ...):
        self.qty = 0  # Single quantity
        # Positive qty = long, Negative qty = short
```

**Problem**: 
- Only ONE `Position` object per symbol
- Position type determined by sign of `qty`
- Cannot represent simultaneous long/short positions

### 2.2 Exchange Configuration

**File**: `jesse/config.py`

**Current Settings**:
```python
'futures_leverage_mode': 'cross'  # or 'isolated'
'futures_leverage': 1
```

**Gap**: No `futures_position_mode` setting for one-way vs hedge

### 2.3 Exchange Drivers

**Interface**: `jesse/exchanges/exchange.py`

**Current Methods**:
```python
- market_order(symbol, qty, price, side, reduce_only)
- limit_order(symbol, qty, price, side, reduce_only)
- stop_order(symbol, qty, price, side, reduce_only)
```

**Gap**: No `position_idx` or position mode management

### 2.4 State Management

**Files**: `jesse/store/state_positions.py`, etc.

**Current Structure**:
```python
positions[exchange_name][symbol] = Position(...)
```

**Problem**: Dictionary key structure assumes one position per symbol

### 2.5 Broker & Order Logic

**File**: `jesse/services/broker.py`

**Current Logic**: Order side is determined by current position type (opposite side = reduce)

**Problem**: In hedge mode, order side doesn't automatically reduce opposite position

---

## 3. Proposed Architecture

### 3.1 New Position Mode Concept

Introduce a new configuration layer:

```python
# Config structure
'futures_position_mode': 'one-way'  # or 'hedge'
'futures_leverage_mode': 'cross'     # or 'isolated'
'futures_leverage': 1
```

### 3.2 Dual Position Model

Create a `PositionPair` wrapper for hedge mode:

```python
class PositionPair:
    """Wrapper for hedge mode positions"""
    def __init__(self, exchange_name: str, symbol: str):
        self.long_position = Position(exchange_name, symbol, side='long')
        self.short_position = Position(exchange_name, symbol, side='short')
        self.mode = 'hedge'
    
    @property
    def net_qty(self) -> float:
        """Net position quantity"""
        return self.long_position.qty + self.short_position.qty
    
    @property
    def total_pnl(self) -> float:
        """Combined PNL from both positions"""
        return self.long_position.pnl + self.short_position.pnl
```

### 3.3 Position State Management

**Backwards Compatible Approach**:

```python
# In state_positions.py
class StatePositions:
    def __init__(self):
        self.storage = {}
        self.position_mode = {}  # Track mode per exchange-symbol
    
    def get_position(self, exchange: str, symbol: str, side: str = None):
        """
        Get position for symbol.
        
        Args:
            side: In hedge mode, specify 'long' or 'short'. 
                  In one-way mode, ignored.
        """
        key = f"{exchange}-{symbol}"
        
        if self.is_hedge_mode(exchange, symbol):
            if side is None:
                # Return wrapper with both positions
                return self.storage[key]  # PositionPair
            else:
                # Return specific side
                return self.storage[key].get_position(side)
        else:
            # One-way mode - return single position
            return self.storage[key]  # Position
```

### 3.4 Order Routing

```python
class Broker:
    def buy_at(self, qty: float, price: float, hedge_mode_side: str = None):
        """
        Args:
            hedge_mode_side: In hedge mode, explicitly specify which 
                           side ('long' or 'short'). Ignored in one-way mode.
        """
        if self.is_hedge_mode and hedge_mode_side is None:
            raise ValueError("In hedge mode, must specify hedge_mode_side")
        
        return self.api.limit_order(
            self.exchange, self.symbol, qty, price, 
            sides.BUY, reduce_only=False, 
            position_idx=self._get_position_idx(hedge_mode_side)
        )
```

### 3.5 Exchange Driver Extensions

**New Abstract Method**:
```python
class Exchange(ABC):
    @abstractmethod
    def set_position_mode(self, symbol: str, mode: str) -> bool:
        """
        Set position mode for symbol
        
        Args:
            mode: 'one-way' or 'hedge'
        
        Returns:
            Success status
        """
        pass
```

**Implementation for Bybit**:
```python
class BybitDriver(Exchange):
    def set_position_mode(self, symbol: str, mode: str) -> bool:
        """
        Bybit API: POST /v5/position/switch-mode
        """
        payload = {
            'category': 'linear',
            'symbol': symbol,
            'mode': 0 if mode == 'one-way' else 3  # 0=one-way, 3=hedge
        }
        response = self._submit_request('/v5/position/switch-mode', payload)
        return response['retCode'] == 0
```

---

## 4. Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- Add position mode configuration
- Refactor Position model to support side parameter
- Create PositionPair wrapper class
- Update state management for dual positions

### Phase 2: Order & Execution Logic (Week 1-2)
- Update Broker class with hedge mode support
- Modify order execution logic
- Update position opening/closing logic
- Implement position-specific order routing

### Phase 3: Exchange Integration (Week 2)
- Add set_position_mode to Exchange interface
- Implement Bybit-specific position mode switching
- Update Sandbox driver for backtest support
- Implement position_idx parameter handling

### Phase 4: Metrics & Reporting (Week 2-3)
- Update PNL calculations for dual positions
- Modify metrics system to handle hedge mode
- Update report generation
- Update charts and visualization

### Phase 5: Testing & Validation (Week 3-4)
- Unit tests for all new components
- Integration tests for backtest mode
- Live trading simulation tests
- Performance benchmarking

### Phase 6: Documentation & Polish (Week 4)
- Update user documentation
- Add hedge mode examples
- Migration guide
- API reference updates

---

## 5. Detailed Implementation Steps

### 5.1 Configuration Changes

**File**: `jesse/config.py`

```python
# Add to default config
config = {
    'env': {
        'exchanges': {
            exchanges.SANDBOX: {
                'fee': 0,
                'type': 'futures',
                'futures_position_mode': 'one-way',  # NEW
                'futures_leverage_mode': 'cross',
                'futures_leverage': 1,
                'balance': 10_000,
            },
        },
    },
}

# Update set_config function
def set_config(conf: dict) -> None:
    # ... existing code ...
    if config['env']['exchanges'][e['name']]['type'] == 'futures':
        config['env']['exchanges'][e['name']]['futures_leverage'] = int(e.get('futures_leverage', 1))
        config['env']['exchanges'][e['name']]['futures_leverage_mode'] = e.get('futures_leverage_mode', 'cross')
        # NEW
        config['env']['exchanges'][e['name']]['futures_position_mode'] = e.get('futures_position_mode', 'one-way')
```

### 5.2 Position Model Refactoring

**File**: `jesse/models/Position.py`

```python
class Position:
    def __init__(
        self, 
        exchange_name: str, 
        symbol: str, 
        attributes: dict = None,
        side: str = None  # NEW: 'long', 'short', or None for one-way mode
    ) -> None:
        self.id = jh.generate_unique_id()
        self.side = side  # NEW
        self.entry_price = None
        self.exit_price = None
        self.current_price = None
        self.qty = 0  # Always positive in hedge mode
        # ... rest of existing code ...
        
        # NEW: Validate qty is always positive in hedge mode
        if self.is_hedge_mode and self.qty < 0:
            raise ValueError("In hedge mode, qty must be positive")
    
    @property
    def is_hedge_mode(self) -> bool:
        """Check if this position is in hedge mode"""
        return self.side is not None
    
    @property
    def type(self) -> str:
        """Position type: 'long', 'short', or 'close'"""
        if self.is_hedge_mode:
            # In hedge mode, type is determined by side, not qty sign
            if self.qty > self._min_qty:
                return self.side
            return 'close'
        else:
            # One-way mode: existing logic
            if self.is_long:
                return 'long'
            elif self.is_short:
                return 'short'
            return 'close'
    
    @property
    def is_long(self) -> bool:
        """Is this a long position?"""
        if self.is_hedge_mode:
            return self.side == 'long' and self.qty > self._min_qty
        else:
            # Existing one-way mode logic
            return self.qty > self._min_qty
    
    @property
    def is_short(self) -> bool:
        """Is this a short position?"""
        if self.is_hedge_mode:
            return self.side == 'short' and self.qty > self._min_qty
        else:
            # Existing one-way mode logic
            return self.qty < -abs(self._min_qty)
    
    def _update_qty(self, qty: float, operation='set'):
        """Update quantity"""
        self.previous_qty = self.qty
        
        if self.is_hedge_mode:
            # In hedge mode, qty is always positive
            if operation == 'set':
                self.qty = abs(qty)
            elif operation == 'add':
                self.qty = sum_floats(self.qty, abs(qty))
            elif operation == 'subtract':
                self.qty = subtract_floats(self.qty, abs(qty))
        else:
            # Existing one-way mode logic
            if self.exchange_type == 'spot':
                # ... existing spot logic ...
            elif self.exchange_type == 'futures':
                # ... existing futures logic ...
```

### 5.3 PositionPair Wrapper

**File**: `jesse/models/PositionPair.py` (NEW)

```python
from typing import Union
import numpy as np
from jesse.models.Position import Position


class PositionPair:
    """
    Wrapper for hedge mode that manages both long and short positions
    for the same symbol.
    """
    
    def __init__(self, exchange_name: str, symbol: str, attributes: dict = None):
        self.exchange_name = exchange_name
        self.symbol = symbol
        self.long_position = Position(exchange_name, symbol, attributes, side='long')
        self.short_position = Position(exchange_name, symbol, attributes, side='short')
    
    def get_position(self, side: str) -> Position:
        """Get position by side"""
        if side == 'long':
            return self.long_position
        elif side == 'short':
            return self.short_position
        else:
            raise ValueError(f"Invalid side: {side}. Must be 'long' or 'short'")
    
    @property
    def net_qty(self) -> float:
        """Net quantity (long qty - short qty)"""
        return self.long_position.qty - self.short_position.qty
    
    @property
    def total_pnl(self) -> float:
        """Combined PNL from both positions"""
        return self.long_position.pnl + self.short_position.pnl
    
    @property
    def total_value(self) -> float:
        """Combined notional value of both positions"""
        return self.long_position.value + self.short_position.value
    
    @property
    def is_both_closed(self) -> bool:
        """Are both positions closed?"""
        return self.long_position.is_close and self.short_position.is_close
    
    @property
    def has_any_open(self) -> bool:
        """Is at least one position open?"""
        return self.long_position.is_open or self.short_position.is_open
    
    @property
    def to_dict(self) -> dict:
        """Export both positions as dict"""
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
        Update positions from WebSocket stream (live trading)
        
        Args:
            data: {
                'long': {...},  # Long position data
                'short': {...}  # Short position data
            }
        """
        if 'long' in data:
            self.long_position.update_from_stream(data['long'], is_initial)
        if 'short' in data:
            self.short_position.update_from_stream(data['short'], is_initial)
```

### 5.4 State Management Updates

**File**: `jesse/store/state_positions.py`

```python
from typing import Union
from jesse.models import Position
from jesse.models.PositionPair import PositionPair
import jesse.helpers as jh


class PositionsState:
    def __init__(self) -> None:
        self.storage = {}
    
    def init_position(self, exchange_name: str, symbol: str, attributes: dict = None) -> None:
        """Initialize position(s) for a symbol"""
        key = jh.key(exchange_name, symbol)
        
        # Check if exchange is in hedge mode
        position_mode = jh.get_config(f'env.exchanges.{exchange_name}.futures_position_mode', 'one-way')
        
        if position_mode == 'hedge':
            # Create position pair
            self.storage[key] = PositionPair(exchange_name, symbol, attributes)
        else:
            # Create single position (existing behavior)
            self.storage[key] = Position(exchange_name, symbol, attributes)
    
    def get_position(
        self, 
        exchange_name: str, 
        symbol: str, 
        side: str = None
    ) -> Union[Position, PositionPair]:
        """
        Get position for symbol
        
        Args:
            exchange_name: Exchange name
            symbol: Trading symbol
            side: In hedge mode: 'long' or 'short'. In one-way mode: ignored
        
        Returns:
            Position object or PositionPair wrapper
        """
        key = jh.key(exchange_name, symbol)
        position_or_pair = self.storage.get(key)
        
        if position_or_pair is None:
            return None
        
        # If it's a PositionPair and side is specified, return specific position
        if isinstance(position_or_pair, PositionPair):
            if side is not None:
                return position_or_pair.get_position(side)
            else:
                # Return the whole pair
                return position_or_pair
        else:
            # One-way mode: return single position
            return position_or_pair
    
    def is_hedge_mode(self, exchange_name: str, symbol: str) -> bool:
        """Check if symbol is in hedge mode"""
        key = jh.key(exchange_name, symbol)
        return isinstance(self.storage.get(key), PositionPair)
```

### 5.5 Broker Class Updates

**File**: `jesse/services/broker.py`

```python
class Broker:
    def __init__(self, position, exchange: str, symbol: str, timeframe: str) -> None:
        self.position = position  # Can be Position or PositionPair
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = exchange
        from jesse.services.api import api
        self.api = api
        
        # NEW: Determine if in hedge mode
        self.is_hedge_mode = jh.get_config(
            f'env.exchanges.{exchange}.futures_position_mode'
        ) == 'hedge'
    
    def buy_at_market(self, qty: float, side: str = None) -> Union[Order, None]:
        """
        Submit market buy order
        
        Args:
            qty: Order quantity
            side: In hedge mode, specify 'long' or 'short'. Ignored in one-way mode.
        """
        self._validate_qty(qty)
        
        if self.is_hedge_mode and side is None:
            raise ValueError(
                "In hedge mode, must specify 'side' parameter ('long' or 'short')"
            )
        
        return self.api.market_order(
            self.exchange,
            self.symbol,
            abs(qty),
            self._get_current_price(side),
            sides.BUY,
            reduce_only=False,
            position_side=side  # NEW parameter
        )
    
    def sell_at_market(self, qty: float, side: str = None) -> Union[Order, None]:
        """
        Submit market sell order
        
        Args:
            qty: Order quantity
            side: In hedge mode, specify 'long' or 'short'. Ignored in one-way mode.
        """
        self._validate_qty(qty)
        
        if self.is_hedge_mode and side is None:
            raise ValueError(
                "In hedge mode, must specify 'side' parameter ('long' or 'short')"
            )
        
        return self.api.market_order(
            self.exchange,
            self.symbol,
            abs(qty),
            self._get_current_price(side),
            sides.SELL,
            reduce_only=False,
            position_side=side  # NEW parameter
        )
    
    def buy_at(self, qty: float, price: float, side: str = None) -> Union[Order, None]:
        """Submit limit buy order"""
        self._validate_qty(qty)
        
        if price < 0:
            raise ValueError('price cannot be negative.')
        
        if self.is_hedge_mode and side is None:
            raise ValueError(
                "In hedge mode, must specify 'side' parameter ('long' or 'short')"
            )
        
        return self.api.limit_order(
            self.exchange,
            self.symbol,
            abs(qty),
            price,
            sides.BUY,
            reduce_only=False,
            position_side=side  # NEW parameter
        )
    
    def sell_at(self, qty: float, price: float, side: str = None) -> Union[Order, None]:
        """Submit limit sell order"""
        self._validate_qty(qty)
        
        if price < 0:
            raise ValueError('price cannot be negative.')
        
        if self.is_hedge_mode and side is None:
            raise ValueError(
                "In hedge mode, must specify 'side' parameter ('long' or 'short')"
            )
        
        return self.api.limit_order(
            self.exchange,
            self.symbol,
            abs(qty),
            price,
            sides.SELL,
            reduce_only=False,
            position_side=side  # NEW parameter
        )
    
    def reduce_position_at(
        self, 
        qty: float, 
        price: float, 
        current_price: float,
        side: str = None
    ) -> Union[Order, None]:
        """
        Reduce position
        
        Args:
            side: In hedge mode, which side to reduce ('long' or 'short')
        """
        self._validate_qty(qty)
        qty = abs(qty)
        
        if price < 0:
            raise ValueError(f'order price cannot be negative. You passed {price}')
        
        if self.is_hedge_mode:
            if side is None:
                raise ValueError("In hedge mode, must specify which side to reduce")
            
            position = self.position.get_position(side)
            if position.is_close:
                raise OrderNotAllowed(
                    f'Cannot submit reduce_position order for {side} when there is no open {side} position'
                )
            
            reduce_side = jh.opposite_side(jh.type_to_side(side))
        else:
            # One-way mode logic (existing)
            if self.position.is_close:
                raise OrderNotAllowed(
                    'Cannot submit a reduce_position order when there is no open position'
                )
            reduce_side = jh.opposite_side(jh.type_to_side(self.position.type))
        
        # MARKET order
        if jh.is_price_near(price, current_price):
            return self.api.market_order(
                self.exchange,
                self.symbol,
                qty,
                price,
                reduce_side,
                reduce_only=True,
                position_side=side
            )
        
        # LIMIT order
        elif (reduce_side == 'sell' and price > current_price) or \
             (reduce_side == 'buy' and price < current_price):
            return self.api.limit_order(
                self.exchange,
                self.symbol,
                qty,
                price,
                reduce_side,
                reduce_only=True,
                position_side=side
            )
        
        # STOP order
        elif (reduce_side == 'sell' and price < current_price) or \
             (reduce_side == 'buy' and price > current_price):
            return self.api.stop_order(
                self.exchange,
                self.symbol,
                abs(qty),
                price,
                reduce_side,
                reduce_only=True,
                position_side=side
            )
        else:
            raise OrderNotAllowed("This order doesn't seem to be for reducing the position.")
    
    def _get_current_price(self, side: str = None) -> float:
        """Get current price for position"""
        if self.is_hedge_mode and side:
            return self.position.get_position(side).current_price
        else:
            return self.position.current_price
```

### 5.6 API Layer Updates

**File**: `jesse/services/api.py`

```python
class API:
    # ... existing code ...
    
    def market_order(
        self,
        exchange: str,
        symbol: str,
        qty: float,
        current_price: float,
        side: str,
        reduce_only: bool,
        position_side: str = None  # NEW
    ) -> Union[Order, None]:
        if exchange not in self.drivers:
            logger.info(f'Exchange "{exchange}" driver not initiated yet. Trying again in the next candle')
            return None
        return self.drivers[exchange].market_order(
            symbol, qty, current_price, side, reduce_only, position_side
        )
    
    def limit_order(
        self,
        exchange: str,
        symbol: str,
        qty: float,
        price: float,
        side: str,
        reduce_only: bool,
        position_side: str = None  # NEW
    ) -> Union[Order, None]:
        if exchange not in self.drivers:
            logger.info(f'Exchange "{exchange}" driver not initiated yet. Trying again in the next candle')
            return None
        return self.drivers[exchange].limit_order(
            symbol, qty, price, side, reduce_only, position_side
        )
    
    def stop_order(
        self,
        exchange: str,
        symbol: str,
        qty: float,
        price: float,
        side: str,
        reduce_only: bool,
        position_side: str = None  # NEW
    ) -> Union[Order, None]:
        if exchange not in self.drivers:
            logger.info(f'Exchange "{exchange}" driver not initiated yet. Trying again in the next candle')
            return None
        return self.drivers[exchange].stop_order(
            symbol, qty, price, side, reduce_only, position_side
        )
```

### 5.7 Exchange Driver Interface Updates

**File**: `jesse/exchanges/exchange.py`

```python
from abc import ABC, abstractmethod
from typing import Union
from jesse.models import Order


class Exchange(ABC):
    """
    The interface that every Exchange driver has to implement
    """
    
    @abstractmethod
    def market_order(
        self, 
        symbol: str, 
        qty: float, 
        current_price: float, 
        side: str, 
        reduce_only: bool,
        position_side: str = None  # NEW
    ) -> Order:
        pass
    
    @abstractmethod
    def limit_order(
        self, 
        symbol: str, 
        qty: float, 
        price: float, 
        side: str, 
        reduce_only: bool,
        position_side: str = None  # NEW
    ) -> Order:
        pass
    
    @abstractmethod
    def stop_order(
        self, 
        symbol: str, 
        qty: float, 
        price: float, 
        side: str, 
        reduce_only: bool,
        position_side: str = None  # NEW
    ) -> Order:
        pass
    
    @abstractmethod
    def cancel_all_orders(self, symbol: str) -> None:
        pass
    
    @abstractmethod
    def cancel_order(self, symbol: str, order_id: str) -> None:
        pass
    
    @abstractmethod
    def _fetch_precisions(self) -> None:
        pass
    
    @abstractmethod
    def set_position_mode(self, symbol: str, mode: str) -> bool:
        """
        Set position mode for symbol (NEW)
        
        Args:
            symbol: Trading symbol
            mode: 'one-way' or 'hedge'
        
        Returns:
            Success status
        """
        pass
```

### 5.8 Sandbox Driver Updates

**File**: `jesse/exchanges/sandbox/Sandbox.py`

```python
class Sandbox(Exchange):
    def __init__(self, name='Sandbox'):
        super().__init__()
        self.name = name
        self.position_modes = {}  # Track position mode per symbol
    
    def market_order(
        self, 
        symbol: str, 
        qty: float, 
        current_price: float, 
        side: str, 
        reduce_only: bool,
        position_side: str = None  # NEW
    ) -> Order:
        order = Order({
            'id': jh.generate_unique_id(),
            'symbol': symbol,
            'exchange': self.name,
            'side': side,
            'type': order_types.MARKET,
            'reduce_only': reduce_only,
            'qty': jh.prepare_qty(qty, side),
            'price': current_price,
            'position_side': position_side,  # NEW
        })
        
        store.orders.add_order(order)
        store.orders.to_execute.append(order)
        
        return order
    
    def limit_order(
        self, 
        symbol: str, 
        qty: float, 
        price: float, 
        side: str, 
        reduce_only: bool,
        position_side: str = None  # NEW
    ) -> Order:
        order = Order({
            'id': jh.generate_unique_id(),
            'symbol': symbol,
            'exchange': self.name,
            'side': side,
            'type': order_types.LIMIT,
            'reduce_only': reduce_only,
            'qty': jh.prepare_qty(qty, side),
            'price': price,
            'position_side': position_side,  # NEW
        })
        
        store.orders.add_order(order)
        
        return order
    
    def stop_order(
        self, 
        symbol: str, 
        qty: float, 
        price: float, 
        side: str, 
        reduce_only: bool,
        position_side: str = None  # NEW
    ) -> Order:
        order = Order({
            'id': jh.generate_unique_id(),
            'symbol': symbol,
            'exchange': self.name,
            'side': side,
            'type': order_types.STOP,
            'reduce_only': reduce_only,
            'qty': jh.prepare_qty(qty, side),
            'price': price,
            'position_side': position_side,  # NEW
        })
        
        store.orders.add_order(order)
        
        return order
    
    def set_position_mode(self, symbol: str, mode: str) -> bool:
        """Set position mode for backtesting"""
        self.position_modes[symbol] = mode
        return True
    
    # ... rest of existing methods ...
```

### 5.9 Order Model Updates

**File**: `jesse/models/Order.py`

```python
class Order:
    def __init__(self, attributes: dict = None) -> None:
        # ... existing attributes ...
        self.position_side = None  # NEW: 'long', 'short', or None
        
        if attributes is None:
            attributes = {}
        
        for a in attributes:
            setattr(self, a, attributes[a])
```

### 5.10 Bybit Live Driver (Separate Repository)

**Note**: This would be in your `jesse_live` module

```python
class BybitDriver(Exchange):
    """Bybit live trading driver"""
    
    def __init__(self, exchange_name: str):
        from pybit.unified_trading import HTTP
        
        self.name = exchange_name
        self.client = HTTP(
            testnet=self.is_testnet,
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        
        # Initialize position mode
        self._sync_position_mode()
    
    def _sync_position_mode(self) -> None:
        """Sync position mode with exchange"""
        mode = jh.get_config(f'env.exchanges.{self.name}.futures_position_mode')
        
        for symbol in self.symbols:
            self.set_position_mode(symbol, mode)
    
    def set_position_mode(self, symbol: str, mode: str) -> bool:
        """
        Set position mode via Bybit API
        
        Bybit API: POST /v5/position/switch-mode
        """
        try:
            # Bybit mode values: 0 = Merged Single, 3 = Both Sides
            bybit_mode = 3 if mode == 'hedge' else 0
            
            response = self.client.set_position_mode(
                category='linear',
                symbol=jh.dashless_symbol(symbol),
                mode=bybit_mode
            )
            
            if response['retCode'] == 0:
                logger.info(f'Set {symbol} to {mode} mode on {self.name}')
                return True
            else:
                logger.error(f'Failed to set position mode: {response["retMsg"]}')
                return False
                
        except Exception as e:
            logger.error(f'Error setting position mode: {str(e)}')
            return False
    
    def market_order(
        self, 
        symbol: str, 
        qty: float, 
        current_price: float, 
        side: str, 
        reduce_only: bool,
        position_side: str = None
    ) -> Order:
        """Submit market order to Bybit"""
        
        # Map position_side to Bybit's positionIdx
        # 0 = one-way mode, 1 = hedge mode buy side, 2 = hedge mode sell side
        position_idx = self._get_position_idx(side, position_side)
        
        try:
            response = self.client.place_order(
                category='linear',
                symbol=jh.dashless_symbol(symbol),
                side=side.capitalize(),
                orderType='Market',
                qty=str(qty),
                positionIdx=position_idx,
                reduceOnly=reduce_only
            )
            
            if response['retCode'] == 0:
                order_data = response['result']
                return Order({
                    'id': order_data['orderId'],
                    'symbol': symbol,
                    'exchange': self.name,
                    'side': side,
                    'type': order_types.MARKET,
                    'qty': qty,
                    'price': current_price,
                    'reduce_only': reduce_only,
                    'position_side': position_side,
                    'status': order_statuses.ACTIVE
                })
            else:
                logger.error(f'Order submission failed: {response["retMsg"]}')
                return None
                
        except Exception as e:
            logger.error(f'Error submitting order: {str(e)}')
            return None
    
    def _get_position_idx(self, side: str, position_side: str = None) -> int:
        """
        Convert side/position_side to Bybit's positionIdx
        
        Returns:
            0 = one-way mode
            1 = hedge mode buy side (long position)
            2 = hedge mode sell side (short position)
        """
        if position_side is None:
            return 0  # One-way mode
        
        # Hedge mode
        if position_side == 'long':
            return 1
        elif position_side == 'short':
            return 2
        else:
            raise ValueError(f'Invalid position_side: {position_side}')
    
    # ... implement limit_order and stop_order similarly ...
```

### 5.11 Strategy API Updates

**File**: `jesse/strategies/Strategy.py`

```python
class Strategy(ABC):
    # ... existing code ...
    
    @property
    def is_hedge_mode(self) -> bool:
        """Check if strategy is using hedge mode"""
        return jh.get_config(
            f'env.exchanges.{self.exchange}.futures_position_mode'
        ) == 'hedge'
    
    @property
    def long_position(self) -> Position:
        """
        Get long position (hedge mode only)
        
        Raises:
            ValueError: If not in hedge mode
        """
        if not self.is_hedge_mode:
            raise ValueError('long_position property only available in hedge mode')
        
        return self.position.long_position
    
    @property
    def short_position(self) -> Position:
        """
        Get short position (hedge mode only)
        
        Raises:
            ValueError: If not in hedge mode
        """
        if not self.is_hedge_mode:
            raise ValueError('short_position property only available in hedge mode')
        
        return self.position.short_position
    
    # Update existing properties to be hedge-mode aware
    @property
    def is_long(self) -> bool:
        """Is in a long position?"""
        if self.is_hedge_mode:
            return self.long_position.is_open
        else:
            return self.position.is_long
    
    @property
    def is_short(self) -> bool:
        """Is in a short position?"""
        if self.is_hedge_mode:
            return self.short_position.is_open
        else:
            return self.position.is_short
    
    # New helper methods for hedge mode
    def go_long_hedge(self) -> None:
        """
        Open/manage long position in hedge mode
        Override this in your strategy
        """
        pass
    
    def go_short_hedge(self) -> None:
        """
        Open/manage short position in hedge mode
        Override this in your strategy
        """
        pass
    
    def should_long_hedge(self) -> bool:
        """
        Should enter/maintain long position? (hedge mode)
        Override this in your strategy
        """
        return False
    
    def should_short_hedge(self) -> bool:
        """
        Should enter/maintain short position? (hedge mode)
        Override this in your strategy
        """
        return False
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

**File**: `tests/test_hedge_mode.py` (NEW)

```python
import pytest
from jesse.strategies import Strategy
from jesse import research
from jesse.factories import candles_from_close_prices
import jesse.helpers as jh


class TestHedgeModePosition(Strategy):
    """Test strategy for hedge mode"""
    
    def should_long_hedge(self):
        return self.index == 2
    
    def should_short_hedge(self):
        return self.index == 4
    
    def go_long_hedge(self):
        qty = 1
        self.buy = qty, self.price, 'long'
    
    def go_short_hedge(self):
        qty = 1
        self.sell = qty, self.price, 'short'
    
    def should_cancel_entry(self):
        return False


def test_hedge_mode_can_hold_both_positions():
    """Test that hedge mode can hold long and short simultaneously"""
    candles = candles_from_close_prices([100, 101, 102, 103, 104, 105, 106])
    
    config = {
        'starting_balance': 10_000,
        'fee': 0,
        'type': 'futures',
        'futures_leverage': 1,
        'futures_leverage_mode': 'cross',
        'futures_position_mode': 'hedge',  # NEW
        'exchange': 'Test Exchange',
        'warm_up_candles': 0
    }
    
    routes = [{
        'exchange': 'Test Exchange',
        'strategy': TestHedgeModePosition,
        'symbol': 'BTC-USDT',
        'timeframe': '1m'
    }]
    
    result = research.backtest(
        config, routes, [], 
        {jh.key('Test Exchange', 'BTC-USDT'): {
            'exchange': 'Test Exchange',
            'symbol': 'BTC-USDT',
            'candles': candles
        }}
    )
    
    # Should have executed both long and short trades
    assert result['metrics']['total'] == 2


def test_hedge_mode_independent_pnl():
    """Test that PNL is calculated independently for each side"""
    # TODO: Implement
    pass


def test_hedge_mode_position_side_required():
    """Test that position_side is required in hedge mode"""
    # TODO: Implement
    pass


def test_one_way_mode_backwards_compatible():
    """Test that one-way mode still works as before"""
    # TODO: Implement
    pass
```

### 6.2 Integration Tests

**File**: `tests/test_hedge_mode_integration.py` (NEW)

```python
def test_hedge_mode_backtest_full_cycle():
    """Test complete backtest cycle with hedge mode"""
    pass


def test_hedge_mode_optimization():
    """Test that optimization works with hedge mode"""
    pass


def test_hedge_mode_metrics_calculation():
    """Test metrics are calculated correctly in hedge mode"""
    pass


def test_hedge_mode_order_execution():
    """Test order execution logic in hedge mode"""
    pass


def test_hedge_mode_position_updates():
    """Test position updates from orders"""
    pass
```

### 6.3 Live Trading Simulation Tests

```python
def test_hedge_mode_websocket_updates():
    """Test position updates from WebSocket in hedge mode"""
    pass


def test_hedge_mode_api_integration():
    """Test Bybit API integration for hedge mode"""
    pass
```

### 6.4 Test Coverage Requirements

- Minimum 90% code coverage for new components
- 100% coverage for critical path (order execution, PNL calculation)
- Integration tests for all three modes (backtest, optimization, live)

---

## 7. Migration & Backwards Compatibility

### 7.1 Backwards Compatibility Strategy

**Key Principle**: Existing strategies MUST continue to work without modification

**Approach**:
1. Default `futures_position_mode` to `'one-way'`
2. All new parameters are optional with sensible defaults
3. Existing Position behavior unchanged when `side=None`
4. New methods/properties clearly named (e.g., `should_long_hedge()`)

### 7.2 Migration Guide for Users

**For Backtest/Optimization**:
```python
# Old config (still works)
config = {
    'futures_leverage_mode': 'cross',
    'futures_leverage': 2
}

# New config for hedge mode
config = {
    'futures_leverage_mode': 'cross',
    'futures_leverage': 2,
    'futures_position_mode': 'hedge'  # Add this line
}
```

**For Strategies**:
```python
# One-way mode (existing, no changes needed)
class MyStrategy(Strategy):
    def should_long(self):
        return self.ema_cross_signal == 'bullish'
    
    def go_long(self):
        self.buy = qty, price


# Hedge mode (new pattern)
class MyHedgeStrategy(Strategy):
    def should_long_hedge(self):
        return self.ema_cross_signal == 'bullish'
    
    def should_short_hedge(self):
        return self.rsi < 30
    
    def go_long_hedge(self):
        self.buy = qty, price, 'long'  # Specify side
    
    def go_short_hedge(self):
        self.sell = qty, price, 'short'  # Specify side
```

### 7.3 Database Migration

If you're storing position data, you'll need to update schema:

```sql
-- Add position_side column
ALTER TABLE positions ADD COLUMN position_side VARCHAR(10) DEFAULT NULL;

-- Update indices
CREATE INDEX idx_positions_side ON positions(exchange, symbol, position_side);
```

---

## 8. Risks & Mitigation

### 8.1 Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Breaking existing strategies | High | Low | Comprehensive backwards compatibility testing |
| PNL calculation errors | High | Medium | Extensive unit tests, cross-validation with exchange data |
| Order routing bugs | High | Medium | Staged rollout, extensive integration testing |
| Performance degradation | Medium | Low | Benchmarking, optimization |
| Exchange API changes | Medium | Low | Version locking, monitoring |

### 8.2 Implementation Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Underestimated complexity | Medium | Medium | Phased approach, buffer time |
| Missing edge cases | Medium | High | Thorough test coverage, beta testing |
| Documentation gaps | Low | Medium | Ongoing documentation updates |

### 8.3 Mitigation Strategies

1. **Feature Flags**: Implement feature flag to enable/disable hedge mode globally
2. **Staged Rollout**: 
   - Week 1-2: Backtest mode only
   - Week 3: Optimization mode
   - Week 4: Live mode (beta)
3. **Beta Testing**: Recruit 3-5 users for beta testing before general release
4. **Monitoring**: Add logging for all hedge mode operations
5. **Rollback Plan**: Maintain ability to revert to one-way mode only

---

## 9. Performance Considerations

### 9.1 Memory Usage

**Impact**: Hedge mode roughly doubles position-related memory usage

**Mitigation**:
- Use `__slots__` in Position class to reduce memory overhead
- Lazy initialization of unused position sides
- Memory profiling during testing

### 9.2 Execution Speed

**Impact**: Additional logic adds ~5-10% overhead to order processing

**Mitigation**:
- Cache position mode lookups
- Optimize hot paths
- Use NumPy operations where possible
- Profile critical sections

### 9.3 Benchmarking Targets

| Metric | Current | Target | Max Acceptable |
|--------|---------|--------|----------------|
| Backtest speed | 100% | 95% | 85% |
| Memory usage | 100% | 110% | 150% |
| Order execution latency | 100% | 105% | 120% |

---

## 10. Future Extensions

### 10.1 Multi-Exchange Hedge Mode

Support hedge mode on other exchanges:
- Binance Futures
- OKX
- Gate.io
- Bitget

### 10.2 Advanced Hedge Strategies

Built-in strategy templates:
- Market-neutral arbitrage
- Statistical arbitrage
- Delta-neutral options hedging
- Cross-symbol hedging

### 10.3 Risk Management Enhancements

- Combined risk limits across both sides
- Net exposure calculations
- Hedge ratio management
- Automated rebalancing

### 10.4 Analytics & Visualization

- Separate charts for long/short positions
- Net position overlay
- Hedge effectiveness metrics
- Risk exposure heatmaps

---

## Appendix A: Code Review Checklist

- [ ] All new code follows PEP 8 style guidelines
- [ ] Type hints added for all function signatures
- [ ] Docstrings added for all public methods
- [ ] Unit tests achieve >90% coverage
- [ ] Integration tests cover all critical paths
- [ ] No breaking changes to existing API
- [ ] Performance benchmarks within acceptable range
- [ ] Error handling for all edge cases
- [ ] Logging added for debugging
- [ ] Documentation updated

## Appendix B: API Changes Summary

### New Configuration Options
```python
'futures_position_mode': 'one-way' | 'hedge'
```

### New Classes
- `PositionPair`: Wrapper for hedge mode positions

### Modified Classes
- `Position`: Add `side` parameter
- `Order`: Add `position_side` attribute
- `Broker`: Add `side` parameter to all methods
- `Strategy`: Add hedge mode methods and properties

### New Methods
- `Exchange.set_position_mode(symbol, mode)`
- `Strategy.should_long_hedge()`
- `Strategy.should_short_hedge()`
- `Strategy.go_long_hedge()`
- `Strategy.go_short_hedge()`

### Modified Method Signatures
All order methods now accept optional `position_side` parameter:
- `market_order(..., position_side=None)`
- `limit_order(..., position_side=None)`
- `stop_order(..., position_side=None)`

---

## Appendix C: Example Strategy

```python
class MarketNeutralHedge(Strategy):
    """
    Example hedge mode strategy that maintains
    market-neutral positions
    """
    
    def hyperparameters(self):
        return [
            {'name': 'long_threshold', 'type': float, 'min': -2, 'max': -0.5, 'default': -1},
            {'name': 'short_threshold', 'type': float, 'min': 0.5, 'max': 2, 'default': 1},
            {'name': 'position_size', 'type': float, 'min': 0.01, 'max': 0.1, 'default': 0.05},
        ]
    
    @property
    def zscore(self):
        """Calculate Z-score of price"""
        prices = self.candles[:, 2]  # close prices
        mean = ta.sma(prices, 20)
        std = ta.stddev(prices, 20)
        return (self.price - mean) / std
    
    def should_long_hedge(self):
        """Enter long when price is oversold"""
        return self.zscore < self.hp['long_threshold']
    
    def should_short_hedge(self):
        """Enter short when price is overbought"""
        return self.zscore > self.hp['short_threshold']
    
    def go_long_hedge(self):
        """Execute long entry"""
        qty = utils.size_to_qty(
            self.capital * self.hp['position_size'],
            self.price,
            fee_rate=self.fee_rate
        )
        
        # In hedge mode, specify side='long'
        self.buy = qty, self.price, 'long'
        self.take_profit = qty, self.price * 1.02, 'long'
        self.stop_loss = qty, self.price * 0.98, 'long'
    
    def go_short_hedge(self):
        """Execute short entry"""
        qty = utils.size_to_qty(
            self.capital * self.hp['position_size'],
            self.price,
            fee_rate=self.fee_rate
        )
        
        # In hedge mode, specify side='short'
        self.sell = qty, self.price, 'short'
        self.take_profit = qty, self.price * 0.98, 'short'
        self.stop_loss = qty, self.price * 1.02, 'short'
    
    def update_position(self):
        """Update positions based on Z-score"""
        # Close long if price has reverted
        if self.long_position.is_open and self.zscore > 0:
            self.liquidate('long')
        
        # Close short if price has reverted
        if self.short_position.is_open and self.zscore < 0:
            self.liquidate('short')
    
    def should_cancel_entry(self):
        return False
```

---

## Questions or Clarifications Needed

1. **Live Driver Access**: Do you have access to modify the `jesse_live` repository, or is it separate?
2. **Testing Resources**: Do you have access to Bybit testnet API keys for testing?
3. **Timeline Flexibility**: Is the 3-4 week timeline acceptable, or do you need it faster/slower?
4. **Scope Adjustments**: Any features you want to add/remove from this plan?
5. **Contribution Strategy**: Will this be a PR to main Jesse repo or maintained as a fork?

---

## Next Steps

1. **Review this document** and provide feedback
2. **Set up development environment** with Bybit testnet credentials
3. **Create feature branch**: `feature/hedge-mode-support`
4. **Begin Phase 1**: Core infrastructure implementation
5. **Daily standups** (optional) to track progress
6. **Weekly demos** to showcase progress

---

**Document Version**: 1.0  
**Last Updated**: 2025-09-30  
**Author**: AI Assistant  
**Review Status**: Draft - Awaiting Approval



