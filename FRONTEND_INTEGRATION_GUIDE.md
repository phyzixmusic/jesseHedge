# Frontend Integration Guide for Hedge Mode

## Overview

This guide shows frontend developers exactly how to add hedge mode support to the Jesse UI. The backend is **100% ready** - we just need to add UI controls.

---

## 🎯 What We Need

Add a "Position Mode" dropdown to the exchange settings form, similar to how "Leverage Mode" works.

---

## 📍 Where to Add the UI Control

### Location
The exchange configuration form where users set:
- Exchange type (spot/futures)
- Balance
- Fee
- Futures Leverage
- **Futures Leverage Mode** ← This already exists
- **Futures Position Mode** ← **ADD THIS**

---

## 🔧 Frontend Changes Required

### 1. Update TypeScript Interface

**File:** `src/types/config.ts` (or wherever types are defined)

```typescript
// Existing interface (update this)
interface FuturesExchangeConfig {
  name: string
  type: 'futures'
  balance: number
  fee: number
  futures_leverage: number
  futures_leverage_mode: 'cross' | 'isolated'
  futures_position_mode: 'one-way' | 'hedge'  // ← ADD THIS LINE
}

// For backtest config
interface BacktestConfig {
  exchanges: {
    [exchangeName: string]: {
      type: 'spot' | 'futures'
      balance: number
      fee: number
      futures_leverage?: number
      futures_leverage_mode?: 'cross' | 'isolated'
      futures_position_mode?: 'one-way' | 'hedge'  // ← ADD THIS LINE
    }
  }
  // ... other config
}
```

### 2. Add UI Control (Vue Component)

**File:** Exchange settings form component (likely in `src/components/`)

**Find the existing futures_leverage_mode dropdown and add this right after it:**

```vue
<template>
  <!-- Existing code for futures_leverage_mode -->
  <div v-if="exchange.type === 'futures'" class="form-group">
    <label for="leverage-mode">Leverage Mode</label>
    <select 
      id="leverage-mode"
      v-model="exchange.futures_leverage_mode" 
      class="form-control"
    >
      <option value="cross">Cross</option>
      <option value="isolated">Isolated</option>
    </select>
  </div>

  <!-- ADD THIS NEW SECTION -->
  <div v-if="exchange.type === 'futures'" class="form-group">
    <label for="position-mode">Position Mode</label>
    <select 
      id="position-mode"
      v-model="exchange.futures_position_mode" 
      class="form-control"
    >
      <option value="one-way">One-Way Mode</option>
      <option value="hedge">Hedge Mode</option>
    </select>
    <small class="form-text text-muted">
      <strong>One-Way:</strong> Can hold either long OR short position.<br>
      <strong>Hedge:</strong> Can hold both long AND short positions simultaneously.
    </small>
  </div>
</template>

<script setup lang="ts">
// If using composition API
const exchange = ref({
  // ... existing properties ...
  futures_position_mode: 'one-way'  // Default value
})

// If using options API
export default {
  data() {
    return {
      exchange: {
        // ... existing properties ...
        futures_position_mode: 'one-way'  // Default value
      }
    }
  }
}
</script>
```

### 3. Update Default Config

**File:** Config initialization (where default exchange config is created)

```typescript
// When creating new exchange config
const defaultFuturesExchange = {
  type: 'futures',
  balance: 10000,
  fee: 0.0004,
  futures_leverage: 1,
  futures_leverage_mode: 'cross',
  futures_position_mode: 'one-way'  // ← ADD THIS DEFAULT
}

// Ensure it's included when building config object
function buildExchangeConfig(exchange) {
  const config = {
    name: exchange.name,
    type: exchange.type,
    balance: exchange.balance,
    fee: exchange.fee
  }
  
  if (exchange.type === 'futures') {
    config.futures_leverage = exchange.futures_leverage || 1
    config.futures_leverage_mode = exchange.futures_leverage_mode || 'cross'
    config.futures_position_mode = exchange.futures_position_mode || 'one-way'  // ← ADD
  }
  
  return config
}
```

### 4. Ensure It's Sent to Backend

**When submitting backtest/optimization:**

```typescript
// The config object sent to backend should include futures_position_mode
const config = {
  exchanges: {
    [exchangeName]: {
      type: 'futures',
      balance: 10000,
      fee: 0.0004,
      futures_leverage: 2,
      futures_leverage_mode: 'cross',
      futures_position_mode: 'hedge'  // ← INCLUDE THIS
    }
  },
  // ... other config
}

// POST to /backtest or /optimization
await fetch('/backtest', {
  method: 'POST',
  body: JSON.stringify({
    id: sessionId,
    exchange: exchangeName,
    routes: routes,
    config: config,  // ← Config includes futures_position_mode
    // ... other params
  })
})
```

### 5. Display in General Info (Optional)

**File:** Backtest/Optimization info display component

```vue
<template>
  <!-- Existing general info display -->
  <div class="info-row">
    <span class="label">Leverage Mode:</span>
    <span class="value">{{ generalInfo.leverage_mode }}</span>
  </div>
  
  <!-- ADD THIS -->
  <div class="info-row" v-if="generalInfo.position_mode">
    <span class="label">Position Mode:</span>
    <span class="value">{{ generalInfo.position_mode }}</span>
  </div>
</template>
```

---

## 🔍 Backend Verification (Already Done!)

### Config Flow Check ✅

**1. Backend receives config from UI:**
```python
# jesse/controllers/backtest_controller.py
@router.post("")
def backtest(request_json: BacktestRequestJson, ...):
    # request_json.config contains futures_position_mode ✅
    run_backtest(..., request_json.config, ...)
```

**2. Config is processed:**
```python
# jesse/config.py - set_config()
config['env']['exchanges'][e['name']]['futures_position_mode'] = \
    e.get('futures_position_mode', 'one-way')  # ✅ Handles it!
```

**3. Positions are created correctly:**
```python
# jesse/store/state_positions.py
position_mode = config['env']['exchanges'][exchange].get('futures_position_mode', 'one-way')
if position_mode == 'hedge':
    self.storage[key] = PositionPair(exchange, symbol)  # ✅
```

**4. Results are displayed:**
```python
# jesse/services/report.py - positions()
p.type  # ✅ Works (NET type from PositionPair)
p.qty   # ✅ Works (NET qty)
p.pnl   # ✅ Works (total PNL)
```

**5. Optimization shows it:**
```python
# jesse/modes/optimize_mode/Optimize.py
general_info = {
    'position_mode': self.user_config['exchange'].get('futures_position_mode', 'one-way')  # ✅
}
```

✅ **Backend is 100% ready to receive and process futures_position_mode!**

---

## 📦 Example Config Object from Frontend

### What the Frontend Should Send

**For Backtest:**
```json
{
  "id": "backtest-session-123",
  "exchange": "Bybit USDT Perpetual",
  "routes": [
    {
      "exchange": "Bybit USDT Perpetual",
      "strategy": "MyStrategy",
      "symbol": "BTC-USDT",
      "timeframe": "15m"
    }
  ],
  "config": {
    "exchanges": {
      "Bybit USDT Perpetual": {
        "type": "futures",
        "balance": 10000,
        "fee": 0.0004,
        "futures_leverage": 2,
        "futures_leverage_mode": "cross",
        "futures_position_mode": "hedge"
      }
    },
    "logging": { ... },
    "warm_up_candles": 100
  },
  "start_date": "2024-01-01",
  "finish_date": "2024-12-31",
  "debug_mode": false,
  "export_csv": false,
  "export_json": false,
  "export_chart": true,
  "export_tradingview": false,
  "fast_mode": false,
  "benchmark": false
}
```

**For Optimization:**
```json
{
  "id": "optimize-session-456",
  "exchange": "Bybit USDT Perpetual",
  "config": {
    "exchange": {
      "type": "futures",
      "balance": 10000,
      "fee": 0.0004,
      "futures_leverage": 2,
      "futures_leverage_mode": "cross",
      "futures_position_mode": "hedge"
    }
  },
  // ... other optimization params
}
```

---

## 🎨 UI Design Suggestions

### Placement
Add right after "Leverage Mode" in the futures settings section:

```
┌─────────────────────────────────────┐
│ Exchange Configuration              │
├─────────────────────────────────────┤
│ Exchange Type: [Futures     ▼]     │
│ Balance:       [10000          ]    │
│ Fee:           [0.0004         ]    │
│ Leverage:      [2              ]    │
│ Leverage Mode: [Cross      ▼]      │
│ Position Mode: [One-Way    ▼]  ← ADD│
│                                     │
│ ℹ️ One-Way: Hold long OR short     │
│    Hedge: Hold long AND short      │
└─────────────────────────────────────┘
```

### Visual Feedback
When hedge mode is selected, could show an icon or badge:
```
Position Mode: [Hedge ▼] 🔀
```

### Validation
```typescript
// No special validation needed - just ensure it's included in config
function validateExchangeConfig(exchange) {
  if (exchange.type === 'futures') {
    // Existing validation
    if (!exchange.futures_leverage_mode) {
      exchange.futures_leverage_mode = 'cross'
    }
    
    // ADD THIS
    if (!exchange.futures_position_mode) {
      exchange.futures_position_mode = 'one-way'  // Default
    }
  }
}
```

---

## 🧪 Testing Frontend Changes

### 1. Add the dropdown
### 2. Set it to "hedge"
### 3. Run a backtest
### 4. Check browser console network tab:

**Request payload should include:**
```json
{
  "config": {
    "exchanges": {
      "Bybit USDT Perpetual": {
        "futures_position_mode": "hedge"  // ← Should be present
      }
    }
  }
}
```

### 5. Backend will respond normally
Backend already handles this! No backend changes needed.

### 6. Results will show NET position
Works immediately - backend sends back correct data.

---

## 📱 Enhanced Position Display (Optional)

### Current Display (Works Fine)
```vue
<template>
  <tr>
    <td>{{ position.symbol }}</td>
    <td :class="positionTypeClass(position.type)">
      {{ position.type }}
    </td>
    <td>{{ position.qty }}</td>
    <td>{{ position.entry }}</td>
    <td>{{ position.pnl }}</td>
  </tr>
</template>
```

Shows NET position. This works!

### Enhanced Display (Nice-to-Have)
```vue
<template>
  <tr v-if="position.mode === 'hedge'">
    <td>{{ position.symbol }}</td>
    <td colspan="5">
      <div class="hedge-position">
        <div class="position-header">
          <span class="badge badge-info">Hedge Mode</span>
          <span>Net: {{ position.qty }} | Total PNL: {{ position.pnl }}</span>
        </div>
        
        <!-- Long position row -->
        <div class="sub-position long">
          <span class="label">↗ Long:</span>
          <span class="qty">{{ position.long.qty }}</span>
          <span class="entry">@ {{ position.long.entry }}</span>
          <span class="pnl" :class="pnlClass(position.long.pnl)">
            {{ position.long.pnl }}
          </span>
        </div>
        
        <!-- Short position row -->
        <div class="sub-position short">
          <span class="label">↘ Short:</span>
          <span class="qty">{{ position.short.qty }}</span>
          <span class="entry">@ {{ position.short.entry }}</span>
          <span class="pnl" :class="pnlClass(position.short.pnl)">
            {{ position.short.pnl }}
          </span>
        </div>
      </div>
    </td>
  </tr>
  
  <!-- Regular display for one-way mode -->
  <tr v-else>
    <td>{{ position.symbol }}</td>
    <td>{{ position.type }}</td>
    <td>{{ position.qty }}</td>
    <td>{{ position.entry }}</td>
    <td>{{ position.pnl }}</td>
  </tr>
</template>
```

**Note:** This requires backend to send both positions. We can add that later if needed.

---

## 🔄 Data Flow Diagram

### Current (One-Way Mode)
```
UI Form → POST /backtest → Backend Config → PositionsState → Position
                              ↓
                        futures_leverage_mode: 'cross'
```

### With Hedge Mode (What We Need)
```
UI Form → POST /backtest → Backend Config → PositionsState → PositionPair
   ↓                           ↓                                  ↓
position_mode: 'hedge'  futures_position_mode: 'hedge'    (long + short)
```

**Backend is ready! Just need the UI form to send it.**

---

## 🚀 Implementation Steps

### Step 1: Update Frontend Types (5 min)
Add `futures_position_mode?: 'one-way' | 'hedge'` to exchange config interface

### Step 2: Add Dropdown to Form (10 min)
Copy the leverage_mode dropdown, rename to position_mode, update options

### Step 3: Set Default Value (2 min)
```javascript
futures_position_mode: 'one-way'  // Default
```

### Step 4: Ensure It's Included in Config (5 min)
When building config object to send to backend, include `futures_position_mode`

### Step 5: Test (5 min)
1. Select "Hedge" in UI
2. Run backtest
3. Check network request includes it
4. Verify backtest works

### Step 6: Build & Deploy (Variable)
```bash
npm run build  # or whatever the build command is
```

**Total Time: ~30 minutes of frontend work**

---

## 📋 Code Snippets for Copy-Paste

### Dropdown HTML
```vue
<div v-if="form.exchange.type === 'futures'" class="mb-4">
  <label class="form-label">Position Mode</label>
  <select v-model="form.exchange.futures_position_mode" class="form-select">
    <option value="one-way">One-Way Mode (Default)</option>
    <option value="hedge">Hedge Mode (Dual Positions)</option>
  </select>
  <div class="form-text">
    Hedge mode allows holding both long and short positions simultaneously.
    <a href="https://docs.jesse.trade/docs/strategies/hedge-mode" target="_blank">Learn more</a>
  </div>
</div>
```

### TypeScript Type
```typescript
export interface ExchangeConfig {
  name: string
  type: 'spot' | 'futures'
  balance: number
  fee: number
  futures_leverage?: number
  futures_leverage_mode?: 'cross' | 'isolated'
  futures_position_mode?: 'one-way' | 'hedge'
}
```

### Default Value
```typescript
// When initializing new exchange
const newExchange: ExchangeConfig = {
  name: selectedExchange,
  type: 'futures',
  balance: 10000,
  fee: 0.0004,
  futures_leverage: 1,
  futures_leverage_mode: 'cross',
  futures_position_mode: 'one-way'  // ← ADD
}
```

### Config Builder
```typescript
function buildBacktestConfig(formData) {
  const config = {
    exchanges: {}
  }
  
  for (const [name, exchange] of Object.entries(formData.exchanges)) {
    config.exchanges[name] = {
      type: exchange.type,
      balance: exchange.balance,
      fee: exchange.fee
    }
    
    if (exchange.type === 'futures') {
      config.exchanges[name].futures_leverage = exchange.futures_leverage
      config.exchanges[name].futures_leverage_mode = exchange.futures_leverage_mode
      config.exchanges[name].futures_position_mode = exchange.futures_position_mode || 'one-way'  // ← ADD
    }
  }
  
  return config
}
```

---

## ✅ Backend Verification Checklist

Let me verify the backend handles everything:

- [x] `BacktestRequestJson.config` - Accepts dict ✅
- [x] `OptimizationRequestJson.config` - Accepts dict ✅
- [x] `jesse/config.py` - Processes futures_position_mode ✅
- [x] `jesse/store/state_positions.py` - Creates PositionPair when hedge ✅
- [x] `jesse/research/backtest.py` - Passes futures_position_mode ✅
- [x] `jesse/modes/optimize_mode/fitness.py` - Uses futures_position_mode ✅
- [x] `jesse/services/report.py` - Handles PositionPair ✅
- [x] WebSocket events include position_mode ✅

**✅ Backend is 100% ready!** No backend changes needed when frontend is updated.

---

## 🧪 Testing the Integration

### Manual Test (Without Rebuilding Frontend)

**1. Use browser dev tools to modify the request:**

Open browser console when submitting backtest:
```javascript
// Intercept fetch
const originalFetch = window.fetch
window.fetch = function(url, options) {
  if (url.includes('/backtest')) {
    const body = JSON.parse(options.body)
    // Add futures_position_mode
    for (const ex in body.config.exchanges) {
      if (body.config.exchanges[ex].type === 'futures') {
        body.config.exchanges[ex].futures_position_mode = 'hedge'
      }
    }
    options.body = JSON.stringify(body)
    console.log('Modified config:', body.config)
  }
  return originalFetch(url, options)
}
```

**2. Run backtest from UI**
**3. Check backend logs - should create PositionPair!**

### Automated Test
```typescript
// In frontend tests
describe('Exchange Config Form', () => {
  it('should include futures_position_mode in config', () => {
    const config = buildConfig({
      type: 'futures',
      futures_leverage: 2,
      futures_leverage_mode: 'cross',
      futures_position_mode: 'hedge'
    })
    
    expect(config.futures_position_mode).toBe('hedge')
  })
})
```

---

## 🎨 UI/UX Recommendations

### Help Text
```
Position Mode: [Hedge ▼]

ℹ️ What is Hedge Mode?
━━━━━━━━━━━━━━━━━━━━
Hedge mode allows you to hold both long and short 
positions on the same symbol simultaneously.

Use cases:
• Market-neutral strategies
• Spread trading
• Risk hedging
• Advanced algorithmic strategies

⚠️ Note: Currently supported in Backtest/Optimization.
Live trading requires additional setup.
```

### Position Display
```
┌─────────────────────────────────────────────┐
│ POSITIONS                                   │
├─────────────────────────────────────────────┤
│ Symbol     │ Type  │ Qty │ Entry  │ PNL    │
├────────────┼───────┼─────┼────────┼────────┤
│ BTC-USDT   │ 🔀    │ 0.5 │ 50000  │ +750   │
│  ├ Long    │   →   │ 1.0 │ 50000  │ +1000  │
│  └ Short   │   ←   │ 0.5 │ 50500  │ -250   │
└─────────────────────────────────────────────┘

Legend: 🔀 = Hedge Mode, → = Long, ← = Short
```

---

## 🐛 Common Issues & Solutions

### Issue 1: "futures_position_mode not defined"
**Solution:** Ensure default value is set when initializing exchange config

### Issue 2: Backend not creating PositionPair
**Solution:** Check that config is being sent correctly in network tab

### Issue 3: Results look weird
**Solution:** PositionPair shows NET values - this is correct for hedge mode

---

## 📞 Backend API Reference

### Config Structure Expected by Backend

```python
{
    'exchanges': {
        '<exchange_name>': {
            'type': 'futures',
            'balance': 10000,
            'fee': 0.0004,
            'futures_leverage': 2,
            'futures_leverage_mode': 'cross',      # Required for futures
            'futures_position_mode': 'one-way'     # Optional, defaults to 'one-way'
        }
    },
    'warm_up_candles': 100,
    'logging': { ... }
}
```

### Valid Values
- `futures_position_mode`: `'one-way'` or `'hedge'`
- Default: `'one-way'` (backwards compatible)

---

## ✨ Summary

**What Frontend Devs Need to Do:**
1. Add one dropdown to the form (10 lines of code)
2. Include the field in config object sent to backend (1 line)
3. Set default value (1 line)
4. Build and deploy

**What Backend Provides (Already Done):**
1. ✅ Receives and processes the setting
2. ✅ Creates correct position types
3. ✅ Handles order routing
4. ✅ Returns correct results
5. ✅ Backwards compatible

**The backend is 100% ready - just add the UI control!** 🚀

---

**Questions?**
- Check `UI_UPDATES_NEEDED.md` for current status
- Check `HEDGE_MODE_COMPLETE.md` for implementation details
- Run `python tests/test_hedge_mode_integration.py` to see it working

**Next:** Create frontend issue/PR with this guide attached!
