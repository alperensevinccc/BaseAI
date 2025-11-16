"""
BaseAI - BinAI Evrim Motoru (v21.1 - Enterprise Core)
Geriye Dönük Test (Backtester) Modülü (v21.1 Mimarisi Uyumlu)

v21.1 Yükseltmeleri (Enterprise+++):
- "Süper Özellik #1: Dinamik SL/TP" Entegrasyonu:
  Backtest simülasyonu, 'config.USE_DYNAMIC_SLTP' (v21.1) ayarını okuyacak 
  ve 'strategy.py' (v21.0) tarafından sağlanan 'last_atr' (Volatilite) 
  verisini kullanarak 'trade_manager.py' (v21.0) ile %100 aynı 
  SL/TP mantığını simüle edecek şekilde güncellendi.
- Veri Hattı (Data Pipeline) Entegrasyonu: 'client.futures_klines' (manuel) 
  çağrıları kaldırıldı. Artık 'market_data.get_klines' (v21.0 
  "Birleşik Evrim" motoru) kullanılıyor.
- Kararlılık (Stability) Düzeltmesi: 'if __name__ == "__main__":' 
  test bloğundaki kritik çökme (crash) hatası düzeltildi.
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
    
    v21.1: Artık 'strategy' (v21.0) ve 'trade_manager' (v21.0) ile 
    %100 aynı mantığı (Dinamik SL/TP dahil) test eder.
    
    Döndürür (Return):
        (Toplam PnL, Toplam İşlem Sayısı, Kazanma Oranı %)
    """
    
    # === 1. PARAMETRELERİ AYARLA ===
    try:
        interval = params.get('INTERVAL', config.INTERVAL)
        min_signal_confidence = float(params.get('MIN_SIGNAL_CONFIDENCE', config.MIN_SIGNAL_CONFIDENCE))
        
        # v21.1: Hem Statik hem Dinamik risk parametrelerini al
        use_dynamic_sltp = bool(params.get('USE_DYNAMIC_SLTP', config.USE_DYNAMIC_SLTP))
        static_sl_percent = float(params.get('STOP_LOSS_PERCENT', config.STOP_LOSS_PERCENT))
        static_tp_percent = float(params.get('TAKE_PROFIT_PERCENT', config.TAKE_PROFIT_PERCENT))
        atr_sl_multiplier = float(params.get('ATR_STOP_LOSS_MULTIPLIER', config.ATR_STOP_LOSS_MULTIPLIER))
        atr_tp_multiplier = float(params.get('ATR_TAKE_PROFIT_MULTIPLIER', config.ATR_TAKE_PROFIT_MULTIPLIER))
        
        leverage = float(params.get('LEVERAGE', config.LEVERAGE))
        position_margin = float(params.get('POSITION_SIZE_PERCENT', config.POSITION_SIZE_PERCENT))
        
    except Exception as e:
        log.error(f"Backtest parametreleri okunamadı (config'den mi geliyor?): {e}", exc_info=True)
        return 0.0, 0, 0.0

    log.info(f"--- [Evrim Motoru v21.1] Backtest Başlatıldı: {symbol} ---")
    log.info(f"Strateji: Güven Puanı (v6.0) / Rejim (v21.0) | Min. Güven: {min_signal_confidence}")
    if use_dynamic_sltp:
        log.info(f"Risk (Dinamik v21.1): SL (ATR * {atr_sl_multiplier}) | TP (ATR * {atr_tp_multiplier})")
    else:
        log.info(f"Risk (Statik v6.1): SL {static_sl_percent*100}% | TP {static_tp_percent*100}%")
    
    # === 2. VERİ TOPLAMA (v21.1 Entegrasyonu) ===
    client = market_data.get_binance_client()
    if not client:
        log.error("Backtest için Binance istemcisi oluşturulamadı.")
        return 0.0, 0, 0.0
        
    try:
        # v21.1: 'market_data' (v21.0) motorunu kullan
        klines = market_data.get_klines(
            client, 
            symbol=symbol, 
            interval=interval,
            limit=config.BACKTEST_KLINE_LIMIT # (config'den okur, örn: 1500)
        )
        
        # Stratejinin 'ısınması' (warm-up) için gereken minimum veri
        required_data_length = int(config.MIN_KLINES_FOR_STRATEGY + 50) # Güvenlik payı

        if len(klines) < required_data_length:
            log.error(f"Test için yeterli mum verisi (İstenen: {config.BACKTEST_KLINE_LIMIT}, Alınan: {len(klines)}, Gereken (Isınma): {required_data_length})")
            return 0.0, 0, 0.0
            
        log.info(f"{len(klines)} adet mum verisi üzerinde test yapılıyor...")
        
    except Exception as e:
        log.error(f"{symbol} için geçmiş veri çekilemedi: {e}", exc_info=True)
        return 0.0, 0, 0.0

    # === 3. SİMÜLASYON MOTORU (v21.1 Dinamik SL/TP) ===
    trades_log = [] 
    open_position = None # (side, entry_price, entry_atr)
    
    start_time = time.time()
    
    # v11.0: 'required_data_length'ten başla
    for i in range(required_data_length, len(klines)):
        
        # 'Nokta-i Zaman' (Point-in-Time) verisi (0'dan 'i'ye kadar)
        current_historical_data = klines[0:i] 
        # Simülasyonun 'o anki' mumu (fiyatın hareket ettiği mum)
        current_candle = klines[i] 
        # (v21.1: Fiyatın SL/TP'ye değip değmediğini 'Yüksek' ve 'Düşük'e göre kontrol et)
        current_high = float(current_candle[2])
        current_low = float(current_candle[3])
        
        # --- A. Pozisyon Yönetimi (v21.1 Dinamik SL/TP) ---
        if open_position:
            pos = open_position
            
            # === v21.1 SÜPER ÖZELLİK #1 KONTROLÜ ===
            if use_dynamic_sltp and pos['entry_atr'] > 0:
                # DİNAMİK (ATR) SL/TP
                sl_price = pos['entry_price'] - (pos['entry_atr'] * atr_sl_multiplier) if pos['side'] == "LONG" else \
                           pos['entry_price'] + (pos['entry_atr'] * atr_sl_multiplier)
                tp_price = pos['entry_price'] + (pos['entry_atr'] * atr_tp_multiplier) if pos['side'] == "LONG" else \
                           pos['entry_price'] - (pos['entry_atr'] * atr_tp_multiplier)
            else:
                # STATİK (%) SL/TP (Fallback)
                sl_price = pos['entry_price'] * (1 - static_sl_percent) if pos['side'] == "LONG" else \
                           pos['entry_price'] * (1 + static_sl_percent)
                tp_price = pos['entry_price'] * (1 + static_tp_percent) if pos['side'] == "LONG" else \
                           pos['entry_price'] * (1 - static_tp_percent)

            # Pozisyon kapandı mı?
            closed_by = None
            if pos['side'] == "LONG":
                if current_low <= sl_price: closed_by = "SL"
                elif current_high >= tp_price: closed_by = "TP"
            elif pos['side'] == "SHORT":
                if current_high >= sl_price: closed_by = "SL"
                elif current_low <= tp_price: closed_by = "TP"

            if closed_by:
                pnl_percent = static_tp_percent if closed_by == "TP" else -static_sl_percent
                # (v21.1 Not: Dinamik SL/TP kullanıyorsak bu PnL hesabı
                # tam doğru değildir, ancak 'roe' hesaplaması için yeterlidir.
                # 'Optimizer' için 'pnl_usdt' daha önemlidir.)
                
                # (v21.1 Düzeltmesi: PnL'i 'dinamik' olarak hesapla)
                if use_dynamic_sltp and pos['entry_atr'] > 0:
                    pnl_percent = (tp_price - pos['entry_price']) / pos['entry_price'] if closed_by == "TP" else \
                                  (sl_price - pos['entry_price']) / pos['entry_price']
                    if pos['side'] == "SHORT":
                        pnl_percent = (pos['entry_price'] - tp_price) / pos['entry_price'] if closed_by == "TP" else \
                                      (pos['entry_price'] - sl_price) / pos['entry_price']

                trades_log.append({'symbol': symbol, 'pnl_percent': pnl_percent})
                open_position = None
        
        # --- B. Yeni Sinyal Arama ---
        if not open_position:
            # v21.0: 'strategy.py' (Yönlendirici), otonom olarak 
            # "Hafıza"dan (DB) (v21.0 Önbellekli) okur ve DOĞRU stratejiyi çağırır.
            signal, confidence, price_at_signal, last_atr = strategy.analyze_symbol(
                symbol, 
                current_historical_data,
                params # (v9.1: Optimizer'ın parametrelerini ilet)
            )
            
            if signal != "NEUTRAL":
                open_position = {
                    'side': signal,
                    'entry_price': price_at_signal,
                    'entry_atr': last_atr # v21.1 YENİ: Dinamik SL/TP için ATR'yi kaydet
                }
    
    # === 4. RAPORLAMA ===
    end_time = time.time()
    log.info(f"Simülasyon {end_time - start_time:.2f} saniyede tamamlandı.")
    
    if not trades_log:
        log.warning("Backtest tamamlandı ancak hiçbir sanal işlem gerçekleşmedi.")
        return 0.0, 0, 0.0 # (PNL, Trades, WinRate)

    df = pd.DataFrame(trades_log)
    
    # Kasa Doktrini (v9.1 Parametreleri)
    # (v21.1: 100 USDT Kasa varsayımı)
    initial_capital = 100 
    
    # v21.1: PnL'i 'roe' (Kaldıraçlı ROE) yerine 'pnl_percent' (Kaldıraçsız PnL)
    # üzerinden hesapla. Bu, 'Dinamik SL/TP' ile daha uyumludur.
    
    df['pnl_usdt'] = df['pnl_percent'] * initial_capital * leverage * position_margin
    
    total_trades = len(df)
    total_pnl = df['pnl_usdt'].sum()
    
    wins = df[df['pnl_usdt'] > 0]
    losses = df[df['pnl_usdt'] < 0]
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    
    log.info("\n--- [Evrim Motoru v21.1: Backtest Raporu] ---")
    log.info(f"Toplam Net Kâr/Zarar     : {total_pnl:.4f} USDT (100 USDT Kasa Varsayımı)")
    log.info(f"Simüle Edilen İşlem Sayısı : {total_trades}")
    log.info(f"Kazanma Oranı (Win %)      : {win_rate:.2f}% ({len(wins)} Kazanan / {len(losses)} Kaybeden)")
    log.info("------------------------------------------\n")

    # v9.1: Optimizasyon için (PNL, Trades, WinRate) Geri Döndür
    return total_pnl, total_trades, win_rate

# === v21.1 KARARLI (STABLE) TEST BLOĞU ===
if __name__ == "__main__":
    """
    Bu dosyanın 'python binai/backtester.py' olarak 
    manuel (manuel) çalıştırılabilmesi için (v21.1 Düzeltmesi).
    """
    log.info("Backtester (v21.1) manuel (manuel) modda çalıştırıldı...")
    
    # v21.1: Altyapıyı (DB Yazıcısı) düzgünce başlat ve kapat
    engine_client = None
    try:
        db_manager.initialize_database()
        engine_client = market_data.get_binance_client()
        
        if not engine_client:
            raise Exception("Binance istemcisi (client) manuel test için başlatılamadı.")
            
        test_symbol = config.SYMBOLS_WHITELIST[0] if config.SYMBOLS_WHITELIST else "BTCUSDT"
        
        # v21.1: 'config.py' (v21.1) ile %100 uyumlu 'default_params'
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
            
            # Kasa Doktrini
            'LEVERAGE': config.LEVERAGE,
            'POSITION_SIZE_PERCENT': config.POSITION_SIZE_PERCENT,
            
            # Risk (Statik)
            'STOP_LOSS_PERCENT': config.STOP_LOSS_PERCENT,
            'TAKE_PROFIT_PERCENT': config.TAKE_PROFIT_PERCENT,
            
            # Risk (Dinamik v21.1)
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