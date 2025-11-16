import sqlite3
from logger import log
import os

DB_NAME = "binai_tradelog.db"
DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)

def get_db_connection():
    # Veritabanı bağlantısı oluştur veya mevcut olana bağlan
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    # Veritabanını ve 'trades' tablosunu (yoksa) oluşturur
    log.info(f"Veritabanı başlatılıyor... Yol: {DB_PATH}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT NOT_NULL,
            position_side TEXT NOT_NULL,
            quantity REAL NOT_NULL,
            entry_price REAL NOT_NULL,
            pnl_usdt REAL NOT_NULL,
            close_reason TEXT NOT_NULL
        )
        """)
        
        conn.commit()
        conn.close()
        log.info("Veritabanı ('trades' tablosu) başarıyla doğrulandı/oluşturuldu.")
    except Exception as e:
        log.error(f"Veritabanı başlatılamadı: {e}")

def log_trade_to_db(symbol, side, qty, entry_price, pnl, reason):
    # Kapanan bir işlemi veritabanına kaydeder
    log.info(f"Veritabanına kayıt: {symbol} | PNL: {pnl}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO trades (symbol, position_side, quantity, entry_price, pnl_usdt, close_reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (symbol, side, qty, entry_price, pnl, reason))
        
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Veritabanı kayıt hatası ({symbol}): {e}")

def initialize_strategy_db():
    # v12.0: "Varlığa Özel Optimizasyon" (Per-Asset) Hafızasını başlatır
    log.info("Strateji Parametreleri (v12.0) veritabanı başlatılıyor...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategy_params (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL UNIQUE,
            fast_ma_period INTEGER,
            slow_ma_period INTEGER,
            stop_loss_percent REAL,
            take_profit_percent REAL,
            last_optimized DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()
        conn.close()
        log.info("Strateji Parametreleri ('strategy_params' tablosu) başarıyla doğrulandı/oluşturuldu.")
    except Exception as e:
        log.error(f"Strateji Parametreleri veritabanı başlatılamadı: {e}")

def save_strategy_params(symbol, params):
    # v12.0: Optimizer'ın bulduğu en iyi parametreleri kaydeder
    log.info(f"Strateji Hafızası (v12.0) güncelleniyor: {symbol}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Otonom Evrim: Varolan kaydı sil ve yenisini (daha kârlısını) ekle
        # (REPLACE INTO, UNIQUE(symbol) kısıtlamasına dayanır)
        cursor.execute("""
        REPLACE INTO strategy_params (
            symbol, fast_ma_period, slow_ma_period, 
            stop_loss_percent, take_profit_percent, last_optimized
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            symbol,
            params.get('FAST_MA_PERIOD'),
            params.get('SLOW_MA_PERIOD'),
            params.get('STOP_LOSS_PERCENT'),
            params.get('TAKE_PROFIT_PERCENT')
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Strateji Hafızası (v12.0) kayıt hatası ({symbol}): {e}")

def get_strategy_params(symbol):
    # v12.0: Canlı botun (v12.0) o sembole ait özel parametreleri okumasını sağlar
    log.debug(f"Strateji Hafızası (v12.0) okunuyor: {symbol}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM strategy_params WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            log.debug(f"{symbol} için özel (optimize edilmiş) parametreler bulundu.")
            return dict(row) # Sözlük (dict) olarak döndür
        else:
            log.debug(f"{symbol} için özel parametre bulunamadı. config.py (varsayılan) kullanılacak.")
            return None
            
    except Exception as e:
        log.error(f"Strateji Hafızası (v12.0) okuma hatası ({symbol}): {e}")
        return None