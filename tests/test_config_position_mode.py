"""
Simple unit tests for the new futures_position_mode configuration.
These tests don't require full Jesse setup.
"""
import sys
import os

# Add jesse to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_config_has_position_mode_default():
    """Test that default config includes futures_position_mode set to 'one-way'"""
    from jesse import config as jesse_config
    
    # Check sandbox exchange has the new config
    sandbox_config = jesse_config.config['env']['exchanges']['Sandbox']
    
    assert 'futures_position_mode' in sandbox_config, "futures_position_mode should exist in config"
    assert sandbox_config['futures_position_mode'] == 'one-way', "Default should be 'one-way' for backwards compatibility"
    
    print("✅ Config has futures_position_mode with correct default")


def test_all_exchanges_have_position_mode():
    """Test that all exchanges in config have futures_position_mode"""
    from jesse import config as jesse_config
    
    exchanges = jesse_config.config['env']['exchanges']
    
    for exchange_name, exchange_config in exchanges.items():
        if exchange_config['type'] == 'futures':
            assert 'futures_position_mode' in exchange_config, \
                f"{exchange_name} should have futures_position_mode"
            assert exchange_config['futures_position_mode'] in ['one-way', 'hedge'], \
                f"{exchange_name} position mode should be 'one-way' or 'hedge'"
    
    print(f"✅ All {len(exchanges)} exchanges have futures_position_mode configured")


def test_set_config_handles_position_mode():
    """Test that set_config properly handles futures_position_mode"""
    from jesse import config as jesse_config
    
    # Simulate config input
    test_config = {
        'warm_up_candles': 100,
        'logging': {
            'order_submission': True,
            'order_execution': True,
        },
        'exchanges': {
            0: {
                'name': 'Sandbox',
                'fee': 0,
                'type': 'futures',
                'balance': 10000,
                'futures_leverage': 2,
                'futures_leverage_mode': 'cross',
                'futures_position_mode': 'hedge'  # Test new config
            }
        }
    }
    
    # Need to set trading mode
    jesse_config.config['app']['trading_mode'] = 'backtest'
    
    # Apply config
    jesse_config.set_config(test_config)
    
    # Verify it was applied
    result_config = jesse_config.config['env']['exchanges']['Sandbox']
    assert result_config['futures_position_mode'] == 'hedge', \
        "set_config should apply futures_position_mode"
    
    print("✅ set_config handles futures_position_mode correctly")


if __name__ == '__main__':
    print("Running configuration tests...\n")
    
    try:
        test_config_has_position_mode_default()
        test_all_exchanges_have_position_mode()
        test_set_config_handles_position_mode()
        
        print("\n✅✅✅ All configuration tests passed!")
        print("Configuration is ready. Safe to proceed with Position model changes.")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



