"""
BaseAI - BinAI Evrim Motoru (v12.1 - Tam Restorasyon)
Geriye Dönük Test (Backtester) Modülü (v11.0 Mimarisi Uyumlu)
"""
import pandas as pd
import numpy as np
import time
from logger import log
import config
import market_data
import strategy # v11.0 Rejim Yönlendiricisini import eder

# v9.1 GÜNCELLEMESİ: Fonksiyon artık 'params' (parametreler) sözlüğü kabul ediyor
def run_backtest(symbol, days_to_test=30, params={}):
    
    # v9.1: Parametreleri 'config' yerine 'params' sözlüğünden al
    interval = params.get('INTERVAL', config.INTERVAL)
    min_signal_confidence = float(params.get('MIN_SIGNAL_CONFIDENCE', config.MIN_SIGNAL_CONFIDENCE))
    stop_loss_percent = float(params.get('STOP_LOSS_PERCENT', config.STOP_LOSS_PERCENT))
    take_profit_percent = float(params.get('TAKE_PROFIT_PERCENT', config.TAKE_PROFIT_PERCENT))

    log.info(f"--- [Evrim Motoru v9.1] Backtest Başlatıldı: {symbol} ---")
    log.info(f"Strateji: Güven Puanı (v6.0) / Rejim (v11.0) | Min. Güven: {min_signal_confidence}")
    log.info(f"Risk: SL {stop_loss_percent*100}% | TP {take_profit_percent*100}%")
    
    # 1. Veri Toplama
    client = market_data.get_binance_client()
    if not client:
        log.error("Backtest için Binance istemcisi oluşturulamadı.")
        return 0.0, 0, 0.0 # Hata durumunda (PNL, Trades, WinRate) döndür
        
    try:
        klines = client.futures_klines(
            symbol=symbol, 
            interval=interval, # v9.4 Düzeltmesi (artık params'tan geliyor)
            limit=1500
        )
        # v11.0: ADX'i de hesaba kat
        adx_period = int(params.get('ADX_PERIOD', config.ADX_PERIOD))
        slow_ma_period = int(params.get('SLOW_MA_PERIOD', config.SLOW_MA_PERIOD))
        required_data_length = max(adx_period, slow_ma_period) + 50 # Güvenlik payı

        if len(klines) < required_data_length:
            log.error(f"Test için yeterli mum verisi (1500) alınamadı. Alınan: {len(klines)}")
            return 0.0, 0, 0.0
        log.info(f"{len(klines)} adet mum verisi üzerinde test yapılıyor...")
    except Exception as e:
        log.error(f"{symbol} için geçmiş veri çekilemedi: {e}")
        return 0.0, 0, 0.0

    # 2. Simülasyon Motoru
    trades_log = [] 
    open_position = None
    
    # v11.0: required_data_length'ten başla
    for i in range(required_data_length, len(klines)):
        
        current_historical_data = klines[0:i]
        current_candle = klines[i]
        current_price = float(current_candle[4])
        
        # --- A. Pozisyon Yönetimi (v9.1 Parametreleri) ---
        if open_position:
            pos = open_position
            pnl_percent = (current_price - pos['entry_price']) / pos['entry_price']
            
            if pos['side'] == "SHORT":
                pnl_percent = (pos['entry_price'] - current_price) / pos['entry_price']

            if pnl_percent <= -stop_loss_percent:
                trades_log.append({'symbol': symbol, 'pnl_percent': -stop_loss_percent})
                open_position = None
            
            elif pnl_percent >= take_profit_percent:
                trades_log.append({'symbol': symbol, 'pnl_percent': take_profit_percent})
                open_position = None
        
        # --- B. Yeni Sinyal Arama ---
        if not open_position:
            # v11.0: strategy.py (Yönlendirici), otonom olarak 
            # "Hafıza"dan (DB) "Varlığa Özel" parametreleri okur
            # ve DOĞRU stratejiyi (Trending/Ranging) çağırır.
            signal, confidence, price_at_signal = strategy.analyze_symbol(
                symbol, 
                current_historical_data,
                params # YENİ EKLENEN PARAMETRE
            )
            
            if signal != "NEUTRAL":
                open_position = {
                    'side': signal,
                    'entry_price': price_at_signal
                }
    
    # 3. Raporlama
    if not trades_log:
        log.warning("Backtest tamamlandı ancak hiçbir sanal işlem gerçekleşmedi.")
        return 0.0, 0, 0.0

    df = pd.DataFrame(trades_log)
    
    # Kasa Doktrini (v9.1 Parametreleri)
    leverage = float(params.get('LEVERAGE', config.LEVERAGE))
    position_margin = float(params.get('POSITION_SIZE_PERCENT', config.POSITION_SIZE_PERCENT))
    
    df['roe'] = df['pnl_percent'] * leverage
    df['pnl_usdt'] = (df['roe'] * (100 * position_margin)) # 100 USDT Kasa varsayımı
    
    total_trades = len(df)
    total_pnl = df['pnl_usdt'].sum()
    
    wins = df[df['pnl_usdt'] > 0]
    losses = df[df['pnl_usdt'] < 0]
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    
    avg_win_pnl = wins['pnl_usdt'].mean()
    avg_loss_pnl = losses['pnl_usdt'].mean()
    
    print("\n--- [Evrim Motoru v9.1: Backtest Raporu] ---")
    print(f"Toplam Net Kâr/Zarar     : {total_pnl:.4f} USDT")
    print(f"Simüle Edilen İşlem Sayısı : {total_trades}")
    print(f"Kazanma Oranı (Win %)      : {win_rate:.2f}% ({len(wins)} Kazanan / {len(losses)} Kaybeden)")
    print("------------------------------------------\n")

    # v9.1: Optimizasyon için (PNL, Trades, WinRate) Geri Döndür
    return total_pnl, total_trades, win_rate

if __name__ == "__main__":
    # v12.1 Düzeltmesi (v11.0 uyumlu)
    test_symbol = config.SYMBOLS_WHITELIST[0] if config.SYMBOLS_WHITELIST else "BTCUSDT"
    
    default_params = {
        'INTERVAL': config.INTERVAL,
        'FAST_MA_PERIOD': config.FAST_MA_PERIOD,
        'SLOW_MA_PERIOD': config.SLOW_MA_PERIOD,
        'RSI_PERIOD': config.RSI_PERIOD,
        'RSI_OVERSOLD': config.RSI_OVERSOLD,
        'RSI_OVERBOUGHT': config.RSI_OVERBOUGHT,
        'VOLUME_AVG_PERIOD': config.VOLUME_AVG_PERIOD,
        'MIN_SIGNAL_CONFIDENCE': config.MIN_SIGNAL_CONFIDENCE,
        'STOP_LOSS_PERCENT': config.STOP_LOSS_PERCENT,
        'TAKE_PROFIT_PERCENT': config.TAKE_PROFIT_PERCENT,
        'LEVERAGE': config.LEVERAGE,
        'POSITION_SIZE_PERCENT': config.POSITION_SIZE_PERCENT,
        # v11.0 Parametrelerini ekle
        'ADX_PERIOD': config.ADX_PERIOD,
        'ADX_TREND_THRESHOLD': config.ADX_TREND_THRESHOLD,
        'RANGING_RSI_PERIOD': config.RANGING_RSI_PERIOD,
        'RANGING_RSI_OVERSOLD': config.RANGING_RSI_OVERSOLD,
        'RANGING_RSI_OVERBOUGHT': config.RANGING_RSI_OVERBOUGHT
    }
    
    klines = client.futures_klines(
            symbol=symbol, 
            interval=interval,
            limit=config.BACKTEST_KLINE_LIMIT # (v19.0: config'den okur, 1500)
        )