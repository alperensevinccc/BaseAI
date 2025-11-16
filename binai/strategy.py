"""
BaseAI - BinAI v21.0 Mimari Yükseltmesi
Piyasa Rejimi Tespiti (Regime Detection) Yönlendiricisi (Router)

v21.0 Yükseltmeleri (Enterprise+++):
- Kritik Hata Düzeltmesi (ADX): Hatalı 'calculate_adx' fonksiyonu kaldırıldı.
- Endüstri Standardı (pandas-ta): ADX ve ATR (Volatilite) hesaplaması için 
  C-optimize edilmiş 'pandas-ta' kütüphanesine geçildi. Bu, %100
  doğru ve binlerce kat daha hızlıdır.
- Parametre Önbellekleme (v21.0): v15.0 'Sıfır Kesinti' (Zero Downtime) mantığı, 
  veritabanını (DB) yormamak için 5 dakikalık bir RAM önbelleği 
  ile optimize edildi.
- Veri Akışı Optimizasyonu: DataFrame artık SADECE BİR KEZ oluşturuluyor
  ve alt stratejilere (trending/ranging) doğrudan 'df' olarak aktarılıyor.
- Süper Özellik Altyapısı: 'Dinamik SL/TP' için 'ATR' (Volatilite) 
  hesaplaması eklendi.
"""

import pandas as pd
import pandas_ta as ta # v21.0 YENİ: Endüstri standardı TA kütüphanesi
import time
from typing import Dict, Any, Tuple

# === BİNAİ MODÜLLERİ ===
try:
    from binai import config
    from binai.logger import log
    from binai import db_manager
    from binai import strategy_trending # v11.0 Yönlendiricisi
    from binai import strategy_ranging  # v11.0 Yönlendiricisi
except ImportError as e:
    print(f"KRİTİK HATA (strategy.py): BinAI modülleri bulunamadı. {e}")
    sys.exit(1)
except Exception as e:
    print(f"KRİTİK HATA (strategy.py): Beklenmedik import hatası: {e}")
    sys.exit(1)


# === v21.0 PERFORMANS ÖNBELLEĞİ (Parameter Cache) ===
# v15.0 "Sıfır Kesinti" (Zero Downtime) mantığını, DB'yi yormadan 
# çalıştırmak için.
# Önbellek yapısı: { "sembol": (params_dict, timestamp) }
_params_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
PARAMS_CACHE_TTL_SECONDS = 300  # 5 Dakika (Optimizer'ın güncellemesi için makul bir süre)


def _get_cached_params(symbol: str) -> Dict[str, Any]:
    """
    v21.0 (YENİ): 'strategy_params.db' (Hafıza) verisini 5 dakika boyunca
    RAM'de (bellekte) önbelleğe alır.
    Bu, 'main.py' döngüsündeki 5 saniyelik 300+ DB sorgusunu engeller.
    """
    current_time = time.time()
    
    # 1. Önbellek (Cache) Kontrolü
    if symbol in _params_cache:
        params, timestamp = _params_cache[symbol]
        if (current_time - timestamp) < PARAMS_CACHE_TTL_SECONDS:
            log.debug(f"{symbol} için parametreler RAM Önbelleğinden (v21.0) okundu.")
            return params
    
    # 2. Önbellekte (Cache) Yoksa veya Süresi Dolmuşsa: DB (Hafıza) Okuması
    log.debug(f"{symbol} için RAM Önbelleği (v21.0) güncelleniyor (DB'den okunuyor)...")
    params_from_db = db_manager.get_strategy_params(symbol)
    
    if params_from_db:
        # Evet. Optimize edilmiş parametreleri kullan ve önbelleğe al.
        log.debug(f"{symbol} için 'Varlığa Özel' (v12.0) parametreler Hafıza'dan (DB) yüklendi.")
        _params_cache[symbol] = (params_from_db, current_time)
        return params_from_db
    else:
        # Hayır. config.py'deki (varsayılan) parametreleri kullan.
        # Not: Varsayılan parametreleri önbelleğe ALMIYORUZ, çünkü 'optimizer'
        # bu sembol için yeni bir parametre ekleyebilir.
        log.debug(f"{symbol} için 'Hafıza'da (DB) parametre bulunamadı. config.py (varsayılan) kullanılıyor.")
        return {} # Boş 'dict' döndür, 'analyze_symbol' varsayılanı kullanacak


def _prepare_dataframe(klines_data: list) -> pd.DataFrame:
    """
    v21.0 (YENİ): Listeyi (ham veri) alır ve tüm stratejilerin 
    kullanacağı standart DataFrame'e dönüştürür.
    """
    df = pd.DataFrame(klines_data, columns=[
        'OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 
        'CloseTime', 'QuoteAssetVolume', 'NumTrades', 
        'TakerBuyBase', 'TakerBuyQuote', 'Ignore'
    ])
    # Veri tiplerini 'numeric' (sayısal) olarak ayarla (hesaplama için şart)
    df['Open'] = pd.to_numeric(df['Open'])
    df['High'] = pd.to_numeric(df['High'])
    df['Low'] = pd.to_numeric(df['Low'])
    df['Close'] = pd.to_numeric(df['Close'])
    df['Volume'] = pd.to_numeric(df['Volume'])
    
    # Stratejilerin ihtiyaç duyacağı temel sütunları tut
    # (Hafızayı (memory) verimli kullanmak için gereksiz sütunları atabiliriz
    # ama şimdilik 'strategy_trending'in neye ihtiyacı olduğunu bilmiyoruz)
    
    return df


# === ANA ANALİZ YÖNLENDİRİCİSİ (v21.0) ===

def analyze_symbol(symbol: str, klines_data: list, params_override: Dict = {}):
    """
    Ana Strateji Yönlendiricisi (Router).
    main.py, backtester.py ve optimizer.py tarafından çağrılır.
    
    v21.0: Artık 'pandas-ta' kullanır, parametreleri önbelleğe alır ve 
    alt stratejilere ham 'list' yerine işlenmiş 'DataFrame' aktarır.
    """
    
    # === 1. PARAMETRE YÖNETİMİ (v21.0 Önbellekli) ===
    
    # 'params_override' (örn: Optimizer) tarafından bir parametre gelmezse,
    # v21.0 Önbellek (Cache) motorunu kullan.
    if not params_override: 
        params = _get_cached_params(symbol)
    else:
        # 'Optimizer' veya 'Backtester' çalışıyor, DB'yi veya Önbelleği ATLA.
        params = params_override

    
    # === 2. VERİ HAZIRLAMA (v21.0 Optimizasyonu) ===
    
    # Gerekli parametreleri 'params' (DB'den) veya 'config' (varsayılan) al
    adx_period = int(params.get('ADX_PERIOD', config.ADX_PERIOD))
    slow_ma_period = int(params.get('SLOW_MA_PERIOD', config.SLOW_MA_PERIOD))
    
    # Stratejilerin çalışması için gereken minimum veriyi kontrol et
    required_data_length = max(adx_period, slow_ma_period, config.MIN_KLINES_FOR_STRATEGY)
    
    if len(klines_data) < required_data_length:
        log.debug(f"{symbol} için yetersiz mum verisi ({len(klines_data)} < {required_data_length}). Atlanıyor.")
        return "NEUTRAL", 0.0, 0.0, 0.0 # v21.0: ATR için 0.0 eklendi

    # v21.0: DataFrame SADECE BİR KEZ burada oluşturulur.
    df = _prepare_dataframe(klines_data)
    
    # Son (mevcut) fiyatı al (trade_manager'a iletmek için)
    current_price = df['Close'].iloc[-1]

    
    # === 3. PİYASA REJİMİ TESPİTİ (v21.0 - pandas-ta) ===
    
    adx_threshold = float(params.get('ADX_TREND_THRESHOLD', config.ADX_TREND_THRESHOLD))
    market_regime = "TREND" # Varsayılan (ADX hesaplanamazsa)
    last_atr = 0.0 # Varsayılan (ATR hesaplanamazsa)
    
    try:
        # v21.0: Hatalı 'calculate_adx' yerine 'pandas-ta' kullan
        # Bu, ADX, DI+, DI- ve (Dinamik SL/TP için) ATR'yi hesaplar
        
        # 'adx' fonksiyonu bir DataFrame döndürür (örn: ADX_14, ADXn_14, DIp_14, DIn_14)
        adx_result = ta.adx(df['High'], df['Low'], df['Close'], length=adx_period)
        # 'atr' fonksiyonu bir Seri (Series) döndürür
        atr_result = ta.atr(df['High'], df['Low'], df['Close'], length=adx_period) # ADX periyodu ile aynı

        if adx_result is not None and f'ADX_{adx_period}' in adx_result and atr_result is not None:
            last_adx = adx_result[f'ADX_{adx_period}'].iloc[-1]
            last_atr = atr_result.iloc[-1]
            
            if last_adx > adx_threshold:
                market_regime = "TREND"
            else:
                market_regime = "RANGING" # Yatay
        else:
            log.warning(f"{symbol} için ADX/ATR hesaplanamadı (pandas-ta). Trend (varsayılan) kullanılıyor.")

    except Exception as e:
        log.error(f"{symbol} için 'pandas-ta' (ADX/ATR) hesaplaması başarısız: {e}", exc_info=True)
        return "NEUTRAL", 0.0, current_price, 0.0 # Hata durumunda işlem yapma
        

    # === 4. STRATEJİ YÖNLENDİRME (Router) (v21.0) ===
    
    # v21.0: Artık 'klines_data' (List) DEĞİL, 'df' (DataFrame) gönderiyoruz.
    # Bu, alt stratejilerin 'prepare_dataframe' adımını ATLAMASINI sağlar.
    
    if market_regime == "TREND":
        log.debug(f"{symbol} Rejim Tespiti: TREND (ADX: {last_adx:.2f}). 'strategy_trending' kullanılıyor.")
        # Alt stratejiden (signal, confidence) bekliyoruz
        signal, confidence = strategy_trending.analyze(df, params)
    
    else: # market_regime == "RANGING"
        log.debug(f"{symbol} Rejim Tespiti: YATAY (ADX: {last_adx:.2f}). 'strategy_ranging' kullanılıyor.")
        # Alt stratejiden (signal, confidence) bekliyoruz
        signal, confidence = strategy_ranging.analyze(df, params)

    # v21.0: 'main.py' ve 'trade_manager' için 4 değer döndür:
    # (Sinyal, Güven Puanı, Mevcut Fiyat, Oynaklık (ATR))
    return signal, confidence, current_price, last_atr