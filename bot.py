import os
import pandas as pd
import ta
import logging
from datetime import datetime
from binance.client import Client
from telegram import Bot

# --- Konfigurasi utama ---
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
client = Client(api_key, api_secret)

bot_token = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")
bot = Bot(token=bot_token)

SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]
TIMEFRAMES = ["1m", "3m", "5m"]

logging.basicConfig(level=logging.INFO)

# --- Fungsi ambil data Binance ---
def get_klines(symbol, interval):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=100)
    df = pd.DataFrame(klines, columns=[
        "open_time","open","high","low","close","volume","close_time",
        "qav","num_trades","taker_base_vol","taker_quote_vol","ignore"
    ])
    df = df.astype(float)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    return df

# --- Deteksi sinyal ---
def detect_signal(df):
    df["ema9"] = ta.trend.ema_indicator(df["close"], 9)
    df["ema21"] = ta.trend.ema_indicator(df["close"], 21)
    df["ema50"] = ta.trend.ema_indicator(df["close"], 50)
    df["rsi"] = ta.momentum.rsi(df["close"], 14)
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    last, prev = df.iloc[-1], df.iloc[-2]
    signal, strength = None, "Weak"

    # --- Combo utama ---
    if prev["ema9"] < prev["ema21"] and last["ema9"] > last["ema21"] and last["rsi"] < 70:
        signal, strength = "BUY", "Strong"
    elif prev["ema9"] > prev["ema21"] and last["ema9"] < last["ema21"] and last["rsi"] > 30:
        signal, strength = "SELL", "Strong"

    # --- Booster tambahan ---
    else:
        ema_gap = abs(last["ema9"] - last["ema21"]) / last["ema21"]
        if ema_gap < 0.001:
            signal, strength = "BUY" if last["macd"] > last["macd_signal"] else "SELL", "Booster (Early Cross)"
        elif last["rsi"] > 40 and prev["rsi"] < 35 and last["close"] > last["ema50"]:
            signal, strength = "BUY", "Booster (RSI Pullback)"
        elif last["rsi"] < 60 and prev["rsi"] > 65 and last["close"] < last["ema50"]:
            signal, strength = "SELL", "Booster (RSI Pullback)"

    return signal, strength

# --- Kirim pesan ke Telegram ---
def send_message(msg):
    try:
        bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Telegram error: {e}")

# --- Main loop ---
def main():
    total_signals = 0
    messages = []

    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            try:
                df = get_klines(symbol, tf)
                signal, strength = detect_signal(df)
                if signal:
                    total_signals += 1
                    last = df.iloc[-1]
                    emoji = "🟢" if signal == "BUY" else "🔴"
                    msg = (
                        f"{emoji} *{signal} Signal ({strength})*\n"
                        f"Pair: `{symbol}` | TF: `{tf}`\n"
                        f"Close: {last['close']:.2f} | RSI: {last['rsi']:.1f}\n"
                        f"Time: {last['close_time'].strftime('%H:%M:%S UTC')}"
                    )
                    messages.append(msg)
            except Exception as e:
                logging.error(f"{symbol} {tf}: {e}")

    if total_signals > 0:
        for m in messages:
            send_message(m)
        send_message(f"✅ Update {datetime.utcnow().strftime('%H:%M UTC')} — {total_signals} sinyal baru.")
    else:
        send_message(
            f"⏳ Update ({datetime.utcnow().strftime('%H:%M UTC')})\n"
            f"Tidak ada sinyal baru.\n"
            f"Pair: {len(SYMBOLS)} | TF: {len(TIMEFRAMES)}"
        )

if __name__ == "__main__":
    main()
