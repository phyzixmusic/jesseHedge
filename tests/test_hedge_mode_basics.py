"""
Tests for hedge mode implementation.

This file contains both regression tests (to ensure one-way mode still works)
and new tests for hedge mode functionality.
"""
import pytest
import jesse.helpers as jh
from jesse.factories import candles_from_close_prices
from jesse.strategies import Strategy
from jesse import research


# ============================================================================
# REGRESSION TESTS - Ensure existing one-way mode still works
# ============================================================================

class SimpleOneWayStrategy(Strategy):
    """Basic strategy for testing one-way mode (existing behavior)"""
    
    def should_long(self):
        return self.index == 2
    
    def should_short(self):
        return False
    
    def go_long(self):
        qty = 1
        self.buy = qty, self.price
    
    def should_cancel_entry(self):
        return False
    
    def go_short(self):
        pass


def test_one_way_mode_still_works():
    """
    REGRESSION TEST: Verify existing one-way mode behavior is unchanged.
    This must pass before we implement any hedge mode features.
    """
    candles = candles_from_close_prices([100, 101, 102, 103, 104, 105])
    
    config = {
        'starting_balance': 10_000,
        'fee': 0,
        'type': 'futures',
        'futures_leverage': 1,
        'futures_leverage_mode': 'cross',
        'exchange': 'Test Exchange',
        'warm_up_candles': 0
    }
    
    routes = [{
        'exchange': 'Test Exchange',
        'strategy': SimpleOneWayStrategy,
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
    
    # Should execute one long trade
    assert result['metrics']['total'] >= 1
    print("✅ One-way mode regression test passed")


def test_one_way_mode_position_behavior():
    """
    REGRESSION TEST: Verify position opens and closes correctly in one-way mode.
    """
    class TestPositionBehavior(Strategy):
        def before(self):
            if self.index == 3:
                # After opening position, verify it's open
                assert self.is_long
                assert not self.is_short
                assert self.position.is_open
        
        def should_long(self):
            return self.index == 2
        
        def go_long(self):
            self.buy = 1, self.price
        
        def should_cancel_entry(self):
            return False
    
    candles = candles_from_close_prices([100, 101, 102, 103, 104, 105])
    
    config = {
        'starting_balance': 10_000,
        'fee': 0,
        'type': 'futures',
        'futures_leverage': 1,
        'futures_leverage_mode': 'cross',
        'exchange': 'Test Exchange',
        'warm_up_candles': 0
    }
    
    routes = [{
        'exchange': 'Test Exchange',
        'strategy': TestPositionBehavior,
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
    
    print("✅ One-way position behavior test passed")


def test_one_way_mode_with_isolated_margin():
    """
    REGRESSION TEST: Ensure isolated margin mode still works.
    """
    candles = candles_from_close_prices([100, 101, 102, 103, 104, 105])
    
    config = {
        'starting_balance': 10_000,
        'fee': 0,
        'type': 'futures',
        'futures_leverage': 2,
        'futures_leverage_mode': 'isolated',  # Test isolated mode
        'exchange': 'Test Exchange',
        'warm_up_candles': 0
    }
    
    routes = [{
        'exchange': 'Test Exchange',
        'strategy': SimpleOneWayStrategy,
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
    
    assert result['metrics']['total'] >= 1
    print("✅ Isolated margin regression test passed")


# ============================================================================
# NEW TESTS - Hedge mode functionality (will be implemented incrementally)
# ============================================================================

@pytest.mark.skip(reason="Hedge mode not yet implemented")
def test_hedge_mode_config_option():
    """
    Test that futures_position_mode config option is recognized.
    Will be implemented in Phase 1.
    """
    candles = candles_from_close_prices([100, 101, 102, 103, 104, 105])
    
    config = {
        'starting_balance': 10_000,
        'fee': 0,
        'type': 'futures',
        'futures_leverage': 1,
        'futures_leverage_mode': 'cross',
        'futures_position_mode': 'hedge',  # NEW config option
        'exchange': 'Test Exchange',
        'warm_up_candles': 0
    }
    
    routes = [{
        'exchange': 'Test Exchange',
        'strategy': SimpleOneWayStrategy,
        'symbol': 'BTC-USDT',
        'timeframe': '1m'
    }]
    
    # Should not crash when hedge mode is configured
    result = research.backtest(
        config, routes, [], 
        {jh.key('Test Exchange', 'BTC-USDT'): {
            'exchange': 'Test Exchange',
            'symbol': 'BTC-USDT',
            'candles': candles
        }}
    )
    
    assert result is not None


@pytest.mark.skip(reason="Hedge mode not yet implemented")
def test_hedge_mode_can_hold_both_positions():
    """
    Test that hedge mode can hold long and short positions simultaneously.
    Will be implemented after core infrastructure is ready.
    """
    class TestHedgeStrategy(Strategy):
        def should_long_hedge(self):
            return self.index == 2
        
        def should_short_hedge(self):
            return self.index == 3
        
        def go_long_hedge(self):
            self.buy = 1, self.price, 'long'
        
        def go_short_hedge(self):
            self.sell = 1, self.price, 'short'
        
        def should_cancel_entry(self):
            return False
    
    candles = candles_from_close_prices([100, 101, 102, 103, 104, 105, 106])
    
    config = {
        'starting_balance': 10_000,
        'fee': 0,
        'type': 'futures',
        'futures_leverage': 1,
        'futures_leverage_mode': 'cross',
        'futures_position_mode': 'hedge',
        'exchange': 'Test Exchange',
        'warm_up_candles': 0
    }
    
    routes = [{
        'exchange': 'Test Exchange',
        'strategy': TestHedgeStrategy,
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
    
    # Should have opened both positions
    assert result['metrics']['total'] == 2


if __name__ == '__main__':
    # Run regression tests
    print("Running regression tests to ensure existing functionality works...\n")
    test_one_way_mode_still_works()
    test_one_way_mode_position_behavior()
    test_one_way_mode_with_isolated_margin()
    print("\n✅ All regression tests passed! Safe to proceed with hedge mode implementation.")



