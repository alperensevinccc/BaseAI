"""
BaseAI - BinAI v11.0 Mimari Yükseltmesi
Yatay Piyasa (Ranging) Stratejisi (v11.2 Restorasyonu)
Strateji: Ortalamaya Geri Dönüş (Mean Reversion) - RSI Osilatörü
"""
import pandas as pd
import config
from logger import log
import numpy as np

# Bu fonksiyon, strategy_trending.py ile aynı imzaya (signature) sahiptir
# Bu, Optimizer'ın (v9.0) gelecekte bu dosyayı da optimize etmesini sağlar.
def analyze_symbol(symbol, klines_data, params={}):
    
    # 1. VERİ HAZIRLAMA
    rsi_period = int(params.get('RANGING_RSI_PERIOD', config.RANGING_RSI_PERIOD))
    
    if len(klines_data) < rsi_period + 2:
        return "NEUTRAL", 0.0, 0.0

    df = pd.DataFrame(klines_data, columns=[
        'OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 
        'CloseTime', 'QuoteAssetVolume', 'NumTrades', 
        'TakerBuyBase', 'TakerBuyQuote', 'Ignore'
    ])
    df['Close'] = pd.to_numeric(df['Close'])

    # 2. TEKNİK ANALİZ (RSI Osilatörü)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
    
    # Sıfıra bölme hatasını (division by zero) önle
    if (loss == 0).any():
        rs = np.inf # veya 100
    else:
        rs = gain / loss
        
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI'] = df['RSI'].fillna(100) # (gain == 0, loss == 0) durumları için

    df.dropna(inplace=True)
    if df.empty or len(df) < 2:
        return "NEUTRAL", 0.0, 0.0

    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    current_price = last_row['Close']

    # 3. YATAY PİYASA (RANGING) SİNYAL TESPİTİ
    
    signal = "NEUTRAL"
    confidence = 0.0 
    
    rsi_oversold = float(params.get('RANGING_RSI_OVERSOLD', config.RANGING_RSI_OVERSOLD))
    rsi_overbought = float(params.get('RANGING_RSI_OVERBOUGHT', config.RANGING_RSI_OVERBOUGHT))
    min_confidence = float(params.get('MIN_SIGNAL_CONFIDENCE', config.MIN_SIGNAL_CONFIDENCE))

    # LONG Sinyali (Osilatör): Fiyat "Aşırı Satım" (Oversold) bölgesine girdi
    if (prev_row['RSI'] >= rsi_oversold) and (last_row['RSI'] < rsi_oversold):
        # v12.7 HATA DÜZELTMESİ (Log Gürültüsü)
        # log.info(...) -> log.debug(...)
        log.debug(f"SİNYAL (v11.0 YATAY): {symbol} | LONG (RSI Aşırı Satım) | Fiyat: {current_price}")
        signal = "LONG"
        confidence = 1.0

    # SHORT Sinyali (Osilatör): Fiyat "Aşırı Alım" (Overbought) bölgesine girdi
    if (prev_row['RSI'] <= rsi_overbought) and (last_row['RSI'] > rsi_overbought):
        # v12.7 HATA DÜZELTMESİ (Log Gürültüsü)
        # log.info(...) -> log.debug(...)
        log.debug(f"SİNYAL (v11.0 YATAY): {symbol} | SHORT (RSI Aşırı Alım) | Fiyat: {current_price}")
        signal = "SHORT"
        confidence = 1.0

    # 4. SONUÇ
    if confidence < min_confidence:
        signal = "NEUTRAL"
    
    return signal, confidence, current_price