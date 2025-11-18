"""
pandas-ta (Local Enterprise Edition - v22.0 Uyumlu)
Bu modül, BinAI v22.0 stratejilerinin ihtiyaç duyduğu 
EMA, MACD, Bollinger Bands, RSI, SMA, ADX ve ATR 
fonksiyonlarını SAF PANDAS ile eksiksiz hesaplar.
"""
import pandas as pd
import numpy as np

version = "0.3.14b (Local v22.0)"

# === TREND GÖSTERGELERİ ===

def sma(series, length=None, **kwargs):
    """Simple Moving Average"""
    if length is None: return None
    return series.rolling(window=length).mean()

def ema(series, length=None, **kwargs):
    """Exponential Moving Average (v22.0 için eklendi)"""
    if length is None: return None
    # pandas ewm fonksiyonu, pandas-ta ile birebir aynı sonucu verir
    return series.ewm(span=length, adjust=False).mean()

def macd(close, fast=None, slow=None, signal=None, **kwargs):
    """Moving Average Convergence Divergence (v22.0 için eklendi)"""
    if fast is None: fast = 12
    if slow is None: slow = 26
    if signal is None: signal = 9
    
    fast_ema = close.ewm(span=fast, adjust=False).mean()
    slow_ema = close.ewm(span=slow, adjust=False).mean()
    
    _macd = fast_ema - slow_ema
    _signal = _macd.ewm(span=signal, adjust=False).mean()
    _hist = _macd - _signal
    
    # pandas-ta sütun isimlendirme standardına uyum
    return pd.DataFrame({
        f"MACD_{fast}_{slow}_{signal}": _macd,
        f"MACDh_{fast}_{slow}_{signal}": _hist,
        f"MACDs_{fast}_{slow}_{signal}": _signal
    })

# === VOLATİLİTE GÖSTERGELERİ ===

def bbands(close, length=None, std=None, **kwargs):
    """Bollinger Bands (v22.0 için eklendi)"""
    if length is None: length = 5
    if std is None: std = 2.0
    
    mid = close.rolling(window=length).mean()
    sd = close.rolling(window=length).std()
    
    upper = mid + (sd * std)
    lower = mid - (sd * std)
    
    # pandas-ta sütun isimlendirme standardına uyum
    return pd.DataFrame({
        f"BBL_{length}_{std}": lower,
        f"BBM_{length}_{std}": mid,
        f"BBU_{length}_{std}": upper
    })

def atr(high, low, close, length=None, **kwargs):
    """Average True Range"""
    if length is None: length = 14
    
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    
    return true_range.ewm(alpha=1/length, adjust=False).mean()

# === MOMENTUM GÖSTERGELERİ ===

def rsi(series, length=None, **kwargs):
    """Relative Strength Index"""
    if length is None: length = 14
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
    
    rs = gain / loss
    res = 100 - (100 / (1 + rs))
    return res.fillna(50)

def adx(high, low, close, length=None, **kwargs):
    """Average Directional Index"""
    if length is None: length = 14
    
    _atr = atr(high, low, close, length)
    
    up = high.diff()
    down = -low.diff()
    
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    
    plus_dm_s = pd.Series(plus_dm, index=high.index).ewm(alpha=1/length, adjust=False).mean()
    minus_dm_s = pd.Series(minus_dm, index=high.index).ewm(alpha=1/length, adjust=False).mean()
    
    plus_di = 100 * (plus_dm_s / _atr)
    minus_di = 100 * (minus_dm_s / _atr)
    
    dx = 100 * np.abs((plus_di - minus_di) / (plus_di + minus_di))
    adx_val = dx.ewm(alpha=1/length, adjust=False).mean()
    
    return pd.DataFrame({
        f"ADX_{length}": adx_val,
        f"DMP_{length}": plus_di,
        f"DMN_{length}": minus_di
    })