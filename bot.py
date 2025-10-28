import logging
import os
import sys
import time
import requests
import numpy as np
import pandas as pd
import ta
from datetime import datetime

# === KONFIGURASI ===
TIMEFRAMES = ["5m", "15m", "1h", "4h"]
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT"
]

TP_MULTIPLIER = 1.5
SL_MULTIPLIER = 1.0

# === FASTSCAN MODE ===
FASTSCAN_ENABLED = True
FASTSCAN_TF_SMALL = ["5m", "15m", "1h"]
FASTSCAN_TF_BIG = ["4h"]

def parse_tf_to_minutes(tf):
    if tf.endswith("m"): return int(tf[:-1])
    if tf.endswith("h"): return int(tf[:-1]) * 60
    if tf.endswith("d"): return int(tf[:-1]) * 1440
    raise ValueError(f"Format timeframe tidak dikenali: {tf}")

SCAN_INTERVAL_MINUTES = parse_tf_to_minutes(min(TIMEFRAMES, key=parse_tf_to_minutes))

# === TELEGRAM ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
if not TELEGRAM_TOKEN or not CHAT_ID:
    logging.error("❌ Missing TELEGRAM_TOKEN or CHAT_ID.")
    sys.exit(1)

def send_message(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logging.warning(f"Telegram API returned {resp.status_code}: {resp.text}")
    except Exception as e:
        logging.error(f"[ERROR] Gagal kirim pesan Telegram: {e}")

# === GET KLINES ===
def get_klines(symbol, interval="15m", limit=200, retries=3):
    url = "https://api.binance.com/api/v3/klines"
    for attempt in range(retries):
        try:
            r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
            r.raise_for_status()
            data = r.json()
            df = pd.DataFrame(data, columns=[
                "open_time","open","high","low","close","volume",
                "close_time","quote_asset_volume","trades",
                "taker_base_volume","taker_quote_volume","ignore"
            ])
            df = df.astype({"open":float,"high":float,"low":float,"close":float,"volume":float})
            df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
            return df
        except Exception as e:
            logging.warning(f"[RETRY {attempt+1}/{retries}] {symbol} {interval}: {e}")
            time.sleep(2)
    logging.error(f"[ERROR] get_klines gagal total: {symbol} {interval}")
    return pd.DataFrame()

# === DETEKSI SINYAL ===
def detect_signal(df):
    if df.empty: return None
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    df["ema50"] = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
    macd = ta.trend.MACD(df["close"])
    df["macd"], df["macd_signal"] = macd.macd(), macd.macd_signal()
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
    df["vwap"] = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()
    df["vwap_diff"] = df["close"] - df["vwap"]
    if len(df) < 3: return None
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

# === KONFIRMASI MULTI-TF ===
def confirm_signal(symbol, *signals):
    valid = [s for s in signals if s]
    if len(valid) < 2:
        return None
    sigs = [s[0] for s in valid]
    if all(x == sigs[0] for x in sigs):
        signal, strength, mode, details = valid[0]
        return signal, f"{strength}+Confirmed({len(valid)}TF)", f"{mode} MTF", details
    return None

# === SCAN ===
def run_scan():
    total = 0
    for symbol in SYMBOLS:
        try:
            # FastScan: ambil TF kecil dulu
            dfs_small = {tf: get_klines(symbol, tf) for tf in FASTSCAN_TF_SMALL}
            res_small = {tf: detect_signal(df) for tf, df in dfs_small.items()}
            # Konfirmasi awal (2–3 TF kecil)
            result_small = confirm_signal(symbol, *res_small.values())
            if not result_small:
                logging.info(f"Skip {symbol} — belum ada konfirmasi di TF kecil")
                continue
            # Kalau sudah ada potensi, ambil TF besar (4h)
            dfs_big = {tf: get_klines(symbol, tf) for tf in FASTSCAN_TF_BIG}
            res_big = {tf: detect_signal(df) for tf, df in dfs_big.items()}
            result = confirm_signal(symbol, result_small, *res_big.values())
            if result:
                total += 1
                signal, strength, mode, details = result
                last = dfs_small["5m"].iloc[-1]
                close_price, atr = last["close"], details["atr"]
                if signal == "BUY":
                    tp, sl, emoji = close_price + atr*TP_MULTIPLIER, close_price - atr*SL_MULTIPLIER, "🟢"
                else:
                    tp, sl, emoji = close_price - atr*TP_MULTIPLIER, close_price + atr*SL_MULTIPLIER, "🔴"
                msg = (
                    f"{emoji} *{signal} Signal ({strength})*\n"
                    f"Mode: `{mode}`\n"
                    f"Pair: `{symbol}`\n"
                    f"Entry: `{close_price:.4f}`\n"
                    f"TP: `{tp:.4f}` | SL: `{sl:.4f}`\n"
                    f"ATR: {atr:.4f}\n"
                    f"RSI: {details['rsi']:.2f} | MACD: {details['macd']:.4f}\n"
                    f"Vol: {details['volume_ratio']:.2f}x avg | EMA50: {details['ema50']:.2f}\n"
                    f"Time: {last['close_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
                    "_FastScan Mode — info only._"
                )
                send_message(msg)
                logging.info(f"{symbol} {signal} ({strength}) {mode}")
        except Exception as e:
            logging.error(f"Error {symbol}: {e}")
    send_message(f"✅ Scan selesai. {total} sinyal ditemukan.")

# === MAIN ===
def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    send_message(f"🚀 Combo+Booster aktif | FastScan={FASTSCAN_ENABLED}\nTF: {', '.join(TIMEFRAMES)}\n"
                 f"Interval otomatis: {SCAN_INTERVAL_MINUTES} menit")
    while True:
        start = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        logging.info(f"🕒 Mulai scan {start}")
        run_scan()
        logging.info(f"⏸ Tunggu {SCAN_INTERVAL_MINUTES} menit...\n")
        time.sleep(SCAN_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    main()
