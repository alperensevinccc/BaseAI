"""
BaseAI - BinAI v20.3 Mimari Yükseltmesi
"Gerçek Zamanlı (WebSocket) Veri Akışı" (Real-Time Data Pipeline)
(v20.3: "Başlatma Hatası" (AttributeError: .start()) ve "Durdurma Hatası" (stop_socket) onarıldı)
"""
from binance import BinanceSocketManager
import market_data
import config
from logger import log
import threading
import time
from collections import deque
import pandas as pd # v20.3: (Hata düzeltmesi için eklendi)
import numpy as np # v20.3: (Hata düzeltmesi için eklendi)

# === v20.0 "BELLEK İÇİ ÖNBELLEK" (In-Memory Cache) ===
klines_cache = {}
KLINE_CACHE_SIZE = 200 # (Her sembol için son 200 mumu sakla)

_bsm = None
_client = None
_active_streams = []
_lock = threading.Lock()

def _process_kline_message(msg):
    """
    v20.0: WebSocket'ten (Binance) "gerçek zamanlı" (real-time)
    bir mum (kline) mesajı geldiğinde bu fonksiyon tetiklenir.
    """
    try:
        if msg.get('e') == 'error':
            log.error(f"v20.0 WebSocket Hata: {msg.get('m')}")
            return

        k = msg.get('k') # Mum (Kline) verisi
        if not k:
            return 

        symbol = k['s']
        is_closed = k['x'] 

        if is_closed:
            log.debug(f"v20.0 WebSocket: {symbol} mumu kapandı. Önbellek (Cache) güncelleniyor...")
            
            kline_data = [
                k['t'], k['o'], k['h'], k['l'], k['c'], k['v'],
                k['T'], k['q'], k['n'], k['V'], k['Q'], '0'
            ]
            
            with _lock: 
                if symbol not in klines_cache:
                    _initialize_symbol_cache(symbol)
                
                klines_cache[symbol].append(kline_data)

    except Exception as e:
        log.error(f"v20.0 WebSocket: Mum (Kline) mesajı işlenemedi: {e}")

def _initialize_symbol_cache(symbol):
    """
    v20.0: "Bellek İçi Önbellek"i (In-Memory Cache)
    "Geçmiş Veri" (Historical Data) (200 mum) ile doldurur.
    (v20.1: 'global _client' düzeltmesi eklendi)
    """
    global klines_cache, _client # <<< v20.1 HATA DÜZELTMESİ
    
    if not _client:
        _client = market_data.get_binance_client()
        
    try:
        log.info(f"v20.0: Önbellek (Cache) dolduruluyor: {symbol} (İlk 200 mum)...")
        # v19.0 "Derin Evrim" (get_klines) motorunu kullan
        klines_data = market_data.get_klines(_client, symbol, config.INTERVAL, KLINE_CACHE_SIZE)
        
        klines_cache[symbol] = deque(klines_data, maxlen=KLINE_CACHE_SIZE)
        
    except Exception as e:
        log.error(f"v20.0: Önbellek (Cache) doldurma hatası ({symbol}): {e}")
        klines_cache[symbol] = deque(maxlen=KLINE_CACHE_SIZE)

def get_klines_from_cache(symbol):
    """
    v20.0: 'main.py' (v20.0) tarafından 'strategy.py' (v18.1) motorunu
    beslemek (feed) için çağrılır.
    """
    with _lock:
        if symbol not in klines_cache:
            _initialize_symbol_cache(symbol)
            
        return list(klines_cache.get(symbol, []))

def start_websocket_listener():
    """
    v20.0: 'main.py' (v20.0) tarafından "Sonsuz Otonomi" (v15.0)
    döngüsünü (threading) başlatmak için çağrılır.
    """
    global _bsm, _client, _active_streams
    
    log.info("--- [v20.0 'Gerçek Zamanlı' (WebSocket) Motoru Başlatılıyor] ---")
    
    if not _client:
        _client = market_data.get_binance_client()
        if not _client:
            log.error("v20.0 WebSocket: İstemci başlatılamadı.")
            return

    # === [BaseAI Stabilite Protokolü v20.2.3: Proxy Uyumluluk Katmanı] ===
    # (v20.2.3: python-binance'in (v20.2) 'futures_multiplex_socket'
    # fonksiyonunun 'https_proxy' (v20.2) özelliğini gerektirmesi düzeltildi)
    if not hasattr(_client, 'https_proxy'):
        setattr(_client, 'https_proxy', None)
    if not hasattr(_client, 'http_proxy'):
        setattr(_client, 'http_proxy', None)
    # === [Protokol v20.2.3 Sonu] ===

    _bsm = BinanceSocketManager(_client)
    
    # 1. Tüm sembolleri (490+) al
    symbols_to_stream = market_data.get_tradable_symbols(_client)
    if not symbols_to_stream:
        log.error("v20.0 WebSocket: Taranacak sembol bulunamadı.")
        return
        
    # 2. Tüm sembolleri (490+) "Bellek İçi Önbellek"e (In-Memory Cache) (v20.0) doldur
    for symbol in symbols_to_stream:
        if symbol not in klines_cache:
            _initialize_symbol_cache(symbol)
            time.sleep(0.1) # (API Limitlerini (Rate Limit) önle)

    # 3. Tüm semboller (490+) için "Gerçek Zamanlı" (v20.0) akışı (stream) başlat
    streams = [f"{s.lower()}@kline_{config.INTERVAL}" for s in symbols_to_stream]
    
    CHUNK_SIZE = 100 
    for i in range(0, len(streams), CHUNK_SIZE):
        chunk = streams[i:i + CHUNK_SIZE]
        log.info(f"v20.0 WebSocket: {len(chunk)} sembol (Parça {i//CHUNK_SIZE + 1}) dinleniyor...")
        
        # === v20.2 HATA DÜZELTMESİ (AttributeError) ===
        conn_key = _bsm.futures_multiplex_socket(chunk, _process_kline_message)
        # === DÜZELTME SONU ===
        
        _active_streams.append(conn_key)
    
    log.info(f"--- [v20.0 'Gerçek Zamanlı' (WebSocket) Motoru (Toplam {len(streams)} Sembol) Aktif] ---")
    
    # === v20.3 HATA DÜZELTMESİ (AttributeError: .start()) ===
    # HATALI KOD (v20.2): _bsm.start()
    # (v20.3: 'futures_multiplex_socket' (v20.2) otonom olarak (otomatik) başlar.
    # '_bsm.start()' (v20.2) çağırmak 'AttributeError'a neden olur)
    pass
    # === DÜZELTME SONU ===

def stop_websocket_listener():
    if _bsm:
        log.info("v20.0 WebSocket: Durduruluyor...")
        try:
            for conn_key in _active_streams:
                # === v20.3 HATA DÜZELTMESİ (AttributeError: ._stop_socket) ===
                # (v20.3: 'stop_socket' (v20.3) (korumalı olmayan) kullanılır)
                _bsm.stop_socket(conn_key)
                # === DÜZELTME SONU ===
            _bsm.close()
        except Exception as e:
            log.error(f"v20.3 WebSocket: Durdurma hatası: {e}")