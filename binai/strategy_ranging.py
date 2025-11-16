"""
BaseAI - BinAI v21.0 Mimari Yükseltmesi
Yatay Piyasa (Ranging) Stratejisi (Enterprise Core)
Strateji: Ortalamaya Geri Dönüş (Mean Reversion) - RSI Osilatörü (pandas-ta optimizeli)

v21.0 Yükseltmeleri:
- 'strategy.py' (v21.0 Yönlendirici) ile tam entegrasyon.
- Fonksiyon imzası 'analyze(df, params)' olarak güncellendi.
- 'pd.DataFrame' oluşturma gibi gereksiz (redundant) Veri Hazırlama adımları 
  kaldırıldı (Artık 'df' hazır geliyor).
- Tüm 'yerel' (manual) TA hesaplamaları (RSI) 'pandas-ta'
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
    print(f"KRİTİK HATA (strategy_ranging.py): BinAI modülleri bulunamadı. {e}")
    sys.exit(1)


# === ANA ANALİZ MOTORU (v21.0) ===

def analyze(df: pd.DataFrame, params: Dict[str, Any]) -> Tuple[str, float]:
    """
    "Yatay Piyasa" (Ranging) stratejisini çalıştırır.
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
    try:
        rsi_period = int(params.get('RANGING_RSI_PERIOD', config.RANGING_RSI_PERIOD))
        rsi_oversold = float(params.get('RANGING_RSI_OVERSOLD', config.RANGING_RSI_OVERSOLD))
        rsi_overbought = float(params.get('RANGING_RSI_OVERBOUGHT', config.RANGING_RSI_OVERBOUGHT))
        min_confidence = float(params.get('MIN_SIGNAL_CONFIDENCE', config.MIN_SIGNAL_CONFIDENCE))
        
    except Exception as e:
        log.error(f"Yatay (Ranging) stratejisi parametreleri okunamadı: {e}", exc_info=True)
        return "NEUTRAL", 0.0

    # 2. TEKNİK ANALİZ (v21.0 - pandas-ta)
    # (v21.0: 'df' zaten hazır, 'prepare_dataframe' adımı yok)
    
    try:
        # Dinamik sütun adı (Enterprise Standardı)
        rsi_col = f"RSI_{rsi_period}"

        # C. RSI
        df[rsi_col] = ta.rsi(df['Close'], length=rsi_period)

        # Hesaplamalardan sonra oluşabilecek 'NaN' (Boş) değerleri temizle
        df.dropna(inplace=True)
        if df.empty or len(df) < 2:
            log.debug(f"Yatay (Ranging) analizi için veri yetersiz (NaN drop sonrası).")
            return "NEUTRAL", 0.0

    except Exception as e:
        log.error(f"Yatay (Ranging) stratejisi TA (pandas-ta) hesaplaması başarısız: {e}", exc_info=True)
        return "NEUTRAL", 0.0

    # 3. YATAY PİYASA (RANGING) SİNYAL TESPİTİ (v11.0 Mantığı, v21.0 Kodu)
    
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]

    signal = "NEUTRAL"
    confidence = 0.0 
    
    # === LONG Sinyali (Osilatör): Fiyat "Aşırı Satım" (Oversold) BÖLGESİNE GİRDİ ===
    if (prev_row[rsi_col] >= rsi_oversold) and (last_row[rsi_col] < rsi_oversold):
        log.info(f"STRATEJİ (YATAY): LONG sinyali (RSI Aşırı Satım: {last_row[rsi_col]:.2f}) 1.00 güven puanı ile bulundu.")
        signal = "LONG"
        confidence = 1.0 # Yatay piyasada 'aşırı' sinyaller yüksek güvenilirdir

    # === SHORT Sinyali (Osilatör): Fiyat "Aşırı Alım" (Overbought) BÖLGESİNE GİRDİ ===
    if (prev_row[rsi_col] <= rsi_overbought) and (last_row[rsi_col] > rsi_overbought):
        log.info(f"STRATEJİ (YATAY): SHORT sinyali (RSI Aşırı Alım: {last_row[rsi_col]:.2f}) 1.00 güven puanı ile bulundu.")
        signal = "SHORT"
        confidence = 1.0

    # 4. SONUÇ FİLTRELEME
    if confidence < min_confidence:
        signal = "NEUTRAL"
    
    # v21.0: Yönlendirici (Router) sadece (sinyal, güven) bekliyor.
    return signal, confidence