"""
BaseAI - BinAI v11.0 Mimari Yükseltmesi
"Trend Takip" (Trend Following) Stratejisi
Strateji: MA Crossover + Güven Puanı (v12.3 Onarımı)
"""
import pandas as pd
import config
from logger import log
import numpy as np # RSI hesaplaması için

# v9.0 GÜNCELLEMESİ: Fonksiyon 'params' (parametreler) sözlüğü kabul ediyor
def analyze_symbol(symbol, klines_data, params={}):
    
    # 1. VERİ HAZIRLAMA
    slow_ma_period = int(params.get('SLOW_MA_PERIOD', config.SLOW_MA_PERIOD))
    
    if len(klines_data) < slow_ma_period + 2:
        return "NEUTRAL", 0.0, 0.0

    df = pd.DataFrame(klines_data, columns=[
        'OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 
        'CloseTime', 'QuoteAssetVolume', 'NumTrades', 
        'TakerBuyBase', 'TakerBuyQuote', 'Ignore'
    ])

    df['Close'] = pd.to_numeric(df['Close'])
    df['Volume'] = pd.to_numeric(df['Volume'])

    # 2. TEKNİK ANALİZ (Yerel Pandas - v9.0 Parametreleri)
    
    # A. Hareketli Ortalamalar (MA)
    fast_ma_period = int(params.get('FAST_MA_PERIOD', config.FAST_MA_PERIOD))
    df['SMA_FAST'] = df['Close'].rolling(window=fast_ma_period).mean()
    df['SMA_SLOW'] = df['Close'].rolling(window=slow_ma_period).mean()
    
    # B. Hacim Ortalaması (Volume Analysis)
    volume_avg_period = int(params.get('VOLUME_AVG_PERIOD', config.VOLUME_AVG_PERIOD))
    df['VOLUME_AVG'] = df['Volume'].rolling(window=volume_avg_period).mean()

    # C. RSI (Yerel Pandas ile Hesaplama)
    rsi_period = int(params.get('RSI_PERIOD', config.RSI_PERIOD))
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    
    # Sıfıra bölme hatasını (division by zero) önle
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI'] = df['RSI'].replace([np.inf, -np.inf], 100).fillna(50) # Hataları ve NaN'leri yönet

    df.dropna(inplace=True)
    if df.empty or len(df) < 2:
        log.debug(f"{symbol} için analiz verisi yetersiz (NA drop sonrası).")
        return "NEUTRAL", 0.0, 0.0

    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    current_price = last_row['Close']

    # 3. GÜVEN PUANI HESAPLAMA (v9.0 Parametreleri)
    
    signal = "NEUTRAL"
    confidence = 0.0
    
    is_long_crossover = (prev_row['SMA_FAST'] <= prev_row['SMA_SLOW']) and (last_row['SMA_FAST'] > last_row['SMA_SLOW'])
    
    if is_long_crossover:
        signal = "LONG"
        confidence = 0.5 # Temel Sinyal Puanı
        
        rsi_overbought = float(params.get('RSI_OVERBOUGHT', config.RSI_OVERBOUGHT))
        if last_row['RSI'] < (rsi_overbought - 10):
            confidence += 0.25
        if last_row['Volume'] > last_row['VOLUME_AVG'] * 1.2:
            confidence += 0.25

    # === v12.3 HATA DÜZELTMESİ (KeyError: 'FAST_MA') ===
    # HATALI KOD:
    # is_short_crossover = (prev_row['FAST_MA'] >= prev_row['SLOW_MA']) and (last_row['FAST_MA'] < last_row['SLOW_MA'])
    
    # ONARILMIŞ KOD:
    is_short_crossover = (prev_row['SMA_FAST'] >= prev_row['SMA_SLOW']) and (last_row['SMA_FAST'] < last_row['SMA_SLOW'])
    # === DÜZELTME SONU ===
    
    if is_short_crossover:
        signal = "SHORT"
        confidence = 0.5 # Temel Sinyal Puanı
        
        rsi_oversold = float(params.get('RSI_OVERSOLD', config.RSI_OVERSOLD))
        if last_row['RSI'] > (rsi_oversold + 10):
            confidence += 0.25
        if last_row['Volume'] > last_row['VOLUME_AVG'] * 1.2:
            confidence += 0.25

    # 4. SONUÇ
    min_signal_confidence = float(params.get('MIN_SIGNAL_CONFIDENCE', config.MIN_SIGNAL_CONFIDENCE))
    
    if confidence < min_signal_confidence:
        signal = "NEUTRAL"
    
    if signal != "NEUTRAL":
        pass
    
    return signal, confidence, current_price