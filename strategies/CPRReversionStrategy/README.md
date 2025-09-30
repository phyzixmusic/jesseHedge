### **Strategy Overview:**
Advanced mean-reversion strategy that trades daily gaps back to CPR levels with historical pattern validation.

### **Core Logic:**
```
1. Daily Setup (8am Bali/9am Tokyo):
   • Calculate today's CPR from yesterday's OHLC
   • Check market open price vs CPR range (TC-BC)
   • Determine CPR trend (ascending/descending vs previous day)

2. Quality Setup Detection:
   • HIGH QUALITY: Descending CPR + Price Above Range = Short
   • STANDARD: Ascending CPR + Price Below Range = Long
   • REQUIREMENT: Sufficient delta (distance from range)

3. Historical Validation:
   • Individual pair: 70% success rate in last 21 days
   • Portfolio-wide: Overall pattern success tracking
   • Pattern = Price touched CPR range during the day

4. Trade Execution:
   • ENTRY: Market open with real-time price streams
   • EXIT: Candle wick touches BC (shorts) or TC (longs)
   • MONITORING: 15-minute candles for intraday tracking
```

### **Example Trade:**
```
Yesterday BTCUSDT: H=$51k, L=$48k, C=$49.5k
Today's CPR: TC=$49.5k, BC=$49k, Pivot=$49.25k
Yesterday's CPR: Pivot=$49.75k

Analysis:
• CPR Trend: DESCENDING (49.25k < 49.75k)
• Market Open (8am Bali): $52k
• Setup: Price ABOVE range + DESCENDING CPR = HIGH QUALITY SHORT
• Delta: |52k - 49.5k| / 49.5k = 5.05% ✅
• Historical Check: 8/10 last occurrences successful = 80% ✅
• ACTION: Execute SHORT at market open
• TARGET: Wait for price to wick touch $49k-$49.5k range
```
