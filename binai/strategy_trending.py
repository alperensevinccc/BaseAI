"""
BaseAI - BinAI v21.0 Mimari Yükseltmesi
"Trend Takip" (Trend Following) Stratejisi (Enterprise Core)
Strateji: MA Crossover + RSI Filtresi + Hacim Onayı (pandas-ta optimizeli)

v21.0 Yükseltmeleri:
- 'strategy.py' (v21.0 Yönlendirici) ile tam entegrasyon.
- Fonksiyon imzası 'analyze(df, params)' olarak güncellendi.
- 'pd.DataFrame' oluşturma gibi gereksiz (redundant) Veri Hazırlama adımları 
  kaldırıldı (Artık 'df' hazır geliyor).
- Tüm 'yerel' (manual) TA hesaplamaları (MA, RSI, Hacim) 'pandas-ta'
  kütüphanesi ile değiştirildi (%100 doğru ve çok daha hızlı).
- Sütun adları, 'config' dosyasına göre 'dinamik' hale getirildi.
"""

import pandas as pd
import pandas_ta as ta # v21.0: Endüstri standardı TA kütüphanesi
from typing import Dict, Any, Tuple

# === BİNAİ MODÜLLERİ ===
try:
    from binai import config
    from binai.logger import log
except ImportError as e:
    print(f"KRİTİK HATA (strategy_trending.py): BinAI modülleri bulunamadı. {e}")
    sys.exit(1)


# === ANA ANALİZ MOTORU (v21.0) ===

def analyze(df: pd.DataFrame, params: Dict[str, Any]) -> Tuple[str, float]:
    """
    "Trend Takip" (Trend Following) stratejisini çalıştırır.
    'strategy.py' (v21.0 Yönlendirici) tarafından çağrılır.
    
    Parametreler:
        df (pd.DataFrame): 'strategy.py' tarafından önceden hazırlanmış
                           ve ADX/ATR içeren ana DataFrame.
        params (Dict): Bu sembol için 'Hafıza'dan (DB) veya 'config'den
                       gelen optimize edilmiş/varsayılan parametreler.
                       
    Döndürür (Return):
        (str, float): (Sinyal ["LONG", "SHORT", "NEUTRAL"], Güven Puanı [0.0 - 1.0])
    """
    
    # 1. PARAMETRELERİ AL (v21.0)
    # Gerekli parametreleri 'params' (DB'den) veya 'config' (varsayılan) al
    try:
        fast_ma_period = int(params.get('FAST_MA_PERIOD', config.FAST_MA_PERIOD))
        slow_ma_period = int(params.get('SLOW_MA_PERIOD', config.SLOW_MA_PERIOD))
        rsi_period = int(params.get('RSI_PERIOD', config.RSI_PERIOD))
        volume_avg_period = int(params.get('VOLUME_AVG_PERIOD', config.VOLUME_AVG_PERIOD))
        
        min_signal_confidence = float(params.get('MIN_SIGNAL_CONFIDENCE', config.MIN_SIGNAL_CONFIDENCE))
        rsi_overbought = float(params.get('RSI_OVERBOUGHT', config.RSI_OVERBOUGHT))
        rsi_oversold = float(params.get('RSI_OVERSOLD', config.RSI_OVERSOLD))
        
    except Exception as e:
        log.error(f"Trend stratejisi parametreleri okunamadı: {e}", exc_info=True)
        return "NEUTRAL", 0.0

    # 2. TEKNİK ANALİZ (v21.0 - pandas-ta)
    # (v21.0: 'df' zaten hazır, 'prepare_dataframe' adımı yok)
    
    try:
        # Dinamik sütun adları (Enterprise Standardı)
        fast_ma_col = f"SMA_{fast_ma_period}"
        slow_ma_col = f"SMA_{slow_ma_period}"
        rsi_col = f"RSI_{rsi_period}"
        vol_col = f"VOL_AVG_{volume_avg_period}"

        # A. Hareketli Ortalamalar (MA)
        df[fast_ma_col] = ta.sma(df['Close'], length=fast_ma_period)
        df[slow_ma_col] = ta.sma(df['Close'], length=slow_ma_period)
        
        # B. Hacim Ortalaması (Volume Analysis - Süper Özellik 1)
        # (ta.sma'yı 'Volume' sütununda çalıştırıyoruz)
        df[vol_col] = ta.sma(df['Volume'], length=volume_avg_period)

        # C. RSI
        df[rsi_col] = ta.rsi(df['Close'], length=rsi_period)

        # Hesaplamalardan sonra oluşabilecek 'NaN' (Boş) değerleri temizle
        df.dropna(inplace=True)
        if df.empty or len(df) < 2:
            log.debug(f"Trend analizi için veri yetersiz (NaN drop sonrası).")
            return "NEUTRAL", 0.0

    except Exception as e:
        log.error(f"Trend stratejisi TA (pandas-ta) hesaplaması başarısız: {e}", exc_info=True)
        return "NEUTRAL", 0.0

    # 3. SİNYAL VE GÜVEN PUANI HESAPLAMA (v11.0 Mantığı, v21.0 Kodu)
    
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    signal = "NEUTRAL"
    confidence = 0.0
    
    # === LONG Sinyal Koşulu ===
    is_long_crossover = (prev_row[fast_ma_col] <= prev_row[slow_ma_col]) and \
                        (last_row[fast_ma_col] > last_row[slow_ma_col])
    
    if is_long_crossover:
        signal = "LONG"
        confidence = 0.5 # Temel Sinyal Puanı
        
        # Güven Artırıcı 1: RSI (Aşırı Alımda Değil)
        if last_row[rsi_col] < (rsi_overbought - 10): # (örn: 70 - 10 = 60'ın altında)
            confidence += 0.25
        
        # Güven Artırıcı 2: Hacim (Ortalamanın Üstünde)
        if last_row['Volume'] > (last_row[vol_col] * 1.2): # (Ortalamanın %20 üstünde)
            confidence += 0.25

    # === SHORT Sinyal Koşulu ===
    # (v12.3 Hata Düzeltmesi korunarak v21.0'a taşındı)
    is_short_crossover = (prev_row[fast_ma_col] >= prev_row[slow_ma_col]) and \
                         (last_row[fast_ma_col] < last_row[slow_ma_col])
    
    if is_short_crossover:
        signal = "SHORT"
        confidence = 0.5 # Temel Sinyal Puanı
        
        # Güven Artırıcı 1: RSI (Aşırı Satımda Değil)
        if last_row[rsi_col] > (rsi_oversold + 10): # (örn: 30 + 10 = 40'ın üstünde)
            confidence += 0.25
            
        # Güven Artırıcı 2: Hacim (Ortalamanın Üstünde)
        if last_row['Volume'] > (last_row[vol_col] * 1.2):
            confidence += 0.25

    # 4. SONUÇ FİLTRELEME
    if confidence < min_signal_confidence:
        signal = "NEUTRAL"
    
    if signal != "NEUTRAL":
        log.info(f"STRATEJİ (TREND): {signal} sinyali {confidence:.2f} güven puanı ile bulundu.")
    
    # v21.0: Yönlendirici (Router) sadece (sinyal, güven) bekliyor.
    return signal, confidence