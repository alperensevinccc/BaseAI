from binance.client import Client
from binance.exceptions import BinanceAPIException
import config
from logger import log

def get_binance_client():
    # config.py'deki ayarlara göre Testnet veya Üretim client'ı döndürür
    try:
        if config.USE_TESTNET:
            log.warning("Sistem TESTNET modunda çalışıyor.")
            client = Client(config.TESTNET_API_KEY, config.TESTNET_API_SECRET, testnet=True)
            # testnet=True Spot testnet'i ayarlar. URL'leri Futures için manuel ezmeliyiz.
            client.API_URL = "https://testnet.binancefuture.com/fapi"
            client.API_URL_PRIVATE = "https://testnet.binancefuture.com/fapi"
        else:
            log.warning("DİKKAT: Sistem ÜRETİM (GERÇEK PARA) modunda çalışıyor.")
            client = Client(config.API_KEY, config.API_SECRET)
            client.API_URL = "https://fapi.binance.com/fapi"
            client.API_URL_PRIVATE = "https://fapi.binance.com/fapi"
        
        # === KOD DÜZELTMESİ (APIError -5000) ===
        client.futures_ping()
        # === DÜZELTME SONU ===
        
        log.info("Binance API bağlantısı başarılı.")
        return client
    except BinanceAPIException as e:
        log.error(f"Binance API bağlantı hatası: {e}")
        return None
    except Exception as e:
        log.error(f"Genel istemci oluşturma hatası: {e}")
        return None

def get_tradable_symbols(client):
    # 'config.py' ayarlarına göre piyasayı tarar veya beyaz listeyi kullanır
    
    if not client:
        log.error("İstemci mevcut değil. Semboller alınamıyor.")
        return []

    if not config.MARKET_SCAN_ENABLED:
        log.info(f"Piyasa tarama kapalı. Statik liste kullanılıyor: {config.SYMBOLS_WHITELIST}")
        return config.SYMBOLS_WHITELIST

    log.info("Dinamik piyasa tarama başlatıldı...")
    try:
        # Tüm f-USDT piyasalarını al
        exchange_info = client.futures_exchange_info()
        ticker_data = client.futures_ticker()

        tradable_symbols = []
        
        # Ticker verisini sembole göre haritala (hızlı erişim için)
        ticker_map = {ticker['symbol']: ticker for ticker in ticker_data}

        for s in exchange_info['symbols']:
            symbol = s['symbol']
            
            if s['status'] != 'TRADING' or not symbol.endswith('USDT'):
                continue
                
            if symbol in config.SYMBOLS_BLACKLIST:
                continue

            if symbol in ticker_map:
                volume_usdt = float(ticker_map[symbol].get('quoteVolume', 0))
                
                if volume_usdt >= config.MIN_24H_VOLUME_USDT:
                    tradable_symbols.append(symbol)
                else:
                    pass 
            
        log.info(f"Tarama tamamlandı. Hacim eşiğini (>{config.MIN_24H_VOLUME_USDT} USDT) geçen {len(tradable_symbols)} sembol bulundu.")
        return tradable_symbols

    except BinanceAPIException as e:
        log.error(f"Piyasa tarama sırasında API hatası: {e}")
        return []
    except Exception as e:
        log.error(f"Piyasa tarama sırasında genel hata: {e}")
        return []

def get_klines(client, symbol, interval, limit=100):
    """
    Belirli bir sembol için mum verilerini (klines) çeker.
    
    v19.0 "Derin Evrim" Yükseltmesi:
    Binance API'si tek seferde 1500 mum (maks) verir.
    'limit' (örn: 15000) 1500'den büyükse,
    bu fonksiyon 'limit'e (15000) ulaşana kadar
    otonom olarak (döngüsel olarak) API'yi çağırır.
    """
    
    # (v19.0: Binance API'sinin maksimum limiti 1500'dür)
    API_MAX_LIMIT = 1500 
    
    try:
        all_klines = []
        
        # Gereken mum (limit) (örn: 15000) 1500'den büyük mü?
        if limit > API_MAX_LIMIT:
            # Evet. "Derin Evrim" (v19.0) döngüsü gerekli.
            log.info(f"v19.0 'Derin Evrim': {symbol} için {limit} mum (API Limiti Aşıldı) çekiliyor...")
            
            # (15000 / 1500 = 10 döngü)
            loops_required = int(np.ceil(limit / API_MAX_LIMIT))
            
            # (v19.0: Binance API'si 'endTime' (Bitiş Zamanı) gerektirir)
            end_time = int(time.time() * 1000)
            
            for i in range(loops_required):
                log.debug(f"v19.0 'Derin Evrim': {symbol} (Döngü {i+1}/{loops_required})...")
                
                klines_segment = client.futures_klines(
                    symbol=symbol, 
                    interval=interval, 
                    limit=API_MAX_LIMIT,
                    endTime=end_time
                )
                
                if not klines_segment:
                    break # Veri yoksa döngüden çık
                
                # Toplam listeye ekle (başa ekle)
                all_klines = klines_segment + all_klines
                
                # Bir sonraki döngü için 'endTime'ı bu segmentin 'startTime'ı yap
                end_time = klines_segment[0][0] - 1 # (İlk mumun Açılış Zamanı - 1ms)
            
            # (v19.0: Son (kapanmamış) mumu at)
            return all_klines[-(limit+1):-1]
            
        else:
            # Hayır. "Sığ Evrim" (v12.4) (Sadece 1500 mum veya daha az)
            klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit + 1)
            # Son (kapanmamış) mumu at
            return klines[:-1]
            
    except BinanceAPIException as e:
        log.error(f"{symbol} için mum verisi çekilemedi: {e}")
        return []
    except Exception as e:
        log.error(f"{symbol} için 'Derin Evrim' (v19.0) döngüsü hatası: {e}")
        return []

def get_exchange_rules(client):
    # Dinamik hassasiyet onarımı (Hata -1111 ve -4012)
    log.info("Borsa (Exchange Info) kuralları alınıyor...")
    try:
        exchange_info = client.futures_exchange_info()
        rules = {} 
        for s in exchange_info['symbols']:
            rules[s['symbol']] = {
                "quantityPrecision": s['quantityPrecision'],
                "pricePrecision": s['pricePrecision']
            }
        
        log.info(f"{len(rules)} sembol için miktar/fiyat hassasiyeti kuralları yüklendi.")
        return rules
    except BinanceAPIException as e:
        log.error(f"Borsa kuralları alınamadı (API): {e}")
        return None
    except Exception as e:
        log.error(f"Borsa kuralları alınamadı (Genel): {e}")
        return None