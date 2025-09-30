# HedgeModeTest - Quick Start

## 🎯 Goal
Verify that you can open LONG and SHORT positions **simultaneously** on the same symbol.

## 📦 Upload
Upload this entire folder to Jesse website.

## ▶️ Run
1. Select **HedgeModeTest** strategy
2. Choose any symbol (ETH-USDT, BTC-USDT)
3. Use **1h timeframe**
4. Date range: **At least 30 candles**
5. Click **Run Backtest**

## ✅ Success = Seeing This

At **candle 15**, look for:

```
[...T00:15:00] --- Position Status (Index 15) ---
[...T00:15:00] Long: 1.0, Short: 0.5  ← BOTH ARE NON-ZERO!
[...T00:15:00] Net: 0.5
```

**If you see this, HEDGE MODE IS WORKING!** 🎉

## ❌ Failure = Seeing This

At **candle 10**, you see:
```
Long position closed
Short position opened
```

Instead of both being open, the short **closed the long** = **ONE-WAY MODE** (hedge mode didn't activate)

## 🔍 Also Check

**First log line:**
```
[HedgeModeTest] ✅ Enabled hedge mode for: Bybit USDT Perpetual
```

**Initialization:**
```
Hedge Mode Active: True  ← Must be True
Position type: PositionPair  ← Not "Position"
```

## 📊 Trade Report

Should show **2 trades**:
- Trade #1: Long (candles 5-20)
- Trade #2: Short (candles 10-25)

Notice they **overlap** from candle 10-20 = Hedge mode working!

## 🆘 If It Doesn't Work

Share these logs:
1. First 50 lines (initialization)
2. Lines from candles 5, 10, 15, 20, 25
3. Final trade report

---

**That's it!** This strategy auto-enables hedge mode, so just upload and run! 🚀