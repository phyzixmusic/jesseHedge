"""
Unit tests for Position model with optional side parameter.
Tests both one-way mode (side=None) and hedge mode (side='long'/'short').
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_position_without_side_backwards_compatible():
    """
    REGRESSION TEST: Position can be created without side parameter (one-way mode).
    This is the existing behavior and must continue to work.
    """
    from jesse.models.Position import Position
    
    # Create position the old way (no side parameter)
    position = Position('Test Exchange', 'BTC-USDT')
    
    # Verify attributes
    assert position.exchange_name == 'Test Exchange'
    assert position.symbol == 'BTC-USDT'
    assert position.side is None, "side should be None for one-way mode"
    assert position.is_hedge_mode is False, "is_hedge_mode should be False when side is None"
    assert position.qty == 0
    
    print("✅ Position without side parameter works (backwards compatible)")


def test_position_with_long_side():
    """
    NEW: Position can be created with side='long' for hedge mode.
    """
    from jesse.models.Position import Position
    
    # Create position with side='long'
    position = Position('Test Exchange', 'BTC-USDT', side='long')
    
    # Verify attributes
    assert position.exchange_name == 'Test Exchange'
    assert position.symbol == 'BTC-USDT'
    assert position.side == 'long', "side should be 'long'"
    assert position.is_hedge_mode is True, "is_hedge_mode should be True when side is specified"
    assert position.qty == 0
    
    print("✅ Position with side='long' works")


def test_position_with_short_side():
    """
    NEW: Position can be created with side='short' for hedge mode.
    """
    from jesse.models.Position import Position
    
    # Create position with side='short'
    position = Position('Test Exchange', 'BTC-USDT', side='short')
    
    # Verify attributes
    assert position.exchange_name == 'Test Exchange'
    assert position.symbol == 'BTC-USDT'
    assert position.side == 'short', "side should be 'short'"
    assert position.is_hedge_mode is True, "is_hedge_mode should be True when side is specified"
    assert position.qty == 0
    
    print("✅ Position with side='short' works")


def test_position_with_attributes_and_side():
    """
    Test that attributes dict still works when side is also provided.
    """
    from jesse.models.Position import Position
    
    # Create position with both attributes and side
    attributes = {
        'entry_price': 50000.0,
        'qty': 1.5
    }
    position = Position('Test Exchange', 'BTC-USDT', attributes=attributes, side='long')
    
    # Verify both attributes and side are set
    assert position.side == 'long'
    assert position.entry_price == 50000.0
    assert position.qty == 1.5
    assert position.is_hedge_mode is True
    
    print("✅ Position with both attributes and side works")


def test_two_positions_same_symbol_different_sides():
    """
    Test that we can create two Position objects for the same symbol with different sides.
    This is the foundation for hedge mode.
    """
    from jesse.models.Position import Position
    
    # Create long position
    long_position = Position('Test Exchange', 'BTC-USDT', side='long')
    
    # Create short position for same symbol
    short_position = Position('Test Exchange', 'BTC-USDT', side='short')
    
    # Verify they're independent
    assert long_position.side == 'long'
    assert short_position.side == 'short'
    assert long_position.id != short_position.id, "Each position should have unique ID"
    assert long_position.is_hedge_mode is True
    assert short_position.is_hedge_mode is True
    
    # They can have different quantities
    long_position.qty = 1.0
    short_position.qty = 0.5
    assert long_position.qty == 1.0
    assert short_position.qty == 0.5
    
    print("✅ Two positions with different sides can coexist")


if __name__ == '__main__':
    print("Running Position model unit tests...\n")
    
    try:
        test_position_without_side_backwards_compatible()
        test_position_with_long_side()
        test_position_with_short_side()
        test_position_with_attributes_and_side()
        test_two_positions_same_symbol_different_sides()
        
        print("\n✅✅✅ All Position model tests passed!")
        print("Position model is ready for hedge mode. Safe to proceed.")
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
