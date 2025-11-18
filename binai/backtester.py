"""
BaseAI - BinAI Evrim Motoru (v21.2 - Enterprise Core)
Geriye Dönük Test (Backtester) Modülü (v21.2 Mimarisi Uyumlu)

v21.2 Yükseltmeleri (Enterprise+++):
- "Süper Özellik #2: Dinamik Pozisyon Boyutu" Entegrasyonu:
  Backtest simülasyonu, 'config.USE_DYNAMIC_POSITION_SIZING' (v21.2) ayarını
  okuyacak ve 'trade_manager.py' (v21.2) ile %100 aynı "Dinamik Miktar"
  (Volatilite Tabanlı Risk) mantığını simüle edecek şekilde güncellendi.
- Doğru PnL (Kâr/Zarar) Raporlaması: PnL (Kâr/Zarar) artık 'pnl_percent' (yüzde) 
  üzerinden 'tahmin' edilmiyor. Simülasyon motoru artık 'hesaplanmış miktar' 
  (calculated quantity) ve 'gerçek çıkış fiyatı' (actual exit price) 
  üzerinden 'gerçek PnL (USDT)'yi hesaplar.
- 'if __name__' bloğu, v21.2 ayarlarıyla tam uyumlu hale getirildi.
"""

import pandas as pd
import numpy as np
import time
import sys
from typing import Dict, Any, Tuple

# === BİNAİ MODÜLLERİ ===
try:
    from binai import config
    from binai.logger import log
    from binai import market_data
    from binai import strategy # v21.0 Rejim Yönlendiricisini import eder
    from binai import db_manager # v21.1 'if __name__' bloğu için gerekli
except ImportError as e:
    print(f"KRİTİK HATA (backtester.py): BinAI modülleri bulunamadı. {e}")
    sys.exit(1)


def run_backtest(symbol: str, params: Dict[str, Any]) -> Tuple[float, int, float]:
    """
    Belirtilen parametrelerle 'Nokta-i Zaman' (Point-in-Time) simülasyonu 
    çalıştırır. 'Optimizer' (v18.0) tarafından çağrılır.
    
    v21.2: Artık 'strategy' (v21.0) ve 'trade_manager' (v21.2) ile 
    %100 aynı mantığı (Dinamik SL/TP ve Dinamik Miktar) test eder.
    
    Döndürür (Return):
        (Toplam PnL, Toplam İşlem Sayısı, Kazanma Oranı %)
    """
    
    # === 1. PARAMETRELERİ AYARLA (v21.2) ===
    try:
        # Strateji
        interval = params.get('INTERVAL', config.INTERVAL)
        min_signal_confidence = float(params.get('MIN_SIGNAL_CONFIDENCE', config.MIN_SIGNAL_CONFIDENCE))
        
        # Risk (Süper Özellik #1 - Dinamik SL/TP)
        use_dynamic_sltp = bool(params.get('USE_DYNAMIC_SLTP', config.USE_DYNAMIC_SLTP))
        static_sl_percent = float(params.get('STOP_LOSS_PERCENT', config.STOP_LOSS_PERCENT))
        static_tp_percent = float(params.get('TAKE_PROFIT_PERCENT', config.TAKE_PROFIT_PERCENT))
        atr_sl_multiplier = float(params.get('ATR_STOP_LOSS_MULTIPLIER', config.ATR_STOP_LOSS_MULTIPLIER))
        atr_tp_multiplier = float(params.get('ATR_TAKE_PROFIT_MULTIPLIER', config.ATR_TAKE_PROFIT_MULTIPLIER))
        
        # Kasa Doktrini (Süper Özellik #2 - Dinamik Miktar)
        leverage = float(params.get('LEVERAGE', config.LEVERAGE))
        use_dynamic_sizing = bool(params.get('USE_DYNAMIC_POSITION_SIZING', config.USE_DYNAMIC_POSITION_SIZING))
        risk_per_trade_percent = float(params.get('RISK_PER_TRADE_PERCENT', config.RISK_PER_TRADE_PERCENT))
        static_pos_percent = float(params.get('POSITION_SIZE_PERCENT', config.POSITION_SIZE_PERCENT))
        
        # (v21.2: Backtester 100 USDT'lik sabit bir kasa varsayar)
        initial_capital = 100.0 
        
    except Exception as e:
        log.error(f"Backtest parametreleri okunamadı (config'den mi geliyor?): {e}", exc_info=True)
        return 0.0, 0, 0.0

    log.info(f"--- [Evrim Motoru v21.2] Backtest Başlatıldı: {symbol} ---")
    log.info(f"Strateji: Güven Puanı (v6.0) / Rejim (v21.0) | Min. Güven: {min_signal_confidence}")
    if use_dynamic_sltp:
        log.info(f"Risk (Dinamik v21.1): SL (ATR * {atr_sl_multiplier}) | TP (ATR * {atr_tp_multiplier})")
    else:
        log.info(f"Risk (Statik v6.1): SL {static_sl_percent*100}% | TP {static_tp_percent*100}%")
    if use_dynamic_sizing:
        log.info(f"Kasa (Dinamik v21.2): Risk/İşlem {risk_per_trade_percent*100}%")
    else:
        log.info(f"Kasa (Statik v5.3): Pozisyon Büyüklüğü {static_pos_percent*100}%")
    
    # === 2. VERİ TOPLAMA (v21.1 Entegrasyonu) ===
    client = market_data.get_binance_client()
    if not client:
        log.error("Backtest için Binance istemcisi oluşturulamadı.")
        return 0.0, 0, 0.0
        
    try:
        klines = market_data.get_klines(
            client, 
            symbol=symbol, 
            interval=interval,
            limit=config.BACKTEST_KLINE_LIMIT
        )
        required_data_length = int(config.MIN_KLINES_FOR_STRATEGY + 50) # Güvenlik payı

        if len(klines) < required_data_length:
            log.error(f"Test için yeterli mum verisi (İstenen: {config.BACKTEST_KLINE_LIMIT}, Alınan: {len(klines)}, Gereken (Isınma): {required_data_length})")
            return 0.0, 0, 0.0
            
        log.info(f"{len(klines)} adet mum verisi üzerinde test yapılıyor...")
        
    except Exception as e:
        log.error(f"{symbol} için geçmiş veri çekilemedi: {e}", exc_info=True)
        return 0.0, 0, 0.0

    # === 3. SİMÜLASYON MOTORU (v21.2 Dinamik SL/TP + Dinamik Miktar) ===
    trades_log = [] 
    open_position = None # (side, entry_price, quantity, sl_price, tp_price)
    
    start_time = time.time()
    
    for i in range(required_data_length, len(klines)):
        
        current_historical_data = klines[0:i] 
        current_candle = klines[i] 
        current_high = float(current_candle[2])
        current_low = float(current_candle[3])
        
        # --- A. Pozisyon Yönetimi (v21.2 Gerçek PnL Hesabı) ---
        if open_position:
            pos = open_position
            pnl_usdt = 0.0
            closed_by = None
            
            if pos['side'] == "LONG":
                if current_low <= pos['sl_price']: 
                    closed_by = "SL"
                    pnl_usdt = (pos['sl_price'] - pos['entry_price']) * pos['quantity']
                elif current_high >= pos['tp_price']: 
                    closed_by = "TP"
                    pnl_usdt = (pos['tp_price'] - pos['entry_price']) * pos['quantity']
            
            elif pos['side'] == "SHORT":
                if current_high >= pos['sl_price']: 
                    closed_by = "SL"
                    pnl_usdt = (pos['entry_price'] - pos['sl_price']) * pos['quantity']
                elif current_low <= pos['tp_price']: 
                    closed_by = "TP"
                    pnl_usdt = (pos['entry_price'] - pos['tp_price']) * pos['quantity']

            if closed_by:
                trades_log.append({'pnl_usdt': pnl_usdt, 'reason': closed_by})
                open_position = None
        
        # --- B. Yeni Sinyal Arama (v21.2 Dinamik Miktar Hesabı) ---
        if not open_position:
            signal, confidence, price_at_signal, last_atr = strategy.analyze_symbol(
                symbol, 
                current_historical_data,
                params
            )
            
            if signal != "NEUTRAL":
                
                # --- v21.2 SÜPER ÖZELLİK #1 ve #2 HESAPLAMALARI ---
                
                # 1. SL/TP Fiyatlarını (Prices) Hesapla (Süper Özellik #1)
                sl_distance_per_unit = 0.0
                
                if use_dynamic_sltp and last_atr > 0:
                    sl_distance_per_unit = last_atr * atr_sl_multiplier
                    tp_distance_per_unit = last_atr * atr_tp_multiplier
                else:
                    sl_distance_per_unit = price_at_signal * static_sl_percent
                    tp_distance_per_unit = price_at_signal * static_tp_percent
                
                if sl_distance_per_unit == 0:
                    continue # Risk hesaplanamaz, atla

                sl_price = price_at_signal - sl_distance_per_unit if signal == "LONG" else price_at_signal + sl_distance_per_unit
                tp_price = price_at_signal + tp_distance_per_unit if signal == "LONG" else price_at_signal - tp_distance_per_unit

                # 2. Miktarı (Quantity) Hesapla (Süper Özellik #2)
                quantity = 0.0
                if use_dynamic_sizing:
                    # Dinamik Miktar (Volatilite Tabanlı Risk)
                    risk_amount_usdt = initial_capital * risk_per_trade_percent
                    quantity = risk_amount_usdt / sl_distance_per_unit
                else:
                    # Statik Miktar (Kasa %'si Tabanlı)
                    position_size_usdt = initial_capital * static_pos_percent
                    quantity = (position_size_usdt * leverage) / price_at_signal
                
                if quantity == 0.0:
                    continue # Miktar 0, atla

                # 3. Pozisyonu Aç
                open_position = {
                    'side': signal,
                    'entry_price': price_at_signal,
                    'quantity': quantity, # v21.2 YENİ: Gerçek PnL için miktarı kaydet
                    'sl_price': sl_price, # v21.2 YENİ: Çıkış (exit) mantığı için fiyatı kaydet
                    'tp_price': tp_price  # v21.2 YENİ: Çıkış (exit) mantığı için fiyatı kaydet
                }
    
    # === 4. RAPORLAMA (v21.2 Gerçek PnL) ===
    end_time = time.time()
    log.info(f"Simülasyon {end_time - start_time:.2f} saniyede tamamlandı.")
    
    if not trades_log:
        log.warning("Backtest tamamlandı ancak hiçbir sanal işlem gerçekleşmedi.")
        return 0.0, 0, 0.0 # (PNL, Trades, WinRate)

    df = pd.DataFrame(trades_log)
    
    # v21.2: PnL Raporlaması (Artık 'pnl_percent' (yüzde) değil, 
    # 'pnl_usdt' (USDT) üzerinden doğrudan hesaplanır. %100 Doğru.)
    
    total_trades = len(df)
    total_pnl = df['pnl_usdt'].sum()
    
    wins = df[df['pnl_usdt'] > 0]
    losses = df[df['pnl_usdt'] < 0]
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    
    log.info("\n--- [Evrim Motoru v21.2: Backtest Raporu] ---")
    log.info(f"Toplam Net Kâr/Zarar     : {total_pnl:.4f} USDT (100 USDT Kasa Varsayımı)")
    log.info(f"Simüle Edilen İşlem Sayısı : {total_trades}")
    log.info(f"Kazanma Oranı (Win %)      : {win_rate:.2f}% ({len(wins)} Kazanan / {len(losses)} Kaybeden)")
    log.info("------------------------------------------\n")

    # v9.1: Optimizasyon için (PNL, Trades, WinRate) Geri Döndür
    return total_pnl, total_trades, win_rate

# === v21.2 KARARLI (STABLE) TEST BLOĞU ===
if __name__ == "__main__":
    """
    Bu dosyanın 'python binai/backtester.py' olarak 
    manuel (manuel) çalıştırılabilmesi için (v21.2 Düzeltmesi).
    """
    log.info("Backtester (v21.2) manuel (manuel) modda çalıştırıldı...")
    
    engine_client = None
    try:
        db_manager.initialize_database()
        engine_client = market_data.get_binance_client()
        
        if not engine_client:
            raise Exception("Binance istemcisi (client) manuel test için başlatılamadı.")
            
        test_symbol = config.SYMBOLS_WHITELIST[0] if config.SYMBOLS_WHITELIST else "BTCUSDT"
        
        # v21.2: 'config.py' (v21.2) ile %100 uyumlu 'default_params'
        default_params = {
            # Çekirdek
            'INTERVAL': config.INTERVAL,
            'MIN_SIGNAL_CONFIDENCE': config.MIN_SIGNAL_CONFIDENCE,
            
            # Trend Stratejisi
            'FAST_MA_PERIOD': config.FAST_MA_PERIOD,
            'SLOW_MA_PERIOD': config.SLOW_MA_PERIOD,
            'RSI_PERIOD': config.RSI_PERIOD,
            'RSI_OVERSOLD': config.RSI_OVERSOLD,
            'RSI_OVERBOUGHT': config.RSI_OVERBOUGHT,
            'VOLUME_AVG_PERIOD': config.VOLUME_AVG_PERIOD,
            
            # Rejim Tespiti
            'ADX_PERIOD': config.ADX_PERIOD,
            'ADX_TREND_THRESHOLD': config.ADX_TREND_THRESHOLD,
            
            # Yatay (Ranging) Strateji
            'RANGING_RSI_PERIOD': config.RANGING_RSI_PERIOD,
            'RANGING_RSI_OVERSOLD': config.RANGING_RSI_OVERSOLD,
            'RANGING_RSI_OVERBOUGHT': config.RANGING_RSI_OVERBOUGHT,
            
            # Kasa Doktrini (Statik v5.3)
            'LEVERAGE': config.LEVERAGE,
            'POSITION_SIZE_PERCENT': config.POSITION_SIZE_PERCENT,
            
            # Kasa Doktrini (Dinamik v21.2 - SÜPER ÖZELLİK #2)
            'USE_DYNAMIC_POSITION_SIZING': config.USE_DYNAMIC_POSITION_SIZING,
            'RISK_PER_TRADE_PERCENT': config.RISK_PER_TRADE_PERCENT,
            
            # Risk (Statik v6.1)
            'STOP_LOSS_PERCENT': config.STOP_LOSS_PERCENT,
            'TAKE_PROFIT_PERCENT': config.TAKE_PROFIT_PERCENT,
            
            # Risk (Dinamik v21.1 - SÜPER ÖZELLİK #1)
            'USE_DYNAMIC_SLTP': config.USE_DYNAMIC_SLTP,
            'ATR_STOP_LOSS_MULTIPLIER': config.ATR_STOP_LOSS_MULTIPLIER,
            'ATR_TAKE_PROFIT_MULTIPLIER': config.ATR_TAKE_PROFIT_MULTIPLIER
        }
        
        # Testi çalıştır
        run_backtest(test_symbol, params=default_params)
        
    except Exception as e:
        log.error(f"Backtester manuel (manuel) test sırasında çöktü: {e}", exc_info=True)
    finally:
        # v21.1: 'Hafıza Yazıcısı'nı (DB Writer) temiz kapat
        log.info("Backtester manuel (manuel) test tamamlandı. DB Yazıcısı kapatılıyor.")
        db_manager.shutdown_db_writer()