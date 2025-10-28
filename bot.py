import logging
import os
import sys
import requests
import numpy as np
import pandas as pd
import ta
import dns.resolver
from datetime import datetime

# === KONFIGURASI ===
TIMEFRAMES = ["15m", "1h"]
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT"
]

TP_MULTIPLIER = 1.5
SL_MULTIPLIER = 1.0

# Ambil token dari environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    logging.error("Missing TELEGRAM_TOKEN or CHAT_ID in environment variables. Exiting.")
    sys.exit(1)

# === FUNGSI TELEGRAM ===
def send_message(msg):
    """Kirim pesan ke Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown",
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logging.warning(f"Telegram API returned {resp.status_code}: {resp.text}")
    except Exception as e:
        logging.error(f"[ERROR] Gagal kirim pesan Telegram: {e}")

# === FUNGSI GET KLINES (dengan DNS Cloudflare) ===
def get_klines(symbol, interval="15m", limit=200):
    """
    Ambil data candle dari Binance menggunakan resolver DNS Cloudflare
    """
    resolver = dns.resolver.Resolver()
    resolver.nameservers = ["1.1.1.1", "1.0.0.1"]

    domain = "api.binance.com"
    url = f"https://{domain}/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}

    try:
        # Tes resolve dulu
        resolver.resolve(domain, "A")

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        df = pd.DataFrame(data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "trades",
            "taker_base_volume", "taker_quote_volume", "ignore"
        ])

        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

        return df

    except Exception as e:
        logging.error(f"[ERROR] get_klines gagal untuk {symbol} {interval}: {e}")
        return pd.DataFrame()

# === FUNGSI DETEKSI SINYAL ===
def detect_signal(df):
    if len(df) < 20:
        return None

    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["ema50"] = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean()

    df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
    df["vwap_diff"] = df["close"] - df["vwap"]

    last, prev = df.iloc[-1], df.iloc[-2]
    bullish_div = (last["close"] > prev["close"]) and (last["vwap_diff"] < prev["vwap_diff"])
    bearish_div = (last["close"] < prev["close"]) and (last["vwap_diff"] > prev["vwap_diff"])

    def kernel_smooth(series, kernel_size=5):
        kernel = np.exp(-0.5 * (np.linspace(-2, 2, kernel_size) ** 2))
        kernel /= kernel.sum()
        return np.convolve(series, kernel, mode='same')

    df["rsi_kernel"] = kernel_smooth(df["rsi"].fillna(method="bfill"))
    df["atr"] = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14).average_true_range()

    signal, strength, mode = None, None, None
    if bullish_div and df["rsi_kernel"].iloc[-1] < 40 and df["macd"].iloc[-1] > df["macd_signal"].iloc[-1]:
        signal, mode = "BUY", "VWAP-RSI-Kernel"
        strength = "Strong" if df["volume_ratio"].iloc[-1] > 1.5 else "Normal"
    elif bearish_div and df["rsi_kernel"].iloc[-1] > 60 and df["macd"].iloc[-1] < df["macd_signal"].iloc[-1]:
        signal, mode = "SELL", "VWAP-RSI-Kernel"
        strength = "Strong" if df["volume_ratio"].iloc[-1] > 1.5 else "Normal"

    if signal:
        details = {
            "rsi": df["rsi_kernel"].iloc[-1],
            "macd": df["macd"].iloc[-1],
            "macd_signal": df["macd_signal"].iloc[-1],
            "volume_ratio": df["volume_ratio"].iloc[-1],
            "ema50": df["ema50"].iloc[-1],
            "atr": df["atr"].iloc[-1],
        }
        return signal, strength, mode, details
    return None

# === FUNGSI KONFIRMASI MULTI-TF ===
def confirm_signal(symbol, signal_small_tf, signal_big_tf):
    if not signal_small_tf or not signal_big_tf:
        return None
    if signal_small_tf[0] == signal_big_tf[0]:
        signal, strength, mode, details = signal_small_tf
        return signal, f"{strength}+Confirmed", f"{mode} MTF", details
    return None

# === FUNGSI UTAMA ===
def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    send_message(f"🚀 Combo+Booster mode aktif\n📊 {len(SYMBOLS)} pair | TF: {', '.join(TIMEFRAMES)}")

    total_signals = 0
    for symbol in SYMBOLS:
        try:
            df_small = get_klines(symbol, TIMEFRAMES[0])
            df_big = get_klines(symbol, TIMEFRAMES[1])

            if df_small.empty or df_big.empty:
                logging.warning(f"Data kosong untuk {symbol}")
                continue

            res_small = detect_signal(df_small)
            res_big = detect_signal(df_big)
            result = confirm_signal(symbol, res_small, res_big)

            if result:
                signal, strength, mode, details = result
                total_signals += 1
                last = df_small.iloc[-1]
                close_price = last["close"]
                atr = details["atr"]

                if signal == "BUY":
                    entry = close_price
                    tp = entry + (atr * TP_MULTIPLIER)
                    sl = entry - (atr * SL_MULTIPLIER)
                    emoji = "🟢"
                else:
                    entry = close_price
                    tp = entry - (atr * TP_MULTIPLIER)
                    sl = entry + (atr * SL_MULTIPLIER)
                    emoji = "🔴"

                msg = (
                    f"{emoji} *{signal} Signal ({strength})*\n"
                    f"Mode: `{mode}`\n"
                    f"Pair: `{symbol}` | TF: `{TIMEFRAMES[0]} & {TIMEFRAMES[1]}`\n"
                    f"Entry: `{entry:.4f}`\n"
                    f"TP: `{tp:.4f}` | SL: `{sl:.4f}`\n"
                    f"ATR: {atr:.4f}\n"
                    f"RSI-Kernel: {details['rsi']:.2f}\n"
                    f"MACD: {details['macd']:.4f} | Signal: {details['macd_signal']:.4f}\n"
                    f"Volume: {details['volume_ratio']:.2f}x rata-rata\n"
                    f"EMA50: {details['ema50']:.2f}\n"
                    f"Time: {last['close_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                    "_Info only — no auto order._"
                )

                send_message(msg)
                logging.info(f"{symbol} {signal} ({strength}) {mode}")

        except Exception as e:
            logging.error(f"Error {symbol}: {e}")

    send_message(f"✅ Scan selesai. {total_signals} sinyal ditemukan.")

if __name__ == "__main__":
    main()
