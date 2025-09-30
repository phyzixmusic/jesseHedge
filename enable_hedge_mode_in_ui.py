#!/usr/bin/env python
"""
Enable Hedge Mode in Jesse UI

This script modifies the Jesse database config to enable hedge mode
for all futures exchanges. After running this, the web UI will use
hedge mode automatically (even though the dropdown isn't in the UI yet).

Usage:
    python enable_hedge_mode_in_ui.py
"""

import json
import jesse.helpers as jh


def enable_hedge_mode():
    """Enable hedge mode for all futures exchanges in the database config."""
    from jesse.services.db import database
    from jesse.models.Option import Option
    
    print("="*60)
    print("Enabling Hedge Mode in Jesse UI Configuration")
    print("="*60)
    print()
    
    database.open_connection()
    
    try:
        # Get current config
        o = Option.get(Option.type == 'config')
        config = json.loads(o.json)
        
        print("📋 Current configuration found")
        print()
        
        # Track changes
        changes_made = []
        
        # Update backtest exchanges
        if 'backtest' in config and 'exchanges' in config['backtest']:
            print("🔧 Updating BACKTEST exchanges...")
            for exchange_name in config['backtest']['exchanges']:
                ex = config['backtest']['exchanges'][exchange_name]
                if ex.get('type') == 'futures':
                    old_mode = ex.get('futures_position_mode', 'not set')
                    ex['futures_position_mode'] = 'hedge'
                    print(f"  ✅ {exchange_name}: {old_mode} → hedge")
                    changes_made.append(f"Backtest: {exchange_name}")
        
        # Update live exchanges if present
        if 'live' in config and 'exchanges' in config['live']:
            print()
            print("🔧 Updating LIVE exchanges...")
            for exchange_name in config['live']['exchanges']:
                ex = config['live']['exchanges'][exchange_name]
                if ex.get('type') == 'futures':
                    old_mode = ex.get('futures_position_mode', 'not set')
                    ex['futures_position_mode'] = 'hedge'
                    print(f"  ✅ {exchange_name}: {old_mode} → hedge")
                    changes_made.append(f"Live: {exchange_name}")
        
        if not changes_made:
            print("⚠️  No futures exchanges found in config")
            print("   Nothing to update.")
            database.close_connection()
            return
        
        # Save updated config
        o.json = json.dumps(config)
        o.updated_at = jh.now(True)
        o.save()
        
        database.close_connection()
        
        print()
        print("="*60)
        print("✅✅✅ Hedge Mode Enabled Successfully!")
        print("="*60)
        print()
        print(f"Updated {len(changes_made)} exchange(s):")
        for change in changes_made:
            print(f"  • {change}")
        print()
        print("🎉 You can now use the Jesse web UI normally.")
        print("   All backtests and optimizations will use hedge mode!")
        print()
        print("💡 To revert to one-way mode, change 'hedge' to 'one-way'")
        print("   in the database or re-run this script with a flag.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        database.close_connection()
        return False
    
    return True


def disable_hedge_mode():
    """Disable hedge mode (revert to one-way)."""
    from jesse.services.db import database
    from jesse.models.Option import Option
    
    print("="*60)
    print("Disabling Hedge Mode (Reverting to One-Way)")
    print("="*60)
    print()
    
    database.open_connection()
    
    try:
        o = Option.get(Option.type == 'config')
        config = json.loads(o.json)
        
        changes_made = []
        
        # Update backtest exchanges
        if 'backtest' in config and 'exchanges' in config['backtest']:
            for exchange_name in config['backtest']['exchanges']:
                ex = config['backtest']['exchanges'][exchange_name]
                if ex.get('type') == 'futures' and ex.get('futures_position_mode') == 'hedge':
                    ex['futures_position_mode'] = 'one-way'
                    print(f"  ✅ {exchange_name}: hedge → one-way")
                    changes_made.append(exchange_name)
        
        # Update live exchanges
        if 'live' in config and 'exchanges' in config['live']:
            for exchange_name in config['live']['exchanges']:
                ex = config['live']['exchanges'][exchange_name]
                if ex.get('type') == 'futures' and ex.get('futures_position_mode') == 'hedge':
                    ex['futures_position_mode'] = 'one-way'
                    print(f"  ✅ {exchange_name}: hedge → one-way")
                    changes_made.append(exchange_name)
        
        if changes_made:
            o.json = json.dumps(config)
            o.updated_at = jh.now(True)
            o.save()
            print()
            print(f"✅ Reverted {len(changes_made)} exchange(s) to one-way mode")
        else:
            print("⚠️  No exchanges were in hedge mode")
        
        database.close_connection()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        database.close_connection()
        return False
    
    return True


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--disable':
        disable_hedge_mode()
    elif len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("""
Hedge Mode Configuration Tool
=============================

Enable hedge mode:
    python enable_hedge_mode_in_ui.py

Disable hedge mode (revert to one-way):
    python enable_hedge_mode_in_ui.py --disable

Show this help:
    python enable_hedge_mode_in_ui.py --help

What this does:
  - Modifies the Jesse database configuration
  - Sets futures_position_mode to 'hedge' (or 'one-way' with --disable)
  - Affects all futures exchanges
  - Web UI will use this setting automatically
  - Can be reverted anytime

Note: This is a workaround until the frontend dropdown is added.
        """)
    else:
        enable_hedge_mode()
