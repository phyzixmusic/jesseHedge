"""
Test state_positions.py with hedge mode support.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_one_way_mode_creates_position():
    """Test that one-way mode creates a single Position object (existing behavior)."""
    from jesse.config import config, reset_config
    from jesse.enums import exchanges
    from jesse.store.state_positions import PositionsState
    from jesse.models.Position import Position
    
    # Setup one-way mode
    reset_config()
    config['env']['exchanges'][exchanges.SANDBOX]['futures_position_mode'] = 'one-way'
    config['app']['trading_exchanges'] = [exchanges.SANDBOX]
    config['app']['trading_symbols'] = ['BTC-USDT']
    
    # Create state
    state = PositionsState()
    
    # Verify it created a Position
    key = f'{exchanges.SANDBOX}-BTC-USDT'
    assert key in state.storage
    position = state.storage[key]
    assert isinstance(position, Position)
    assert not hasattr(position, 'long_position'), "Should be a simple Position, not a PositionPair"
    
    print("✅ One-way mode creates Position object")


def test_hedge_mode_creates_position_pair():
    """Test that hedge mode creates a PositionPair object."""
    from jesse.config import config, reset_config
    from jesse.enums import exchanges
    from jesse.store.state_positions import PositionsState
    from jesse.models.PositionPair import PositionPair
    
    # Setup hedge mode
    reset_config()
    config['env']['exchanges'][exchanges.SANDBOX]['futures_position_mode'] = 'hedge'
    config['app']['trading_exchanges'] = [exchanges.SANDBOX]
    config['app']['trading_symbols'] = ['BTC-USDT']
    
    # Create state
    state = PositionsState()
    
    # Verify it created a PositionPair
    key = f'{exchanges.SANDBOX}-BTC-USDT'
    assert key in state.storage
    position_pair = state.storage[key]
    assert isinstance(position_pair, PositionPair)
    assert hasattr(position_pair, 'long_position')
    assert hasattr(position_pair, 'short_position')
    
    print("✅ Hedge mode creates PositionPair object")


def test_count_open_positions_one_way():
    """Test count_open_positions works with one-way mode."""
    from jesse.config import config, reset_config
    from jesse.enums import exchanges
    from jesse.store.state_positions import PositionsState
    
    # Setup one-way mode
    reset_config()
    config['env']['exchanges'][exchanges.SANDBOX]['futures_position_mode'] = 'one-way'
    config['app']['trading_exchanges'] = [exchanges.SANDBOX]
    config['app']['trading_symbols'] = ['BTC-USDT', 'ETH-USDT']
    
    # Create state
    state = PositionsState()
    
    # Initially no positions open
    assert state.count_open_positions() == 0
    
    # Open one position
    btc_key = f'{exchanges.SANDBOX}-BTC-USDT'
    state.storage[btc_key].qty = 1.0
    assert state.count_open_positions() == 1
    
    # Open second position
    eth_key = f'{exchanges.SANDBOX}-ETH-USDT'
    state.storage[eth_key].qty = 0.5
    assert state.count_open_positions() == 2
    
    # Close one
    state.storage[btc_key].qty = 0
    assert state.count_open_positions() == 1
    
    print("✅ count_open_positions works in one-way mode")


def test_count_open_positions_hedge():
    """Test count_open_positions works with hedge mode."""
    from jesse.config import config, reset_config
    from jesse.enums import exchanges
    from jesse.store.state_positions import PositionsState
    
    # Setup hedge mode
    reset_config()
    config['env']['exchanges'][exchanges.SANDBOX]['futures_position_mode'] = 'hedge'
    config['app']['trading_exchanges'] = [exchanges.SANDBOX]
    config['app']['trading_symbols'] = ['BTC-USDT']
    
    # Create state
    state = PositionsState()
    
    # Initially no positions open
    assert state.count_open_positions() == 0
    
    # Open long position
    btc_key = f'{exchanges.SANDBOX}-BTC-USDT'
    pair = state.storage[btc_key]
    pair.long_position.qty = 1.0
    assert state.count_open_positions() == 1
    
    # Open short position too (still counts as 1 symbol with open position)
    pair.short_position.qty = -0.5
    assert state.count_open_positions() == 1
    
    # Close long, short still open
    pair.long_position.qty = 0
    assert state.count_open_positions() == 1
    
    # Close both
    pair.short_position.qty = 0
    assert state.count_open_positions() == 0
    
    print("✅ count_open_positions works in hedge mode")


if __name__ == '__main__':
    print("Running state_positions hedge mode tests...\n")
    
    try:
        test_one_way_mode_creates_position()
        test_hedge_mode_creates_position_pair()
        test_count_open_positions_one_way()
        test_count_open_positions_hedge()
        
        print("\n✅✅✅ All state_positions tests passed!")
        print("State management is ready for hedge mode!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
