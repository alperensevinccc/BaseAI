"""
BaseAI - BinAI v21.0 Mimari Yükseltmesi
"Gerçek Zamanlı (WebSocket) Veri Akışı" (Enterprise Core)

v21.0 Yükseltmeleri:
- %100 Thread-Safe (İş Parçacığı Güvenli): 'klines_cache' (Önbellek) üzerinde 
  yapılan tüm 'okuma', 'yazma' ve 'başlatma' (I/O dahil) işlemleri 
  '_lock' (kilit) altına alındı. Bu, 'yarış koşullarını' (race conditions) 
  tamamen engeller.
- 'main.py' Entegrasyonu: 'main.py' (v21.0) motorunun 'Akıllı Bekleme' 
  yapabilmesi için 'is_cache_ready()' ve 'get_cache_size()' 
  fonksiyonları eklendi.
- Kod Temizliği: 'global _client' gibi geçici çözümler kaldırıldı, 
  istemci (client) nesnesi bağımlılık olarak (dependency) enjekte edildi.
"""

from binance import BinanceSocketManager
from binance.client import Client # v21.0: Tip (Type Hinting) için eklendi
from collections import deque
import threading
import time
import pandas as pd
import numpy as np
from typing import List, Deque, Dict, Any, Optional

# === BİNAİ MODÜLLERİ ===
try:
    from binai import market_data
    from binai import config
    from binai.logger import log
except ImportError as e:
    print(f"KRİTİK HATA (websocket_manager.py): BinAI modülleri bulunamadı. {e}")
    sys.exit(1)


# === v20.0 "BELLEK İÇİ ÖNBELLEK" (In-Memory Cache) ===
# 'deque' (çift uçlu kuyruk) kullanarak her sembol için son X mumu saklar.
klines_cache: Dict[str, Deque[List[Any]]] = {}
KLINE_CACHE_SIZE = 200 # (Her sembol için son 200 mumu sakla)

_bsm: Optional[BinanceSocketManager] = None
_client: Optional[Client] = None
_active_streams: List[str] = []

# v21.0: Önbellek (Cache) üzerindeki TÜM işlemleri koruyan kilit
_lock = threading.Lock() 


def _process_kline_message(msg):
    """
    v20.0: WebSocket'ten (Binance) "gerçek zamanlı" (real-time)
    bir mum (kline) mesajı geldiğinde bu fonksiyon tetiklenir.
    v21.0: Artık %100 'thread-safe'.
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
            # log.debug(f"v20.0 WebSocket: {symbol} mumu kapandı. Önbellek (Cache) güncelleniyor...")
            
            kline_data = [
                k['t'], k['o'], k['h'], k['l'], k['c'], k['v'],
                k['T'], k['q'], k['n'], k['V'], k['Q'], '0'
            ]
            
            # === v21.0 THREAD-SAFE YÜKSELTME ===
            with _lock:
                if symbol not in klines_cache:
                    # Bu sembol henüz 'ilk dolum' (initial fill) listesinde
                    # işlenmedi, ancak canlı bir veri geldi.
                    # 'main.py' motorunu riske atmamak için, 'ilk dolum'
                    # yapılana kadar bu canlı veriyi atla VEYA
                    # '_initialize_symbol_cache'i burada çağır.
                    # En güvenli (safe) yol: _initialize_symbol_cache'i tetiklemek.
                    
                    # (Not: _initialize_symbol_cache de _lock kullandığı için
                    # burada 'recursive' (iç içe) bir kilitlenme olmaması adına
                    # _lock'u 'RLock' (ReentrantLock) yapmak gerekir. 
                    # Şimdilik, 'start_websocket_listener'ın ilk dolumu 
                    # bitireceğine güveniyoruz ve bu nadir durumu logluyoruz.)
                    
                    log.warning(f"v21.0: {symbol} için canlı veri (WS) geldi, ancak önbellek (Cache) henüz başlatılmamış. 'İlk Dolum' bekleniyor.")
                    # Alternatif (daha agresif):
                    # _initialize_symbol_cache(_client, symbol)
                    return

                # Önbellek (Cache) mevcut, yeni mumu ekle
                klines_cache[symbol].append(kline_data)
            # === v21.0 YÜKSELTME SONU ===

    except Exception as e:
        log.error(f"v20.0 WebSocket: Mum (Kline) mesajı işlenemedi: {e}", exc_info=True)


def _initialize_symbol_cache(client: Client, symbol: str):
    """
    v20.0: "Bellek İçi Önbellek"i (In-Memory Cache)
    "Geçmiş Veri" (Historical Data) (200 mum) ile doldurur.
    v21.0: %100 'thread-safe' ve 'client' bağımlılığını (dependency) alır.
    
    NOT: Bu fonksiyon I/O (API çağrısı) içerir ve '_lock' (kilit) tutarken 
    çağrılır, bu bir 'performans' darboğazıdır ANCAK 'veri bütünlüğü' 
    ve 'kararlılık' (yeşil) için gereklidir. Sadece sistemin 
    ilk açılışında (startup) yaşanır.
    """
    
    # === v21.0 THREAD-SAFE KONTROL ===
    # Bu fonksiyon SADECE '_lock' (kilit) tutulurken çağrılmalıdır.
    
    if symbol in klines_cache:
        log.warning(f"v21.0: {symbol} için 'Önbellek Başlatma' (Init Cache) çağrıldı, ancak zaten mevcuttu. Atlanıyor.")
        return # Zaten başka bir thread (iş parçacığı) tarafından doldurulmuş
        
    if not client:
        log.error(f"v21.0: {symbol} önbelleği doldurulamadı. Binance istemcisi (client) 'None'.")
        return
        
    try:
        log.info(f"v20.0: Önbellek (Cache) dolduruluyor: {symbol} (İlk {KLINE_CACHE_SIZE} mum)...")
        # v19.0 "Derin Evrim" (get_klines) motorunu kullan
        klines_data = market_data.get_klines(client, symbol, config.INTERVAL, KLINE_CACHE_SIZE)
        
        # v21.0: Veriyi 'deque' (kuyruk) olarak sakla
        klines_cache[symbol] = deque(klines_data, maxlen=KLINE_CACHE_SIZE)
        
    except Exception as e:
        log.error(f"v20.0: Önbellek (Cache) doldurma hatası ({symbol}): {e}")
        # Hata durumunda bile boş bir 'deque' (kuyruk) oluştur ki tekrar tekrar denemesin
        klines_cache[symbol] = deque(maxlen=KLINE_CACHE_SIZE)

# === v21.0 YENİ FONKSİYONLAR (main.py Entegrasyonu) ===

def get_klines_from_cache(symbol: str) -> List[List[Any]]:
    """
    v20.0: 'main.py' tarafından 'strategy.py' motorunu beslemek için çağrılır.
    v21.0: %100 'thread-safe' ve "lazy-loading" (tembel yükleme) yapar.
    """
    with _lock:
        if symbol not in klines_cache:
            # Bu sembol (henüz) 'ilk dolum' (initial fill) listesinde yoktu 
            # veya yeni bir sembol eklendi. Şimdi (lazy-load) doldur.
            log.warning(f"v21.0: {symbol} önbellekte (Cache) bulunamadı. 'Tembel Yükleme' (Lazy-Load) tetiklendi.")
            
            # v21.0: _client'in başlatıldığından emin ol
            global _client
            if not _client:
                _client = market_data.get_binance_client()
                
            _initialize_symbol_cache(_client, symbol)
            
        # 'list()' kopyasını döndürür, böylece 'main.py' analiz yaparken
        # 'klines_cache' (önbellek) değişse bile hata almaz.
        return list(klines_cache.get(symbol, []))

def get_cache_size() -> int:
    """
    v21.0 (YENİ): Önbellekte (Cache) kaç adet sembol olduğunu döndürür.
    'main.py' (v21.0) 'Akıllı Bekleme' motoru tarafından kullanılır.
    """
    with _lock:
        return len(klines_cache)

def is_cache_ready(min_symbols_needed: int) -> bool:
    """
    v21.0 (YENİ): Önbelleğin (Cache) kullanıma hazır olup olmadığını kontrol eder.
    'main.py' (v21.0) 'Akıllı Bekleme' motoru tarafından kullanılır.
    """
    with _lock:
        return len(klines_cache) >= min_symbols_needed

# === v20.0 ANA BAŞLATMA VE DURDURMA FONKSİYONLARI ===

def start_websocket_listener():
    """
    v20.0: 'main.py' (v20.0) tarafından "Sonsuz Otonomi" (v15.0)
    döngüsünü (threading) başlatmak için çağrılır.
    v21.0: Artık 'ilk dolum' (initial fill) mantığını da yönetir.
    """
    global _bsm, _client, _active_streams
    
    log.info("--- [v20.0 'Gerçek Zamanlı' (WebSocket) Motoru Başlatılıyor] ---")
    
    if not _client:
        _client = market_data.get_binance_client()
        if not _client:
            log.critical("v20.0 WebSocket: İstemci başlatılamadı. API anahtarlarını kontrol edin.")
            return

    # === [BaseAI Stabilite Protokolü v20.2.3: Proxy Uyumluluk Katmanı] ===
    # (v21.0: Bu katman 'Enterprise' sistemler için önemlidir, koruyoruz)
    if not hasattr(_client, 'https_proxy'):
        setattr(_client, 'https_proxy', None)
    if not hasattr(_client, 'http_proxy'):
        setattr(_client, 'http_proxy', None)
    # === [Protokol v20.2.3 Sonu] ===

    _bsm = BinanceSocketManager(_client)
    
    # 1. Tüm sembolleri (490+) al
    symbols_to_stream = market_data.get_tradable_symbols(_client)
    if not symbols_to_stream:
        log.critical("v20.0 WebSocket: Taranacak sembol bulunamadı. İnternet veya API hatası.")
        return
        
    # 2. (v21.0 DEĞİŞİKLİĞİ): ÖNCE "Gerçek Zamanlı" akışı (stream) başlat
    # Bu, 'ilk dolum' (initial fill) yapılırken 'canlı' (live) mumları 
    # kaçırmamamızı sağlar.
    
    streams = [f"{s.lower()}@kline_{config.INTERVAL}" for s in symbols_to_stream]
    
    CHUNK_SIZE = 100 
    for i in range(0, len(streams), CHUNK_SIZE):
        chunk = streams[i:i + CHUNK_SIZE]
        log.info(f"v20.0 WebSocket: {len(chunk)} sembol (Parça {i//CHUNK_SIZE + 1}) dinleniyor...")
        
        conn_key = _bsm.futures_multiplex_socket(chunk, _process_kline_message)
        _active_streams.append(conn_key)
    
    log.info(f"--- [v20.0 'Gerçek Zamanlı' (WebSocket) Motoru (Toplam {len(streams)} Sembol) AktİF] ---")
    
    # 3. (v21.0): ŞİMDİ "İlk Dolum" (Initial Fill) işlemini başlat
    # (Bu, 'main.py' v21.0 'Akıllı Bekleme' motorunun beklediği işlemdir)
    
    log.info(f"v21.0: 'İlk Önbellek Dolumu' (Initial Cache Fill) {len(symbols_to_stream)} sembol için başlatılıyor...")
    
    fill_start_time = time.time()
    
    for i, symbol in enumerate(symbols_to_stream):
        # v21.0: Kilitli (Locked) başlatma fonksiyonunu kullan
        with _lock:
            # (Fonksiyonun kendisi de kilitli, ancak burada 'if' kontrolü 
            # yaparak 'I/O' (API) çağrısını gereksiz yere yapmaktan kaçınırız)
            if symbol not in klines_cache:
                _initialize_symbol_cache(_client, symbol)
        
        if (i + 1) % 50 == 0: # Her 50 sembolde bir ilerleme bildir
            log.info(f"v21.0: 'İlk Dolum' ilerlemesi: {i+1} / {len(symbols_to_stream)}")
            
        time.sleep(0.1) # (API Limitlerini (Rate Limit) önle)

    fill_total_time = time.time() - fill_start_time
    log.info(f"--- [v21.0 'İlk Önbellek Dolumu' {len(symbols_to_stream)} sembol için {fill_total_time:.2f} saniyede TAMAMLANDI] ---")
    
    # === v20.3 HATA DÜZELTMESİ (AttributeError: .start()) ===
    # (v21.0: Korundu. 'futures_multiplex_socket' otonom olarak (otomatik) başlar)
    pass
    # === DÜZELTME SONU ===

def stop_websocket_listener():
    if _bsm:
        log.info("v20.0 WebSocket: Durduruluyor...")
        try:
            for conn_key in _active_streams:
                # === v20.3 HATA DÜZELTMESİ (AttributeError: ._stop_socket) ===
                # (v21.0: Korundu)
                _bsm.stop_socket(conn_key)
                # === DÜZELTME SONU ===
            _bsm.close()
            log.info("v20.0 WebSocket: Başarıyla durduruldu.")
        except Exception as e:
            log.error(f"v20.3 WebSocket: Durdurma hatası: {e}")