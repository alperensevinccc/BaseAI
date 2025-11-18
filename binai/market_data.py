"""
BaseAI - BinAI v21.0 Mimarisi
"Veri Hattı" (Data Pipeline) ve Borsa Entegrasyonu (Enterprise Core)

v21.0 Yükseltmeleri (Enterprise+++):
- "API Önbellekleme" (Caching): 'get_tradable_symbols' ve 'get_exchange_rules' 
  artık 'client.futures_exchange_info()' API'sini ayrı ayrı çağırmıyor.
  Bunun yerine, 'exchange_info' verisini 5 dakika boyunca RAM'de (bellekte) 
  saklayan '_get_exchange_info_with_caching' (v21.0) fonksiyonunu 
  kullanıyorlar. Bu, açılış hızını artırır ve API limitlerini korur.
- Birleşik (Unified) 'get_klines' (v21.0):
  v19.0 "Derin Evrim" mantığındaki "limit - 1" hatası (bug) düzeltildi.
  "Sığ" (limit < 1500) ve "Derin" (limit > 1500) mantığı, *tek bir* birleşik (unified) fonksiyonda birleştirildi. Bu, 'limit' ne olursa olsun 
  *her zaman* 'limit + 1' mum çeker ve 'limit' adet kapanmış mum döndürür.
"""

from binance.client import Client
from binance.exceptions import BinanceAPIException
import time
import numpy as np # v21.0 'get_klines' için gerekli
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
# Önbelleği 5 dakikada bir yenile (API limitleri için)
EXCHANGE_INFO_CACHE_TTL_SECONDS = 300 


def get_binance_client() -> Optional[Client]:
    """
    config.py'deki ayarlara göre Testnet veya Üretim client'ı döndürür.
    v22.3: 'recvWindow' parametresi MANUEL olarak ayarlandı (Kütüphane bug'ını aşmak için).
    """
    try:
        # v22.1: Zaman Senkronizasyonu için tolerans
        RECV_WINDOW = 60000 

        if config.USE_TESTNET:
            log.warning("Sistem TESTNET modunda çalışıyor.")
            # 1. Client'ı SADECE API key'ler ile başlat (extra parametre verme)
            client = Client(config.TESTNET_API_KEY, config.TESTNET_API_SECRET, testnet=True)
            client.API_URL = "https://testnet.binancefuture.com/fapi"
        else:
            log.warning("DİKKAT: Sistem ÜRETİM (GERÇEK PARA) modunda çalışıyor.")
            # 1. Client'ı SADECE API key'ler ile başlat (extra parametre verme)
            client = Client(config.API_KEY, config.API_SECRET)
            client.API_URL = "https://fapi.binance.com/fapi"

        # 2. 'recvWindow' ayarını MANUEL olarak yapılandır
        # (Bu yöntem, kütüphanenin __init__ fonksiyonundaki hatayı atlatır)
        client.recv_window = RECV_WINDOW
        
        # API Anahtarlarını ve Bağlantıyı Doğrula
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
    v21.0 (YENİ): 'exchange_info' verisini 5 dakika boyunca RAM'de (bellekte)
    önbelleğe alan (cache) özel (private) fonksiyon.
    """
    global _exchange_info_cache, _exchange_info_timestamp
    current_time = time.time()
    
    # 1. Önbellek (Cache) geçerli mi?
    if _exchange_info_cache and (current_time - _exchange_info_timestamp) < EXCHANGE_INFO_CACHE_TTL_SECONDS:
        log.info("Borsa (Exchange Info) kuralları ÖNBELLEK'ten (RAM v21.0) okundu.")
        return _exchange_info_cache
        
    # 2. Önbellek (Cache) geçersiz veya boş. API'den çek.
    log.info("Borsa (Exchange Info) kuralları API'den çekiliyor (Önbellek (v21.0) yenileniyor)...")
    try:
        exchange_info = client.futures_exchange_info()
        
        # Önbelleği (Cache) güncelle
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
    'config.py' ayarlarına göre piyasayı tarar veya beyaz listeyi kullanır.
    v21.0: Artık 'exchange_info' verisini API'den değil, 
    'Önbellek'ten (Cache v21.0) okur.
    """
    
    if not client:
        log.error("İstemci (client) mevcut değil. Semboller alınamıyor.")
        return []

    if not config.MARKET_SCAN_ENABLED:
        log.info(f"Piyasa tarama kapalı. Statik liste kullanılıyor: {config.SYMBOLS_WHITELIST}")
        return config.SYMBOLS_WHITELIST

    log.info("Dinamik piyasa tarama başlatıldı...")
    try:
        # === v21.0 YÜKSELTMESİ (Önbellek Okuması) ===
        exchange_info = _get_exchange_info_with_caching(client)
        if not exchange_info:
            log.error("Piyasa tarama başarısız (Exchange Info alınamadı).")
            return []
        # === YÜKSELTME SONU ===
            
        ticker_data = client.futures_ticker()

        tradable_symbols = []
        
        # Ticker verisini sembole göre haritala (hızlı erişim için)
        ticker_map = {ticker['symbol']: ticker for ticker in ticker_data}

        for s in exchange_info['symbols']:
            symbol = s['symbol']
            
            # Sadece 'TRADING' (Ticarette) olan ve 'USDT' ile bitenleri al
            if s['status'] != 'TRADING' or not symbol.endswith('USDT'):
                continue
            
            # Kara listedekileri atla
            if symbol in config.SYMBOLS_BLACKLIST:
                continue

            # Hacim (Volume) kontrolü
            if symbol in ticker_map:
                volume_usdt = float(ticker_map[symbol].get('quoteVolume', 0))
                
                if volume_usdt >= config.MIN_24H_VOLUME_USDT:
                    tradable_symbols.append(symbol)
                else:
                    pass # Hacim (Volume) düşük, atla
            
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
    Belirli bir sembol için mum verilerini (klines) çeker.
    
    v21.0 "Birleşik (Unified) Derin Evrim" Yükseltmesi:
    v19.0'daki 'limit-1' hatası (bug) düzeltildi.
    Artık 'limit' ne olursa olsun (100 veya 15000), 'limit + 1' mum 
    çekilir ve 'limit' adet *kapanmış* mum döndürülür.
    """
    
    # (v19.0: Binance API'sinin maksimum limiti 1500'dür)
    API_MAX_LIMIT = 1500
    
    try:
        all_klines = []
        
        # v21.0: Her zaman 'limit + 1' mum hedefle (son kapanmamış mumu atmak için)
        klines_needed = limit + 1
        
        # (örn: 15001 / 1500 = 10.0006 -> 11 döngü)
        loops_required = int(np.ceil(klines_needed / API_MAX_LIMIT))
        
        # (v19.0: Binance API'si 'endTime' (Bitiş Zamanı) gerektirir)
        end_time = int(time.time() * 1000)
        
        log.debug(f"v21.0 'Birleşik Evrim': {symbol} için {klines_needed} mum ({loops_required} döngü) çekiliyor...")
            
        for i in range(loops_required):
            
            # Bu döngüde ne kadar çekeceğiz?
            # (örn: Kalan 15001, Maks 1500 -> 1500 çek)
            # (örn: Kalan 1, Maks 1500 -> 1 çek)
            limit_to_fetch = min(klines_needed, API_MAX_LIMIT)
            
            log.debug(f"v21.0 'Birleşik Evrim': {symbol} (Döngü {i+1}/{loops_required}, {limit_to_fetch} mum isteniyor)...")
            
            klines_segment = client.futures_klines(
                symbol=symbol, 
                interval=interval, 
                limit=limit_to_fetch,
                endTime=end_time
            )
            
            if not klines_segment:
                log.warning(f"{symbol} için (Döngü {i+1}) veri (segment) bulunamadı. Erken çıkılıyor.")
                break # Veri yoksa döngüden çık
            
            # Toplam listeye ekle (başa ekle)
            all_klines = klines_segment + all_klines
            
            # Bir sonraki döngü için 'endTime'ı bu segmentin 'startTime'ı yap
            # (İlk mumun Açılış Zamanı - 1 milisaniye)
            end_time = klines_segment[0][0] - 1
            
            # İhtiyaç duyulan mum sayısını azalt
            klines_needed -= len(klines_segment)
            if klines_needed <= 0:
                break # İhtiyacımız olan tüm mumları (ve fazlasını) aldık
        
        # v21.0 Düzeltmesi: Her zaman 'son (kapanmamış)' mumu at
        # (ve tam olarak 'limit' (örn: 100 veya 15000) adet mum döndür)
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
    Dinamik hassasiyet (precision) kurallarını (Miktar/Fiyat) döndürür.
    v21.0: Artık 'exchange_info' verisini API'den değil, 
    'Önbellek'ten (Cache v21.0) okur.
    """
    
    if not client:
        log.error("İstemci (client) mevcut değil. Borsa kuralları alınamıyor.")
        return None
        
    try:
        # === v21.0 YÜKSELTMESİ (Önbellek Okuması) ===
        exchange_info = _get_exchange_info_with_caching(client)
        if not exchange_info:
            log.error("Borsa kuralları başarısız (Exchange Info alınamadı).")
            return None
        # === YÜKSELTME SONU ===
            
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