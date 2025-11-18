"""
BaseAI - BinAI v22.0 Mimarisi
Piyasa Rejimi Tespiti (Regime Detection) Yönlendiricisi (Router)

v22.0 Yükseltmeleri (Enterprise+++):
- STRATEJİ UYUMU: 'config.py' (v22.0) içindeki yeni parametrelerle 
  (EMA, MACD, Bollinger) tam uyumlu hale getirildi.
- 'SLOW_MA_PERIOD' hatası (bug) düzeltildi (Artık 'EMA_SLOW_PERIOD' kullanılıyor).
- Saf Pandas (v21.5) altyapısı korundu.
"""

import pandas as pd
import numpy as np 
import time
from typing import Dict, Any, Tuple

try:
    from binai import config
    from binai.logger import log
    from binai import db_manager
    from binai import strategy_trending 
    from binai import strategy_ranging  
except ImportError as e:
    print(f"KRİTİK HATA (strategy.py): {e}")
    sys.exit(1)

_params_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
PARAMS_CACHE_TTL_SECONDS = 300 

def _get_cached_params(symbol: str) -> Dict[str, Any]:
    current_time = time.time()
    if symbol in _params_cache:
        params, timestamp = _params_cache[symbol]
        if (current_time - timestamp) < PARAMS_CACHE_TTL_SECONDS:
            return params
    
    params_from_db = db_manager.get_strategy_params(symbol)
    if params_from_db:
        _params_cache[symbol] = (params_from_db, current_time)
        return params_from_db
    else:
        return {} 

def _prepare_dataframe(klines_data: list) -> pd.DataFrame:
    df = pd.DataFrame(klines_data, columns=[
        'OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 
        'CloseTime', 'QuoteAssetVolume', 'NumTrades', 
        'TakerBuyBase', 'TakerBuyQuote', 'Ignore'
    ])
    df['Open'] = pd.to_numeric(df['Open'])
    df['High'] = pd.to_numeric(df['High'])
    df['Low'] = pd.to_numeric(df['Low'])
    df['Close'] = pd.to_numeric(df['Close'])
    df['Volume'] = pd.to_numeric(df['Volume'])
    return df

def _calculate_atr(df: pd.DataFrame, period: int) -> pd.DataFrame:
    df_copy = df.copy() 
    df_copy['H-L'] = df_copy['High'] - df_copy['Low']
    df_copy['H-C'] = np.abs(df_copy['High'] - df_copy['Close'].shift())
    df_copy['L-C'] = np.abs(df_copy['Low'] - df_copy['Close'].shift())
    df_copy['TR'] = df_copy[['H-L', 'H-C', 'L-C']].max(axis=1)
    df[f'ATR_{period}'] = df_copy['TR'].ewm(alpha=1/period, adjust=False).mean()
    return df

def _calculate_adx(df: pd.DataFrame, period: int) -> pd.DataFrame:
    df_copy = df.copy()
    if f'ATR_{period}' not in df.columns:
         df = _calculate_atr(df, period)
    
    # ADX hesaplaması için ATR'ye ihtiyacımız var (df'den alıyoruz)
    _atr = df[f'ATR_{period}']

    up = df['High'].diff()
    down = -df['Low'].diff()
    
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    
    plus_dm_s = pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    minus_dm_s = pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    
    plus_di = 100 * (plus_dm_s / _atr)
    minus_di = 100 * (minus_dm_s / _atr)
    
    dx = 100 * np.abs((plus_di - minus_di) / (plus_di + minus_di))
    df[f'ADX_{period}'] = dx.ewm(alpha=1/period, adjust=False).mean()
    
    return df

def analyze_symbol(symbol: str, klines_data: list, params_override: Dict = {}):
    if not params_override: 
        params = _get_cached_params(symbol)
    else:
        params = params_override

    # === v22.0 DÜZELTMESİ ===
    # Eski 'SLOW_MA_PERIOD' yerine yeni 'EMA_SLOW_PERIOD' kullan
    adx_period = int(params.get('ADX_PERIOD', config.ADX_PERIOD))
    ema_slow_period = int(params.get('EMA_SLOW_PERIOD', config.EMA_SLOW_PERIOD))
    
    required_data_length = max(adx_period, ema_slow_period, config.MIN_KLINES_FOR_STRATEGY)
    
    if len(klines_data) < required_data_length:
        return "NEUTRAL", 0.0, 0.0, 0.0 

    df = _prepare_dataframe(klines_data)
    current_price = df['Close'].iloc[-1]

    adx_threshold = float(params.get('ADX_TREND_THRESHOLD', config.ADX_TREND_THRESHOLD))
    market_regime = "TREND" 
    last_atr = 0.0 
    
    try:
        df = _calculate_atr(df, adx_period) 
        df = _calculate_adx(df, adx_period)
        
        adx_col = f'ADX_{adx_period}'
        atr_col = f'ATR_{adx_period}'

        if adx_col in df and not df[adx_col].isna().all():
            last_adx = df[adx_col].iloc[-1]
            last_atr = df[atr_col].iloc[-1]
            
            if last_adx > adx_threshold:
                market_regime = "TREND"
            else:
                market_regime = "RANGING" 
        else:
            market_regime = "TREND"

    except Exception as e:
        log.error(f"{symbol} ADX hatası: {e}")
        return "NEUTRAL", 0.0, current_price, 0.0
        
    if market_regime == "TREND":
        signal, confidence = strategy_trending.analyze(df, params)
    else: 
        signal, confidence = strategy_ranging.analyze(df, params)

    return signal, confidence, current_price, last_atr