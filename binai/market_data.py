"""
BaseAI - BinAI v22.4 Mimarisi (FINAL AGRESİF DÜZELTME)
"Veri Hattı" (Data Pipeline) ve Borsa Entegrasyonu (Enterprise Core)

v22.4 Yükseltmeleri (Enterprise+++):
- KESİN ZAMAN SENKRONİZASYONU: '-1022 Signature' hatasını önlemek için, 
  Client oluşturulduktan HEMEN SONRA sunucu saatiyle senkronize edilir 
  (timestamp_offset) ve 'recvWindow' MANUEL olarak atanır.
- Bu yöntem, 'python-binance' kütüphanesinin 'init' hatalarını bypass eder.
"""

from binance.client import Client
from binance.exceptions import BinanceAPIException
import time
import numpy as np 
from typing import Optional, Dict, List, Any

# === BİNAİ MODÜLLERİ ===
try:
    from binai import config
    from binai.logger import log
except ImportError as e:
    print(f"KRİTİK HATA (market_data.py): BinAI modülleri bulunamadı. {e}")
    sys.exit(1)


# === v21.0 API ÖNBELLEĞİ (Enterprise Caching) ===
_exchange_info_cache: Optional[Dict[str, Any]] = None
_exchange_info_timestamp: float = 0.0
EXCHANGE_INFO_CACHE_TTL_SECONDS = 300 


def get_binance_client() -> Optional[Client]:
    """
    config.py'deki ayarlara göre Testnet veya Üretim client'ı döndürür.
    v22.4: 'recvWindow' ve 'Time Sync' ayarları MANUEL ve GÜVENLİ şekilde yapılır.
    """
    try:
        # v22.1: Zaman Senkronizasyonu için 60 saniye tolerans
        RECV_WINDOW = 60000 

        # 1. İstemciyi (Client) En Basit Şekilde Başlat (Hatasız)
        if config.USE_TESTNET:
            log.warning("Sistem TESTNET modunda çalışıyor.")
            # 'requests_params' veya 'recvWindow' parametresi VERME! (Hata kaynağı)
            client = Client(config.TESTNET_API_KEY, config.TESTNET_API_SECRET, testnet=True)
            client.API_URL = "https://testnet.binancefuture.com/fapi"
        else:
            log.warning("DİKKAT: Sistem ÜRETİM (GERÇEK PARA) modunda çalışıyor.")
            client = Client(config.API_KEY, config.API_SECRET)
            client.API_URL = "https://fapi.binance.com/fapi"

        # 2. v22.4 GÜNCELLEMESİ: 'recvWindow' Ayarını Manuel Yap (Injection)
        # Kütüphanenin içindeki 'recv_window' özelliğini doğrudan değiştir.
        client.recv_window = RECV_WINDOW
        
        # 3. v22.4 GÜNCELLEMESİ: Zaman Senkronizasyonu (Time Sync)
        # Sunucu saatini al ve yerel saat ile farkı (offset) hesapla.
        try:
            server_time_res = client.get_server_time()
            server_time = server_time_res['serverTime']
            local_time = int(time.time() * 1000)
            diff = server_time - local_time
            
            # İstemciye zaman farkını (offset) işle
            client.timestamp_offset = diff
            log.info(f"Binance Sunucu Saati Senkronize Edildi. Fark: {diff}ms (recvWindow: {RECV_WINDOW})")
        except Exception as e:
            log.warning(f"Zaman senkronizasyonu sırasında uyarı: {e}")

        # 4. Bağlantıyı Doğrula
        client.futures_ping()
        
        log.info("Binance API bağlantısı başarılı.")
        return client
        
    except BinanceAPIException as e:
        log.critical(f"Binance API bağlantı hatası: {e}. API Anahtarları veya IP Erişimi? Çıkılıyor.", exc_info=True)
        return None
    except Exception as e:
        log.critical(f"Genel istemci (client) oluşturma hatası: {e}. Çıkılıyor.", exc_info=True)
        return None

def _get_exchange_info_with_caching(client: Client) -> Optional[Dict[str, Any]]:
    """
    v21.0: 'exchange_info' verisini 5 dakika boyunca RAM'de saklar.
    """
    global _exchange_info_cache, _exchange_info_timestamp
    current_time = time.time()
    
    if _exchange_info_cache and (current_time - _exchange_info_timestamp) < EXCHANGE_INFO_CACHE_TTL_SECONDS:
        log.info("Borsa (Exchange Info) kuralları ÖNBELLEK'ten (RAM v21.0) okundu.")
        return _exchange_info_cache
        
    log.info("Borsa (Exchange Info) kuralları API'den çekiliyor (Önbellek (v21.0) yenileniyor)...")
    try:
        exchange_info = client.futures_exchange_info()
        _exchange_info_cache = exchange_info
        _exchange_info_timestamp = current_time
        return _exchange_info_cache
    except BinanceAPIException as e:
        log.error(f"Borsa (Exchange Info) kuralları alınamadı (API): {e}")
        return None
    except Exception as e:
        log.error(f"Borsa (Exchange Info) kuralları alınamadı (Genel): {e}", exc_info=True)
        return None

def get_tradable_symbols(client: Client) -> List[str]:
    """
    'config.py' ayarlarına göre piyasayı tarar.
    v21.0: Önbellekli Exchange Info kullanır.
    """
    if not client:
        log.error("İstemci (client) mevcut değil. Semboller alınamıyor.")
        return []

    if not config.MARKET_SCAN_ENABLED:
        log.info(f"Piyasa tarama kapalı. Statik liste kullanılıyor: {config.SYMBOLS_WHITELIST}")
        return config.SYMBOLS_WHITELIST

    log.info("Dinamik piyasa tarama başlatıldı...")
    try:
        exchange_info = _get_exchange_info_with_caching(client)
        if not exchange_info:
            log.error("Piyasa tarama başarısız (Exchange Info alınamadı).")
            return []
            
        ticker_data = client.futures_ticker()
        tradable_symbols = []
        ticker_map = {ticker['symbol']: ticker for ticker in ticker_data}

        for s in exchange_info['symbols']:
            symbol = s['symbol']
            if s['status'] != 'TRADING' or not symbol.endswith('USDT'): continue
            if symbol in config.SYMBOLS_BLACKLIST: continue

            if symbol in ticker_map:
                volume_usdt = float(ticker_map[symbol].get('quoteVolume', 0))
                if volume_usdt >= config.MIN_24H_VOLUME_USDT:
                    tradable_symbols.append(symbol)
            
        log.info(f"Tarama tamamlandı. Hacim eşiğini (>{config.MIN_24H_VOLUME_USDT} USDT) geçen {len(tradable_symbols)} sembol bulundu.")
        return tradable_symbols

    except BinanceAPIException as e:
        log.error(f"Piyasa tarama sırasında API hatası: {e}")
        return []
    except Exception as e:
        log.error(f"Piyasa tarama sırasında genel hata: {e}", exc_info=True)
        return []

def get_klines(client: Client, symbol: str, interval: str, limit: int = 100) -> List[List[Any]]:
    """
    v21.0 "Birleşik (Unified) Derin Evrim": 
    Her zaman 'limit + 1' mum çeker ve 'limit' adet kapanmış mum döndürür.
    """
    API_MAX_LIMIT = 1500
    
    try:
        all_klines = []
        klines_needed = limit + 1
        loops_required = int(np.ceil(klines_needed / API_MAX_LIMIT))
        end_time = int(time.time() * 1000)
        
        log.debug(f"v21.0 'Birleşik Evrim': {symbol} için {klines_needed} mum ({loops_required} döngü) çekiliyor...")
            
        for i in range(loops_required):
            limit_to_fetch = min(klines_needed, API_MAX_LIMIT)
            
            klines_segment = client.futures_klines(
                symbol=symbol, 
                interval=interval, 
                limit=limit_to_fetch,
                endTime=end_time
            )
            
            if not klines_segment:
                log.warning(f"{symbol} için (Döngü {i+1}) veri bulunamadı. Erken çıkılıyor.")
                break 
            
            all_klines = klines_segment + all_klines
            end_time = klines_segment[0][0] - 1
            klines_needed -= len(klines_segment)
            if klines_needed <= 0: break
        
        final_klines = all_klines[-limit:]
        log.debug(f"v21.0 'Birleşik Evrim': {symbol} için {len(final_klines)} adet mum başarıyla çekildi.")
        return final_klines
            
    except BinanceAPIException as e:
        log.error(f"{symbol} için mum verisi çekilemedi: {e}")
        return []
    except Exception as e:
        log.error(f"{symbol} için 'Birleşik Evrim' (v21.0) döngüsü hatası: {e}", exc_info=True)
        return []

def get_exchange_rules(client: Client) -> Optional[Dict[str, Any]]:
    """
    Dinamik hassasiyet (precision) kurallarını döndürür.
    v21.0: Önbellekli Exchange Info kullanır.
    """
    if not client:
        log.error("İstemci (client) mevcut değil. Borsa kuralları alınamıyor.")
        return None
        
    try:
        exchange_info = _get_exchange_info_with_caching(client)
        if not exchange_info:
            log.error("Borsa kuralları başarısız (Exchange Info alınamadı).")
            return None
            
        rules = {} 
        for s in exchange_info['symbols']:
            rules[s['symbol']] = {
                "quantityPrecision": s['quantityPrecision'],
                "pricePrecision": s['pricePrecision']
            }
        
        log.info(f"{len(rules)} sembol için miktar/fiyat hassasiyeti kuralları yüklendi.")
        return rules
        
    except Exception as e:
        log.error(f"Borsa kuralları ayrıştırılamadı (Genel Hata): {e}", exc_info=True)
        return None