#!/usr/bin/env python3
import os
import time
import requests
import pandas as pd
import telegram
import logging
from datetime import datetime

# Ambil konfigurasi dari environment (GitHub Secrets)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SYMBOLS = os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT").split(",")
TIMEFRAMES = os.getenv("TIMEFRAMES", "1m,5m,15m").split(",")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 15))

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise SystemExit("❌ Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")

bot = telegram.Bot(token=TELEGRAM_TOKEN)

def send_msg(text):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Telegram Error: {e}")

def get_klines(symbol, interval, limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    data = requests.get(url, params=params, timeout=10).json()
    df = pd.DataFrame(data, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","qav","trades","tbbav","tbqav","ignore"
    ])
    df["close"] = pd.to_numeric(df["close"])
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    return df

def ema(series, period): return series.ewm(span=period, adjust=False).mean()
def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def detect_signal(df):
    df["ema9"] = ema(df["close"], 9)
    df["ema21"] = ema(df["close"], 21)
    df["rsi"] = rsi(df["close"], 14)
    prev, last = df.iloc[-2], df.iloc[-1]
    if prev["ema9"] <= prev["ema21"] and last["ema9"] > last["ema21"] and last["rsi"] < 70:
        return "BUY"
    if prev["ema9"] >= prev["ema21"] and last["ema9"] < last["ema21"] and last["rsi"] > 30:
        return "SELL"
    return None

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    results = []
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            try:
                df = get_klines(symbol, tf)
                sig = detect_signal(df)
                if sig:
                    last = df.iloc[-1]
                    msg = (
                        f"*{sig} Signal*\n"
                        f"Pair: `{symbol}`\n"
                        f"TF: `{tf}`\n"
                        f"Close: {last['close']:.4f}\n"
                        f"RSI: {last['rsi']:.2f}\n"
                        f"Time: {last['close_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    )
                    send_msg(msg)
                    results.append(f"{symbol}-{tf}: {sig}")
            except Exception as e:
                logging.error(f"{symbol}-{tf}: {e}")
    if not results:
        logging.info("No new signal found.")

if __name__ == "__main__":
    main()
