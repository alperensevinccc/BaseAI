"""
BaseAI - BinAI v15.0 Mimari Yükseltmesi
Piyasa Rejimi Tespiti (Regime Detection) Yönlendiricisi (Router)
v15.0: "Sıfır Kesinti" (Zero Downtime) Hafıza Okuyucusu
"""
import pandas as pd
import config
from logger import log
import numpy as np

# v11.0 Yönlendiricisi, her iki strateji motorunu da import eder
import strategy_trending
import strategy_ranging
import db_manager # v12.0 "Hafıza"yı okumak için eklendi

def calculate_adx(df, adx_period):
    """
    ADX (Average Directional Index) hesaplar (Yerel Pandas/Numpy).
    """
    try:
        # 1. TR (True Range) Hesapla
        df['H-L'] = df['High'] - df['Low']
        df['H-C'] = np.abs(df['High'] - df['Close'].shift())
        df['L-C'] = np.abs(df['Low'] - df['Close'].shift())
        df['TR'] = df[['H-L', 'H-C', 'L-C']].max(axis=1)
        
        df['ATR'] = df['TR'].ewm(alpha=1/adx_period, adjust=False).mean()

        # 2. +DM (Directional Movement) ve -DM Hesapla
        df['H-pH'] = df['High'] - df['High'].shift()
        df['pL-L'] = df['Low'].shift() - df['Low']
        
        df['+DM_unsm'] = ((df['H-pH'] > df['pL-L']) & (df['H-pH'] > 0)) * df['H-pH']
        df['-DM_unsm'] = ((df['pL-L'] > df['pL-L']) & (df['pL-L'] > 0)) * df['pL-L']
        
        df['+DI_unsm'] = (df['+DM_unsm'].ewm(alpha=1/adx_period, adjust=False).mean() / df['ATR']) * 100
        df['-DI_unsm'] = (df['-DM_unsm'].ewm(alpha=1/adx_period, adjust=False).mean() / df['ATR']) * 100

        # 3. ADX Hesapla
        df['DX_raw'] = (np.abs(df['+DI_unsm'] - df['-DI_unsm']))
        df['DI_sum'] = (df['+DI_unsm'] + df['-DI_unsm'])
        
        df['DX'] = (df['DX_raw'] / df['DI_sum']).fillna(0) * 100
        df['ADX'] = df['DX'].ewm(alpha=1/adx_period, adjust=False).mean()
        
        return df
    except Exception as e:
        log.error(f"ADX hesaplaması başarısız: {e}")
        return df

# Bu, main.py, backtester.py ve optimizer.py tarafından çağrılan ana fonksiyondur.
def analyze_symbol(symbol, klines_data, params={}):
    
    # === v15.0 "SONSUZ OTONOMİ" (ZERO DOWNTIME) ÇEKİRDEĞİ ===
    # 'params' boşsa (yani canlı bot çağırıyorsa, Optimizer değilse)
    if not params: 
        # "Hafıza" (v12.0) *her çağrıldığında* okunur.
        # Bu, 'optimizer.py' (v15.0) "Evrim Motoru"nun
        # 'strategy_params.db'yi 'canlı (live)' güncellemesine izin verir.
        params_from_db = db_manager.get_strategy_params(symbol)
        
        if params_from_db:
            # Evet. Optimize edilmiş (örn: LPTUSDT için MA 5/10) parametreleri kullan.
            log.debug(f"{symbol} için 'Varlığa Özel' (v12.0) parametreler Hafıza'dan (DB) yüklendi.")
            params = params_from_db
        else:
            # Hayır. config.py'deki (örn: MA 20/50) varsayılanı kullan.
            log.debug(f"{symbol} için 'Hafıza'da (DB) parametre bulunamadı. config.py (varsayılan) kullanılıyor.")
            pass # params boş kalır
    # === v15.0 YÜKSELTME SONU ===
    
    # 1. VERİ HAZIRLAMA (ADX ve Stratejiler için)
    # v12.0: Artık 'params' sözlüğünden (ya DB'den ya config'den) okur
    adx_period = int(params.get('ADX_PERIOD', config.ADX_PERIOD))
    slow_ma_period = int(params.get('SLOW_MA_PERIOD', config.SLOW_MA_PERIOD))
    
    required_data_length = max(adx_period, slow_ma_period) + 2
    
    if len(klines_data) < required_data_length:
        return "NEUTRAL", 0.0, 0.0

    # ... (DataFrame hazırlama aynı) ...
    df = pd.DataFrame(klines_data, columns=[
        'OpenTime', 'Open', 'High', 'Low', 'Close', 'Volume', 
        'CloseTime', 'QuoteAssetVolume', 'NumTrades', 
        'TakerBuyBase', 'TakerBuyQuote', 'Ignore'
    ])
    df['Close'] = pd.to_numeric(df['Close'])
    df['High'] = pd.to_numeric(df['High'])
    df['Low'] = pd.to_numeric(df['Low'])
    df['Volume'] = pd.to_numeric(df['Volume'])

    # 2. PİYASA REJİMİ TESPİTİ (v11.0 Çekirdeği)
    df = calculate_adx(df, adx_period)
    
    if 'ADX' not in df.columns or df['ADX'].isna().all():
        log.warning(f"{symbol} için ADX hesaplanamadı (Yetersiz veri?). Trend (varsayılan) kullanılıyor.")
        market_regime = "TREND"
    else:
        last_adx = df['ADX'].iloc[-1]
        adx_threshold = float(params.get('ADX_TREND_THRESHOLD', config.ADX_TREND_THRESHOLD))
        
        if last_adx > adx_threshold:
            market_regime = "TREND"
        else:
            market_regime = "RANGING" # Yatay

    # 3. STRATEJİ YÖNLENDİRME (Router)
    
    if market_regime == "TREND":
        log.debug(f"{symbol} Rejim Tespiti: TREND (ADX: {last_adx:.2f}). 'strategy_trending' (MA Crossover) kullanılıyor.")
        return strategy_trending.analyze_symbol(symbol, klines_data, params)
    
    else: # market_regime == "RANGING"
        log.debug(f"{symbol} Rejim Tespiti: YATAY (ADX: {last_adx:.2f}). 'strategy_ranging' (Osilatör) kullanılıyor.")
        return strategy_ranging.analyze_symbol(symbol, klines_data, params)