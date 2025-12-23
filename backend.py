from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import requests, pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

app = FastAPI()
BINANCE = "https://api.binance.com/api/v3/klines"

def get_df(symbol, tf, limit=120):
    data = requests.get(BINANCE, params={
        "symbol": symbol,
        "interval": tf,
        "limit": limit
    }).json()
    df = pd.DataFrame(data, columns=[
        "t","o","h","l","c","v","_","_","_","_","_","_"
    ]).astype(float)
    return df

def signal_logic(df):
    rsi = RSIIndicator(df["c"]).rsi().iloc[-1]
    ema20 = EMAIndicator(df["c"],20).ema_indicator().iloc[-1]
    ema50 = EMAIndicator(df["c"],50).ema_indicator().iloc[-1]
    price = df["c"].iloc[-1]

    if price > ema20 > ema50 and rsi < 70:
        return "BUY", rsi
    if price < ema20 < ema50 and rsi > 30:
        return "SELL", rsi
    return "WAIT", rsi

@app.get("/signal")
def signal(symbol="BTCUSDT", tf="15m"):
    df = get_df(symbol, tf)
    sig, rsi = signal_logic(df)

    support = round(df["l"].tail(20).min(),2)
    resistance = round(df["h"].tail(20).max(),2)

    sl = tp = None
    if sig=="BUY":
        sl, tp = support, resistance
    elif sig=="SELL":
        sl, tp = resistance, support

    confidence = 50
    if sig!="WAIT": confidence+=30
    if rsi<30 or rsi>70: confidence+=15
    confidence=min(confidence,95)

    candles = [
        {"time":int(r.t/1000),"open":r.o,"high":r.h,"low":r.l,"close":r.c}
        for _,r in df.tail(80).iterrows()
    ]

    return JSONResponse({
        "signal": sig,
        "confidence": confidence,
        "rsi": round(rsi,2),
        "support": support,
        "resistance": resistance,
        "sl": sl,
        "tp": tp,
        "candles": candles
    })

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TradingView Helper</title>
<script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
<style>
body{background:#0b0f1a;color:white;font-family:Arial;padding:10px}
select{width:100%;padding:8px;margin-bottom:8px}
.signal{font-size:28px;text-align:center;font-weight:bold}
.BUY{color:#00ff99}.SELL{color:#ff4d4d}.WAIT{color:#ffaa00}
.card{background:#151a2e;padding:12px;border-radius:10px;margin-top:10px}
</style>
</head>
<body>

<h3>📊 TradingView Signal Helper</h3>

<select id="coin" onchange="load()">
<option>BTCUSDT</option>
<option>ETHUSDT</option>
<option>BNBUSDT</option>
<option>SOLUSDT</option>
<option>XRPUSDT</option>
</select>

<select id="tf" onchange="load()">
<option value="1m">1m</option>
<option value="5m">5m</option>
<option value="15m">15m</option>
<option value="1h">1h</option>
<option value="4h">4h</option>
<option value="1d">1d</option>
</select>

<div id="chart" style="height:300px"></div>

<div class="card">
<div id="signal" class="signal">Loading...</div>
<p>Confidence: <span id="conf"></span>%</p>
<p>RSI: <span id="rsi"></span></p>
<p>Stop Loss: <span id="sl"></span></p>
<p>Take Profit: <span id="tp"></span></p>
</div>

<script>
const chart = LightweightCharts.createChart(document.getElementById('chart'), {
  layout:{background:{color:'#0b0f1a'},textColor:'#fff'}
});
const series = chart.addCandlestickSeries();

async function load(){
  let coin = coinEl.value;
  let tf = tfEl.value;
  let r = await fetch(`/signal?symbol=${coin}&tf=${tf}`);
  let d = await r.json();

  series.setData(d.candles);

  let s = document.getElementById("signal");
  s.innerText = d.signal;
  s.className = "signal " + d.signal;

  conf.innerText = d.confidence;
  rsi.innerText = d.rsi;
  sl.innerText = d.sl;
  tp.innerText = d.tp;
}

const coinEl = document.getElementById("coin");
const tfEl = document.getElementById("tf");
load();
</script>

</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
