"""
BaseAI - BinAI v21.0 Mimarisi
"Hafıza" (Veritabanı) Yöneticisi (Enterprise Core)

v21.0 Yükseltmeleri (Enterprise+++):
- "Asenkron Yazıcı Sırası" (Async Writer Queue):
  'check_same_thread=False' (Tehlikeli) kaldırıldı. Artık tüm 'YAZMA' 
  (INSERT/REPLACE) işlemleri, 'queue.Queue' (Sıra) üzerinden çalışan
  özel bir 'Yazıcı Thread' (Writer Thread) tarafından %100 'thread-safe' 
  (güvenli) ve 'asenkron' (non-blocking) olarak yönetilir.
- Performans: 'YAZMA' işlemleri (log_trade, save_params) artık 'disk I/O' 
  beklemez, 'RAM' hızında (queue.put) çalışır.
- Esnek (JSONB) Strateji Hafızası: 'strategy_params' tablosu artık 
  'params_json TEXT' sütunu kullanır. 'Optimizer' (Evrim Motoru) artık
  'ADX', 'RSI' veya 'ATR' gibi *herhangi* bir parametreyi 
  DB'ye (Hafıza) kaydedebilir.
"""

import sqlite3
import os
import threading
import queue
import json
import time
from typing import Dict, Any, Optional

# === BİNAİ MODÜLLERİ ===
try:
    from binai.logger import log
except ImportError as e:
    print(f"KRİTİK HATA (db_manager.py): BinAI modülleri bulunamadı. {e}")
    sys.exit(1)


# === v21.0 VERİTABANI YOLU ===
DB_NAME = "binai_tradelog.db"
# Bu dosyanın (db_manager.py) bulunduğu konumu temel alır
DB_PATH = os.path.join(os.path.dirname(__file__), DB_NAME)

# === v21.0 ASENKRON YAZICI SIRASI (Enterprise Queue) ===
_db_write_queue: queue.Queue = queue.Queue()
_db_writer_thread: Optional[threading.Thread] = None
_writer_thread_running = False

def get_db_connection(is_writer_thread: bool = False):
    """
    Veritabanı bağlantısı oluşturur.
    v21.0: 'check_same_thread=False' (TEHLİKELİ) kaldırıldı.
    'Yazıcı Thread' (Writer Thread) 'timeout' (zaman aşımı) ile 
    kalıcı bir bağlantı kullanır.
    """
    try:
        if is_writer_thread:
            # Yazıcı Thread'in özel bağlantısı (Kalıcı)
            conn = sqlite3.connect(DB_PATH, timeout=10.0)
        else:
            # Okuyucu Thread'lerin bağlantısı (Geçici, Sadece Okuma)
            conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=True)
            
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError as e:
        # v21.0: 'mode=ro' (Sadece Okuma) modu, DB dosyası yoksa hata verir.
        # Bu 'initialize_database' tarafından düzeltilir.
        if "unable to open database file" in str(e) and not is_writer_thread:
            log.warning("DB (Hafıza) dosyası henüz 'Yazıcı' (Writer) tarafından oluşturulmadı. Okuma (Read) atlanıyor.")
            return None
        log.critical(f"Veritabanı bağlantı hatası (get_db_connection): {e}")
        raise e


def _db_writer_loop():
    """
    v21.0 (YENİ): Bu 'özel' (dedicated) thread, 'Sıra'dan (Queue) 
    gelen YAZMA işlerini GÜVENLE (tek tek) işler.
    """
    global _writer_thread_running
    log.info("v21.0: Veritabanı 'Yazıcı Thread' (DB Writer Thread) başlatıldı.")
    
    conn = None
    try:
        conn = get_db_connection(is_writer_thread=True)
        cursor = conn.cursor()
        _writer_thread_running = True
        log.info("v21.0: 'Yazıcı Thread' (Writer Thread) veritabanına bağlandı. İşler bekleniyor...")

        while _writer_thread_running:
            try:
                # 'Sıra'dan (Queue) bir iş (task) al (Bloklar)
                task = _db_write_queue.get()

                if task is None: # 'None' (Zehirli Hap) = Kapatma Sinyali
                    log.info("v21.0: 'Yazıcı Thread' (Writer Thread) kapatma sinyali (None) aldı.")
                    _writer_thread_running = False
                    continue

                # === İŞ YÖNLENDİRİCİSİ (Task Router) ===
                task_type, payload = task

                if task_type == "log_trade":
                    # Görev: Kapanan işlemi kaydet
                    cursor.execute("""
                        INSERT INTO trades (symbol, position_side, quantity, entry_price, pnl_usdt, close_reason)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, payload)
                    log.debug(f"v21.0 Yazıcı: 'trades' tablosuna kayıt yapıldı: {payload[0]}")

                elif task_type == "save_params":
                    # Görev: Strateji parametresini kaydet (v21.0 JSON)
                    symbol, params_json = payload
                    cursor.execute("""
                        REPLACE INTO strategy_params (symbol, params_json, last_optimized)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    """, (symbol, params_json))
                    log.debug(f"v21.0 Yazıcı: 'strategy_params' tablosuna kayıt yapıldı: {symbol}")
                
                # Değişiklikleri 'Toplu' (Batch) olarak kaydet
                conn.commit()

            except queue.Empty:
                continue # Bu normalde 'get(block=True)' ile olmaz
            except Exception as e:
                log.error(f"v21.0: 'Yazıcı Thread' (Writer Thread) döngü hatası: {e}", exc_info=True)
                # Hatayı logla ama çöKME
                time.sleep(1)

    except Exception as e:
        log.critical(f"v21.0: 'Yazıcı Thread' (Writer Thread) BAŞLATILAMADI: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()
        _writer_thread_running = False
        log.info("v21.0: Veritabanı 'Yazıcı Thread' (DB Writer Thread) durduruldu.")


def _start_db_writer_thread():
    """v21.0 (YENİ): 'Yazıcı Thread'i (Writer Thread) 'daemon' olarak başlatır."""
    global _db_writer_thread
    if _db_writer_thread is None or not _db_writer_thread.is_alive():
        _db_writer_thread = threading.Thread(target=_db_writer_loop, daemon=True)
        _db_writer_thread.start()

def shutdown_db_writer():
    """
    v21.0 (YENİ): 'main.py' tarafından 'temiz kapatma' (graceful shutdown) 
    için çağrılmalıdır.
    """
    if not _writer_thread_running:
        log.info("v21.0: 'Yazıcı Thread' (Writer Thread) zaten çalışmıyor.")
        return
        
    log.info("v21.0: 'Yazıcı Thread'e (Writer Thread) kapatma sinyali (None) gönderiliyor...")
    _db_write_queue.put(None)
    
    if _db_writer_thread:
        # Thread'in işlerini bitirip kapanmasını bekle (Max 5sn)
        _db_writer_thread.join(timeout=5)
        if _db_writer_thread.is_alive():
            log.error("v21.0: 'Yazıcı Thread' (Writer Thread) 5 saniyede kapanmadı!")

# === 'trades' (Ticaretler) TABLOSU ===

def initialize_database():
    """
    Veritabanını ve 'trades' tablosunu (yoksa) oluşturur.
    v21.0: Artık 'Yazıcı Thread'i (Writer Thread) de başlatır.
    """
    log.info(f"Veritabanı başlatılıyor... Yol: {DB_PATH}")
    try:
        # v21.0: 'Yazıcı' (Writer) olarak bağlan (dosyayı oluşturmak için)
        conn = get_db_connection(is_writer_thread=True)
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
        
        # v21.0: Strateji tablosunu da başlat
        initialize_strategy_db()
        
        # v21.0: "Yazıcı Thread"i (Writer Thread) başlat
        _start_db_writer_thread()
        
    except Exception as e:
        log.critical(f"Veritabanı başlatılamadı: {e}", exc_info=True)

def log_trade_to_db(symbol: str, side: str, qty: float, entry_price: float, pnl: float, reason: str):
    """
    v21.0 (HIZLI): Kapanan bir işlemi 'Sıra'ya (Queue) atar. (Diski beklemez)
    """
    log.info(f"Veritabanına kayıt için 'Sıra'ya (Queue) alınıyor: {symbol} | PNL: {pnl}")
    try:
        payload = (symbol, side, qty, entry_price, pnl, reason)
        _db_write_queue.put(("log_trade", payload))
    except Exception as e:
        log.error(f"Veritabanı 'Sıra' (Queue) hatası ({symbol}): {e}", exc_info=True)

# === 'strategy_params' (Strateji Parametreleri) TABLOSU ===

def initialize_strategy_db():
    """
    v12.0: "Varlığa Özel Optimizasyon" (Per-Asset) Hafızasını başlatır
    v21.0: Artık 'Esnek (JSONB) Schema' kullanır.
    """
    log.info("Strateji Parametreleri (v21.0 JSON) veritabanı başlatılıyor...")
    try:
        conn = get_db_connection(is_writer_thread=True)
        cursor = conn.cursor()
        
        # === v21.0 YÜKSELTMESİ (JSONB) ===
        # (v12.0'daki 'fast_ma_period' gibi sabit sütunlar kaldırıldı)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategy_params (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL UNIQUE,
            params_json TEXT NOT NULL,
            last_optimized DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # === YÜKSELTME SONU ===
        
        conn.commit()
        conn.close()
        log.info("Strateji Parametreleri ('strategy_params' v21.0) tablosu başarıyla doğrulandı/oluşturuldu.")
    except Exception as e:
        log.error(f"Strateji Parametreleri veritabanı başlatılamadı: {e}", exc_info=True)

def save_strategy_params(symbol: str, params: Dict[str, Any]):
    """
    v21.0 (HIZLI): Optimizer'ın bulduğu parametreleri (dict) 
    JSON'a çevirir ve 'Sıra'ya (Queue) atar. (Diski beklemez)
    """
    log.info(f"Strateji Hafızası (v21.0) 'Sıra'ya (Queue) alınıyor: {symbol}")
    try:
        # Parametre sözlüğünü (dict) JSON metnine (string) çevir
        params_json = json.dumps(params)
        payload = (symbol, params_json)
        
        # 'Sıra'ya (Queue) at
        _db_write_queue.put(("save_params", payload))
        
    except Exception as e:
        log.error(f"Strateji Hafızası (v21.0) 'Sıra' (Queue) hatası ({symbol}): {e}", exc_info=True)

def get_strategy_params(symbol: str) -> Optional[Dict[str, Any]]:
    """
    v21.0 (OKUMA): Canlı botun o sembole ait özel parametreleri
    (JSON) okumasını sağlar.
    (Bu, 'Sıra'yı (Queue) kullanmaz, 'OKUMA' (READ) işlemi yapar.)
    """
    log.debug(f"Strateji Hafızası (v21.0) okunuyor: {symbol}")
    
    conn = None
    try:
        # v21.0: 'Sadece Okuma' (Read-Only) bağlantısı al
        conn = get_db_connection(is_writer_thread=False)
        if conn is None:
            log.warning("Strateji Hafızası (v21.0) okunamadı (DB henüz oluşturulmamış olabilir).")
            return None
            
        cursor = conn.cursor()
        
        # v21.0: JSON sütununu seç
        cursor.execute("SELECT params_json FROM strategy_params WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        conn.close() # Okuma (Read) bitti, bağlantıyı hemen kapat
        
        if row and row["params_json"]:
            log.debug(f"{symbol} için özel (optimize edilmiş) parametreler bulundu.")
            # JSON metnini (string) tekrar sözlüğe (dict) çevir
            return json.loads(row["params_json"])
        else:
            log.debug(f"{symbol} için özel parametre bulunamadı. config.py (varsayılan) kullanılacak.")
            return None
            
    except Exception as e:
        if conn:
            conn.close()
        log.error(f"Strateji Hafızası (v21.0) okuma hatası ({symbol}): {e}", exc_info=True)
        return None