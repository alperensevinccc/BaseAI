"""
BaseAI - BinAI v22.0 Mimari Yükseltmesi
Yatay Piyasa (Ranging) Stratejisi (Enterprise Core)
Strateji: Bollinger Bantları (Reversal) + RSI Uyumsuzluğu

v22.0 Yükseltmeleri:
- Bollinger Bantları eklendi. Fiyat bandın dışına çıkıp içeri döndüğünde sinyal üretir.
- Bu, sadece RSI kullanmaktan çok daha güvenilirdir.
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
    
    # 1. PARAMETRELER
    try:
        bb_length = int(params.get('BB_LENGTH', config.BB_LENGTH))
        bb_std = float(params.get('BB_STD', config.BB_STD))
        
        rsi_period = int(params.get('RANGING_RSI_PERIOD', config.RANGING_RSI_PERIOD))
        rsi_oversold = float(params.get('RANGING_RSI_OVERSOLD', config.RANGING_RSI_OVERSOLD))
        rsi_overbought = float(params.get('RANGING_RSI_OVERBOUGHT', config.RANGING_RSI_OVERBOUGHT))
        min_conf = float(params.get('MIN_SIGNAL_CONFIDENCE', config.MIN_SIGNAL_CONFIDENCE))
        
    except Exception as e:
        log.error(f"Yatay parametre hatası: {e}")
        return "NEUTRAL", 0.0

    # 2. TEKNİK ANALİZ (pandas-ta)
    try:
        # Bollinger Bands (BBL, BBM, BBU)
        bb = ta.bbands(df['Close'], length=bb_length, std=bb_std)
        if bb is None: return "NEUTRAL", 0.0
        
        # Sütun isimlerini standartlaştır (pandas-ta isimleri: BBL_20_2.0 vb.)
        bbl_col = f"BBL_{bb_length}_{bb_std}"
        bbu_col = f"BBU_{bb_length}_{bb_std}"
        
        df = pd.concat([df, bb], axis=1)

        # RSI
        rsi_col = f"RSI_{rsi_period}"
        df[rsi_col] = ta.rsi(df['Close'], length=rsi_period)

        df.dropna(inplace=True)
        if df.empty: return "NEUTRAL", 0.0

    except Exception as e:
        log.error(f"Yatay TA hatası: {e}")
        return "NEUTRAL", 0.0

    # 3. SİNYAL MANTIĞI (BOLLINGER REVERSAL)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    signal = "NEUTRAL"
    confidence = 0.0
    
    # === LONG Sinyali (Dip Dönüşü) ===
    # Fiyat Alt Bandın (BBL) altındaydı (veya dokundu) VE Şimdi yukarı döndü
    # VE RSI Aşırı Satım bölgesinden çıkıyor
    price_touched_low = (prev['Low'] <= prev[bbl_col])
    price_bounced = (last['Close'] > last[bbl_col])
    rsi_buy_cond = (last[rsi_col] < 45) # RSI hala düşük seviyelerde olmalı

    if price_touched_low and price_bounced:
        signal = "LONG"
        confidence = 0.70 # Bollinger dönüşü güçlüdür
        
        if last[rsi_col] < rsi_oversold: 
            confidence += 0.20 # RSI aşırı satımdan dönüyor
        if last['Close'] > prev['High']: 
            confidence += 0.10 # Güçlü mum kapanışı

    # === SHORT Sinyali (Tepe Dönüşü) ===
    # Fiyat Üst Bandın (BBU) üstündeydi (veya dokundu) VE Şimdi aşağı döndü
    price_touched_high = (prev['High'] >= prev[bbu_col])
    price_rejected = (last['Close'] < last[bbu_col])
    rsi_sell_cond = (last[rsi_col] > 55)

    if price_touched_high and price_rejected:
        signal = "SHORT"
        confidence = 0.70
        
        if last[rsi_col] > rsi_overbought: 
            confidence += 0.20
        if last['Close'] < prev['Low']: 
            confidence += 0.10

    if confidence < min_conf:
        return "NEUTRAL", 0.0
    
    log.info(f"GÜÇLÜ YATAY SİNYAL: {signal} | Güven: {confidence:.2f} | Bollinger Onaylı")
    return signal, confidence