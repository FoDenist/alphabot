import requests, time
from datetime import datetime

ALPACA_KEY = "PKUSGLCEEZMNDE63GB7HZH4DSP"
ALPACA_SECRET = "23TRHGpy8FeWND3VX8UEE8brb38BPQN89nP5HuxcbocW"
TELEGRAM_TOKEN = "8796929920:AAFuEntANaqhsViOItc8KTLMpDcHuraEWqA"
TELEGRAM_CHAT_ID = "5149087675"

BASE_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"
COINS = ["BTCUSD","ETHUSD","SOLUSD","ADAUSD","XRPUSD"]
STOP_LOSS = 0.006
PROFIT_TARGET = 0.012
DAILY_LOSS_LIMIT = 0.03

baslangic_equity = None
bot_aktif = True

def alpaca_get(endpoint):
    h = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    return requests.get(f"{BASE_URL}{endpoint}", headers=h).json()

def alpaca_post(endpoint, data):
    h = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    return requests.post(f"{BASE_URL}{endpoint}", headers=h, json=data).json()

def telegram(mesaj):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                  json={"chat_id": TELEGRAM_CHAT_ID, "text": mesaj})

def rsi(prices, period=14):
    if len(prices) < period+1: return 50
    gains = losses = 0
    for i in range(len(prices)-period, len(prices)):
        d = prices[i]-prices[i-1]
        if d > 0: gains += d
        else: losses -= d
    ag, al = gains/period, losses/period
    if al == 0: return 100
    return 100 - 100/(1+ag/al)

def sinyal(symbol):
    h = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    url = f"{DATA_URL}/v1beta3/crypto/us/bars?symbols={symbol}&timeframe=5Min&limit=50"
    try:
        bars = requests.get(url, headers=h).json()["bars"][symbol]
        prices = [b["c"] for b in bars]
        r = rsi(prices)
        mom = (prices[-1]-prices[-2])/prices[-2]
        skor = 0
        if r < 35: skor += 2
        elif r < 45: skor += 1
        if r > 65: skor -= 2
        elif r > 55: skor -= 1
        if mom > 0.002: skor += 1
        elif mom < -0.002: skor -= 1
        if skor >= 2: return "BUY", prices[-1], r
        if skor <= -2: return "SELL", prices[-1], r
        return "HOLD", prices[-1], r
    except: return "HOLD", None, 50

def emir(symbol, side):
    return alpaca_post("/v2/orders", {
        "symbol": symbol, "notional": "100",
        "side": side, "type": "market", "time_in_force": "gtc"})

def zarar_kontrol():
    global baslangic_equity, bot_aktif
    eq = float(alpaca_get("/v2/account").get("equity", 0))
    if baslangic_equity is None:
        baslangic_equity = eq
        return True
    if (eq-baslangic_equity)/baslangic_equity <= -DAILY_LOSS_LIMIT:
        bot_aktif = False
        telegram("🛑 Günlük zarar limiti! Bot durduruldu.")
        return False
    return True

def main():
    global bot_aktif
    telegram("🚀 AlphaBot başlatıldı! Paper trading aktif.")
    print("Bot başladı!")
    pozlar = {}
    while bot_aktif:
        try:
            if not zarar_kontrol(): break
            hesap = alpaca_get("/v2/account")
            nakit = float(hesap.get("cash", 0))
            equity = float(hesap.get("equity", 0))
            print(f"{datetime.now().strftime('%H:%M:%S')} | Hesap: ${equity:,.2f}")
            for coin in COINS:
                s, fiyat, r = sinyal(coin)
                if fiyat is None: continue
                print(f"{coin}: ${fiyat:.4f} RSI:{r:.1f} {s}")
                if s == "BUY" and coin not in pozlar and nakit > 100:
                    sonuc = emir(coin, "buy")
                    if "id" in sonuc:
                        pozlar[coin] = {"fiyat": fiyat,
                                        "hedef": fiyat*(1+PROFIT_TARGET),
                                        "stop": fiyat*(1-STOP_LOSS)}
                        telegram(f"🟢 ALINDI: {coin}\n💵 ${fiyat:.4f}\n🎯 Hedef: ${pozlar[coin]['hedef']:.4f}\n🛑 Stop: ${pozlar[coin]['stop']:.4f}")
                elif coin in pozlar:
                    p = pozlar[coin]
                    kar = (fiyat-p["fiyat"])/p["fiyat"]*100
                    if fiyat >= p["hedef"]:
                        emir(coin, "sell")
                        telegram(f"✅ KAR: {coin} +%{kar:.2f}")
                        del pozlar[coin]
                    elif fiyat <= p["stop"]:
                        emir(coin, "sell")
                        telegram(f"🛑 STOP: {coin} %{kar:.2f}")
                        del pozlar[coin]
            time.sleep(60)
        except Exception as e:
            print(f"Hata: {e}")
            time.sleep(30)

main()
