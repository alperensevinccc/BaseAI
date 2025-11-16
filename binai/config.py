"""
BaseAI - BinAI v21.2 Mimarisi
Ana Konfigürasyon Dosyası (Enterprise Core)

v21.2 Yükseltmeleri:
- "Süper Özellik #2: Dinamik Pozisyon Boyutu" (Volatilite Tabanlı Risk) 
  ayarları eklendi.
- Bu, 'trade_manager.py' (v21.2) motoru tarafından kullanılır.
"""

# === ÇEKİRDEK API AYARLARI ===
API_KEY = "YOUR_PRODUCTION_API_KEY"
API_SECRET = "YOUR_PRODUCTION_API_SECRET"
TESTNET_API_KEY = "j6u7LwkGO03XY7FD2BNoEeMrdj80xGxlVZdssLMEjvCfHt9ORd5HkHGTMxASPXPA"
TESTNET_API_SECRET = "jxW9lyD9ppwIvVo8gd9LnUCP1R1H6YZAgZGrs9JXAlVGXakmoVTiftrcWsHbqDm0"
USE_TESTNET = True  # Canlı işlem için 'False' yapın

# === PİYASA TARAMA MİMARİSİ ===
MARKET_SCAN_ENABLED = True
SYMBOLS_BLACKLIST = ["USDCUSDT", "BUSDUSDT", "TUSDUSDT", "FDUSDUSDT", "USDTTRY"]
MIN_24H_VOLUME_USDT = 50000000
SYMBOLS_WHITELIST = ["BTCUSDT", "ETHUSDT"] # Backtester v9.0 tarafından kullanılır

# === v20.0 WEBSOCKET (GERÇEK ZAMANLI) MOTORU ===
# (main.py v21.0 'Akıllı Bekleme' tarafından kullanılır)
MIN_CACHE_SYMBOLS = 100 # Botun başlamak için beklemesi gereken minimum sembol sayısı

# === v21.0 ÇEKİRDEK MOTOR AYARLARI ===
# (main.py v21.0 tarafından kullanılır)
MAIN_LOOP_SLEEP_SECONDS = 5 # Ana analiz döngüsü arasındaki bekleme süresi (v20'deki 5sn)
CRITICAL_ERROR_SLEEP_SECONDS = 30 # Kritik hatadan sonra bekleme süresi (v20'deki 30sn)

# === v15.0 "SONSUZ OTONOMİ" DÖNGÜSÜ ===
OPTIMIZATION_INTERVAL_HOURS = 12 # 12 saatte bir otonom analiz/optimizasyon

# === v19.0 "DERİN EVRİM" (Deep Evolution) VERİ DERİNLİĞİ ===
DEEP_EVOLUTION_KLINE_LIMIT = 15000 # (50+ gün)
BACKTEST_KLINE_LIMIT = 1500 # (5 gün)

# === v16.0 "FIRSATÇI YENİDEN DENGELEME" (Opportunistic Rebalancing) ===
OPPORTUNISTIC_REBALANCE_ENABLED = True
OPPORTUNISTIC_REBALANCE_THRESHOLD = 0.95 # (Güven Puanı %95'in üzerinde olmalı)

# === STRATEJİ MİMARİSİ (v11.0 - PİYASA REJİMİ TESPİTİ) ===
INTERVAL = "5m" 
MIN_SIGNAL_CONFIDENCE = 0.80
ADX_PERIOD = 14
ADX_TREND_THRESHOLD = 25 
MIN_KLINES_FOR_STRATEGY = 200 # (YENİ - v21.0) Stratejinin analiz için ihtiyaç duyduğu minimum mum sayısı
                              # (SLOW_MA_PERIOD + ADX_PERIOD + 2'den (örn: 50+14+2=66) büyük bir tampon olmalı)

# === v10.3 "Trend Takip" Stratejisi Parametreleri (Evrim Motoru tarafından optimize edildi) ===
FAST_MA_PERIOD = 20
SLOW_MA_PERIOD = 50
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERSOUGHT = 70
VOLUME_AVG_PERIOD = 20

# === v11.0 "Yatay Piyasa" (Ranging) Stratejisi Parametreleri ===
RANGING_RSI_PERIOD = 14
RANGING_RSI_OVERSOLD = 30
RANGING_RSI_OVERBOUGHT = 70

# === KASA DOKTRİNİ (v21.2 - SÜPER ÖZELLİK #2) ===
MAX_CONCURRENT_POSITIONS = 2
LEVERAGE = 10

# --- SÜPER ÖZELLİK #2: DİNAMİK POZİSYON BOYUTU (v21.2) ---
# (Eğer True ise, bot 'RISK_PER_TRADE_PERCENT' ayarını kullanarak 
# 'Volatilite' (ATR) ve 'SL' mesafesine göre pozisyon boyutunu 
# otonom olarak (otomatik) hesaplar.)
USE_DYNAMIC_POSITION_SIZING = True
# (Dinamik Boyutlandırma AÇIK (True) ise kullanılır)
# Kasa başına % kaç risk alınacağını belirler (örn: 0.02 = %2)
RISK_PER_TRADE_PERCENT = 0.02

# (Eğer USE_DYNAMIC_POSITION_SIZING = False (Kapalı) ise, 
# bu 'Statik' (v5.3) ayar kullanılır.)
POSITION_SIZE_PERCENT = 0.50 # Kasanın %50'si (örn: 1000$ kasanın 500$'ı)

# === KAR/ZARAR HEDEFLERİ (v6.1 - Öğrenilmiş Parametreler) ===
# (Eğer USE_DYNAMIC_SLTP = False ise bu 'Statik' ayarlar kullanılır)
STOP_LOSS_PERCENT = 0.015  # %1.5
TAKE_PROFIT_PERCENT = 0.03 # %3.0

# === SÜPER ÖZELLİK #1: DİNAMİK SL/TP (v21.1) ===
# (Eğer True ise, 'trade_manager.py' 'strategy.py'den gelen ATR (Volatilite)
# verisini kullanarak SL/TP'yi dinamik olarak belirler.)
USE_DYNAMIC_SLTP = True
# SL = Fiyat - (ATR * Çarpan) (örn: Volatilitenin 2 katı)
ATR_STOP_LOSS_MULTIPLIER = 2.0
# TP = Fiyat + (ATR * Çarpan) (örn: Volatilitenin 4 katı)
ATR_TAKE_PROFIT_MULTIPLIER = 4.0

# === v13.0 KORELASYONLU RİSK YÖNETİMİ ===
CORRELATION_CHECK_ENABLED = True
CORRELATION_THRESHOLD = 0.80
CORRELATION_KLINE_LIMIT = 500

# === LOGLAMA AYARLARI (v21.0 Güncellemesi) ===
LOG_LEVEL = "INFO"
# 'logger.py' tarafından kullanılan, botun 'iç' log dosyası
CORE_LOG_FILE = "binai_runtime.log" 
# NOT: 'binai_main_runtime.log' ve 'binai_optimizer_runtime.log' dosyaları
# 'run.py' (v2) tarafından otomatik olarak yönetilir (Bunlar stdout/stderr loglarıdır).