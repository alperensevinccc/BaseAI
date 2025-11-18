"""
BaseAI - BinAI v22.0 Mimari Yükseltmesi
"Trend Takip" (Trend Following) Stratejisi (Enterprise Core)
Strateji: EMA Cross + MACD Momentum + RSI Filtresi

v22.0 Yükseltmeleri:
- SMA yerine EMA (Üssel Hareketli Ortalama) kullanımı.
- MACD (Momentum) onayı eklendi. Sadece momentum güçlüyse işleme girer.
"""

import pandas as pd
import pandas_ta as ta 
from typing import Dict, Any, Tuple

try:
    from binai import config
    from binai.logger import log
except ImportError as e:
    print(f"KRİTİK HATA: {e}")
    sys.exit(1)

def analyze(df: pd.DataFrame, params: Dict[str, Any]) -> Tuple[str, float]:
    
    # 1. PARAMETRELERİ AL
    try:
        ema_fast_period = int(params.get('EMA_FAST_PERIOD', config.EMA_FAST_PERIOD))
        ema_slow_period = int(params.get('EMA_SLOW_PERIOD', config.EMA_SLOW_PERIOD))
        
        macd_fast = int(params.get('MACD_FAST', config.MACD_FAST))
        macd_slow = int(params.get('MACD_SLOW', config.MACD_SLOW))
        macd_signal = int(params.get('MACD_SIGNAL', config.MACD_SIGNAL))
        
        rsi_period = int(params.get('RSI_PERIOD', config.RSI_PERIOD))
        vol_avg_period = int(params.get('VOLUME_AVG_PERIOD', config.VOLUME_AVG_PERIOD))
        
        min_conf = float(params.get('MIN_SIGNAL_CONFIDENCE', config.MIN_SIGNAL_CONFIDENCE))
        
    except Exception as e:
        log.error(f"Trend parametre hatası: {e}")
        return "NEUTRAL", 0.0

    # 2. TEKNİK ANALİZ (pandas-ta)
    try:
        # A. EMA (Exponential Moving Average)
        # (Bazen 'ema' fonksiyonu None dönebilir, kontrol etmeliyiz)
        ema_f = ta.ema(df['Close'], length=ema_fast_period)
        ema_s = ta.ema(df['Close'], length=ema_slow_period)
        
        if ema_f is None or ema_s is None: return "NEUTRAL", 0.0
        
        df[f'EMA_{ema_fast_period}'] = ema_f
        df[f'EMA_{ema_slow_period}'] = ema_s

        # B. MACD
        macd = ta.macd(df['Close'], fast=macd_fast, slow=macd_slow, signal=macd_signal)
        if macd is None: return "NEUTRAL", 0.0
        
        # pandas-ta MACD sütun isimleri: MACD_12_26_9, MACDh_12_26_9 (Histogram), MACDs...
        macd_col = f"MACD_{macd_fast}_{macd_slow}_{macd_signal}"
        hist_col = f"MACDh_{macd_fast}_{macd_slow}_{macd_signal}"
        
        df = pd.concat([df, macd], axis=1) # DataFrame'e ekle

        # C. RSI & Volume
        df[f'RSI_{rsi_period}'] = ta.rsi(df['Close'], length=rsi_period)
        df[f'VOL_AVG'] = ta.sma(df['Volume'], length=vol_avg_period)

        df.dropna(inplace=True)
        if df.empty: return "NEUTRAL", 0.0

    except Exception as e:
        log.error(f"Trend TA hatası: {e}")
        return "NEUTRAL", 0.0

    # 3. SİNYAL MANTIĞI (GÜÇLENDİRİLMİŞ)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    ema_fast = f'EMA_{ema_fast_period}'
    ema_slow = f'EMA_{ema_slow_period}'
    rsi_col = f'RSI_{rsi_period}'

    signal = "NEUTRAL"
    confidence = 0.0
    
    # === LONG MANTIĞI ===
    # 1. EMA Cross (Hızlı, Yavaşı yukarı kesti)
    trend_up = (prev[ema_fast] <= prev[ema_slow]) and (last[ema_fast] > last[ema_slow])
    
    # 2. MACD Onayı (Histogram 0'ın üzerinde VE artıyor)
    momentum_up = (last[hist_col] > 0) and (last[hist_col] > prev[hist_col])
    
    if trend_up:
        signal = "LONG"
        confidence = 0.5
        
        if momentum_up: 
            confidence += 0.20 # MACD onayı
        if last[rsi_col] > 50: 
            confidence += 0.15 # RSI 50 üzeri (Bullish Zone)
        if last['Volume'] > last['VOL_AVG']: 
            confidence += 0.15 # Hacim onayı

    # === SHORT MANTIĞI ===
    # 1. EMA Cross (Hızlı, Yavaşı aşağı kesti)
    trend_down = (prev[ema_fast] >= prev[ema_slow]) and (last[ema_fast] < last[ema_slow])
    
    # 2. MACD Onayı (Histogram 0'ın altında VE düşüyor)
    momentum_down = (last[hist_col] < 0) and (last[hist_col] < prev[hist_col])

    if trend_down:
        signal = "SHORT"
        confidence = 0.5
        
        if momentum_down: 
            confidence += 0.20
        if last[rsi_col] < 50: 
            confidence += 0.15 # RSI 50 altı (Bearish Zone)
        if last['Volume'] > last['VOL_AVG']: 
            confidence += 0.15

    if confidence < min_conf:
        return "NEUTRAL", 0.0
    
    log.info(f"GÜÇLÜ TREND SİNYALİ: {signal} | Güven: {confidence:.2f} | MACD Onaylı")
    return signal, confidence