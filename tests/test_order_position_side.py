"""
Test Order model with position_side attribute for hedge mode.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_order_without_position_side():
    """Test that Order can be created without position_side (one-way mode)."""
    from jesse.testing_utils import set_up
    set_up()
    
    from jesse.models.Order import Order
    from jesse.enums import order_types, sides
    
    # Create order without position_side (existing behavior)
    order_data = {
        'id': 'test-order-1',
        'symbol': 'BTC-USDT',
        'exchange': 'Sandbox',
        'side': sides.BUY,
        'type': order_types.MARKET,
        'qty': 1.0,
        'price': 50000,
        'reduce_only': False
    }
    
    order = Order(order_data, should_silent=True)
    
    # Verify order was created
    assert order.symbol == 'BTC-USDT'
    assert order.side == sides.BUY
    assert order.qty == 1.0
    
    # position_side should be None (or not set) for one-way mode
    assert not hasattr(order, 'position_side') or order.position_side is None
    
    print("✅ Order without position_side works (backwards compatible)")


def test_order_with_position_side_long():
    """Test that Order can be created with position_side='long' for hedge mode."""
    from jesse.testing_utils import set_up
    set_up()
    
    from jesse.models.Order import Order
    from jesse.enums import order_types, sides
    
    # Create order with position_side='long'
    order_data = {
        'id': 'test-order-2',
        'symbol': 'BTC-USDT',
        'exchange': 'Sandbox',
        'side': sides.BUY,
        'type': order_types.MARKET,
        'qty': 1.0,
        'price': 50000,
        'reduce_only': False,
        'position_side': 'long'  # NEW for hedge mode
    }
    
    order = Order(order_data, should_silent=True)
    
    # Verify order has position_side
    assert order.position_side == 'long'
    assert order.symbol == 'BTC-USDT'
    assert order.qty == 1.0
    
    print("✅ Order with position_side='long' works")


def test_order_with_position_side_short():
    """Test that Order can be created with position_side='short' for hedge mode."""
    from jesse.testing_utils import set_up
    set_up()
    
    from jesse.models.Order import Order
    from jesse.enums import order_types, sides
    
    # Create order with position_side='short'
    order_data = {
        'id': 'test-order-3',
        'symbol': 'BTC-USDT',
        'exchange': 'Sandbox',
        'side': sides.SELL,
        'type': order_types.MARKET,
        'qty': 1.0,
        'price': 50000,
        'reduce_only': False,
        'position_side': 'short'  # NEW for hedge mode
    }
    
    order = Order(order_data, should_silent=True)
    
    # Verify order has position_side
    assert order.position_side == 'short'
    assert order.symbol == 'BTC-USDT'
    assert order.qty == 1.0
    
    print("✅ Order with position_side='short' works")


def test_order_side_vs_position_side():
    """
    Clarify the difference between 'side' and 'position_side':
    - side: BUY or SELL (order action)
    - position_side: long or short (which position in hedge mode)
    """
    from jesse.testing_utils import set_up
    set_up()
    
    from jesse.models.Order import Order
    from jesse.enums import order_types, sides
    
    # In hedge mode, you can:
    # 1. BUY to open/increase long position
    long_open_order = Order({
        'id': 'test-order-4',
        'symbol': 'BTC-USDT',
        'exchange': 'Sandbox',
        'side': sides.BUY,  # Action: buying
        'type': order_types.MARKET,
        'qty': 1.0,
        'price': 50000,
        'reduce_only': False,
        'position_side': 'long'  # Target: long position
    }, should_silent=True)
    
    assert long_open_order.side == sides.BUY
    assert long_open_order.position_side == 'long'
    
    # 2. SELL to open/increase short position
    short_open_order = Order({
        'id': 'test-order-5',
        'symbol': 'BTC-USDT',
        'exchange': 'Sandbox',
        'side': sides.SELL,  # Action: selling
        'type': order_types.MARKET,
        'qty': 1.0,
        'price': 50000,
        'reduce_only': False,
        'position_side': 'short'  # Target: short position
    }, should_silent=True)
    
    assert short_open_order.side == sides.SELL
    assert short_open_order.position_side == 'short'
    
    # 3. SELL to close long position (reduce)
    long_close_order = Order({
        'id': 'test-order-6',
        'symbol': 'BTC-USDT',
        'exchange': 'Sandbox',
        'side': sides.SELL,  # Action: selling
        'type': order_types.MARKET,
        'qty': 1.0,
        'price': 50000,
        'reduce_only': True,
        'position_side': 'long'  # Target: long position (to close it)
    }, should_silent=True)
    
    assert long_close_order.side == sides.SELL
    assert long_close_order.position_side == 'long'
    assert long_close_order.reduce_only is True
    
    print("✅ side vs position_side distinction is clear")


if __name__ == '__main__':
    print("Running Order model position_side tests...\n")
    
    try:
        test_order_without_position_side()
        test_order_with_position_side_long()
        test_order_with_position_side_short()
        test_order_side_vs_position_side()
        
        print("\n✅✅✅ All Order model tests passed!")
        print("Order model is ready for hedge mode routing.")
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
