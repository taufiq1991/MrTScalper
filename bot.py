#!/usr/bin/env python3
import os
import requests
import pandas as pd
import telegram
import logging
from datetime import datetime

# --- Environment Variables from GitHub Secrets ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SYMBOLS = os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,ADAUSDT,DOGEUSDT,AVAXUSDT,TRXUSDT,MATICUSDT").split(",")
TIMEFRAMES = os.getenv("TIMEFRAMES", "1m,5m,15m").split(",")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise SystemExit("❌ TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set")

bot = telegram.Bot(token=TELEGRAM_TOKEN)

# --- Utility Functions ---
def send_message(text):
    """Kirim pesan ke Telegram"""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Telegram send failed: {e}")

def get_klines(symbol, interval, limit=100):
    """Ambil data candle dari Binance"""
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","qav","trades","tbbav","tbqav","ignore"
    ])
    df["close"] = pd.to_numeric(df["close"])
    df["volume"] = pd.to_numeric(df["volume"])
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    return df

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line

# --- Signal Detection ---
def detect_signal(df):
    df["ema9"] = ema(df["close"], 9)
    df["ema21"] = ema(df["close"], 21)
    df["ema50"] = ema(df["close"], 50)
    df["rsi14"] = rsi(df["close"], 14)
    df["macd"], df["macd_signal"] = macd(df["close"])

    prev = df.iloc[-2]
    last = df.iloc[-1]

    # --- Volume Filter ---
    avg_vol = df["volume"].rolling(20).mean().iloc[-1]
    last_vol = df["volume"].iloc[-1]
    vol_ratio = last_vol / avg_vol if avg_vol > 0 else 0
    if vol_ratio < 1.5:
        return None  # Volume rendah, abaikan sinyal

    # --- EMA Cross + MACD + RSI + Trend Confirmation ---
    signal = None
    if (
        prev["ema9"] <= prev["ema21"]
        and last["ema9"] > last["ema21"]
        and last["rsi14"] < 70
        and last["macd"] > last["macd_signal"]
        and last["close"] > last["ema50"]
    ):
        signal = "BUY"

    elif (
        prev["ema9"] >= prev["ema21"]
        and last["ema9"] < last["ema21"]
        and last["rsi14"] > 30
        and last["macd"] < last["macd_signal"]
        and last["close"] < last["ema50"]
    ):
        signal = "SELL"

    if signal:
        details = {
            "rsi": last["rsi14"],
            "macd": last["macd"],
            "macd_signal": last["macd_signal"],
            "volume_ratio": vol_ratio,
            "ema50": last["ema50"]
        }
        return signal, details
    return None

# --- Main ---
def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    start_msg = f"🚀 Bot sinyal trading aktif!\n📊 Memeriksa {len(SYMBOLS)} pair di timeframe {', '.join(TIMEFRAMES)}"
    send_message(start_msg)

    total_signals = 0
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            try:
                df = get_klines(symbol, tf)
                result = detect_signal(df)
                if result:
                    signal, details = result
                    total_signals += 1
                    last = df.iloc[-1]
                    msg = (
                        f"*{signal} Signal*\n"
                        f"Pair: `{symbol}`\n"
                        f"Timeframe: `{tf}`\n"
                        f"Close: {last['close']:.4f}\n"
                        f"RSI14: {details['rsi']:.2f}\n"
                        f"MACD: {details['macd']:.4f} | Signal: {details['macd_signal']:.4f}\n"
                        f"Volume: {details['volume_ratio']:.2f}x rata-rata\n"
                        f"EMA50: {details['ema50']:.2f}\n"
                        f"Time: {last['close_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                        "_Info only — no auto order._"
                    )
                    send_message(msg)
                    logging.info(f"{symbol} {tf} {signal}")
            except Exception as e:
                logging.error(f"Error {symbol} {tf}: {e}")

    end_msg = f"✅ Scan selesai. {total_signals} sinyal ditemukan."
    send_message(end_msg)

if __name__ == "__main__":
    main()
