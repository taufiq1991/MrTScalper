# 🚀 Combo+Booster Binance Signal Bot

Bot trading analisis multi-timeframe yang mengirimkan sinyal BUY / SELL ke Telegram berdasarkan kombinasi indikator teknikal (RSI, VWAP, MACD, EMA, dan Volume).
Dilengkapi fitur anti-duplikat sinyal, persistent storage, serta multi-timeframe confirmation.

---

## ⚙️ Fitur Utama

| Fitur | Deskripsi |
|-------|------------|
| 🕐 Multi-Timeframe Analysis | Menganalisis 4 timeframe sekaligus (5m, 15m, 1h, 4h) |
| 💰 20 Top USDT Pairs | Memantau 20 aset kripto paling aktif di Binance |
| ⚡ VWAP–RSI–Kernel Strategy | Deteksi sinyal dengan kombinasi VWAP divergence, RSI kernel smoothing, dan MACD cross |
| 🔁 Auto-Loop Scan | Menjalankan analisis otomatis setiap beberapa menit |
| 💾 Persistent Sinyal (JSON) | Menyimpan sinyal terakhir agar tidak kirim ulang |
| 🔒 Telegram Notification | Kirim hasil sinyal langsung ke chat Telegram |
| 🧱 Binance API v3 Terbaru | Mengambil data harga real-time dari Binance |

---

## 📦 Instalasi

1. Clone repository
   ```bash
   git clone https://github.com/username/ComboBooster-Bot.git
   cd ComboBooster-Bot
   ```

2. Buat virtual environment & install dependencies
   ```bash
   python -m venv venv
   source venv/bin/activate     # Mac/Linux
   venv\Scripts\activate      # Windows

   pip install -r requirements.txt
   ```

3. Buat file environment (.env)
   ```bash
   export TELEGRAM_TOKEN="123456:ABCDEF..."
   export CHAT_ID="123456789"
   ```

---

## 🧠 Konfigurasi

Edit variabel di bagian atas file `bot.py`:

```python
TIMEFRAMES = ["5m", "15m", "1h", "4h"]
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
    "TRXUSDT", "UNIUSDT", "SUIUSDT", "SHIBUSDT", "MATICUSDT",
    "LTCUSDT", "BCHUSDT", "ICPUSDT", "ALGOUSDT", "AAVEUSDT"
]
SCAN_INTERVAL = 15  # menit antar scan
```

---

## 🗂 File Pendukung

| File | Fungsi |
|------|---------|
| `bot.py` | File utama bot |
| `last_signals.json` | Menyimpan sinyal terakhir agar tidak duplikat |
| `.env` | Token dan Chat ID Telegram |
| `requirements.txt` | Daftar dependensi Python |

---

## 🧾 Contoh Output Telegram

```
🟢 BUY Signal (Strong+Confirmed)
Mode: VWAP-RSI-Kernel MTF
Pair: BTCUSDT | TF: 5m & 1h
Entry: 67542.3210
TP: 68122.4210 | SL: 66962.2210
ATR: 388.0721
RSI-Kernel: 32.55
MACD: 56.0031 | Signal: 45.8821
Volume: 1.83x rata-rata
EMA50: 67831.23
Time: 2025-10-28 12:15:00 UTC

_Info only — no auto order._
```

---

## 🧩 Menjalankan Bot

```bash
python bot.py
```

Bot akan:
- Mengambil data harga dari Binance
- Menghitung indikator teknikal
- Mendeteksi sinyal multi-timeframe
- Mengirim notifikasi ke Telegram
- Menyimpan hasil terakhir ke `last_signals.json`

---

## ⚠️ Catatan

- Bot ini **tidak melakukan eksekusi order otomatis** — hanya memberikan sinyal analisis.
- Gunakan untuk **riset, edukasi, atau manual trading**.
- Pastikan koneksi internet stabil agar data dari Binance tidak timeout.
- Disarankan **delay 2–10 detik per pair** jika kamu menambah jumlah pasangan agar tidak kena rate limit Binance.

---

## 💡 Ide Pengembangan Selanjutnya

- Integrasi ke TradingView Webhook
- Ekspor sinyal ke Google Sheets
- Fitur backtesting otomatis
- Order simulator (untuk evaluasi akurasi strategi)

---

## 🧑‍💻 Author

**Combo+Booster Bot by [YourName]**  
📬 Telegram Alerts • Python • Binance API • TA Indicators
