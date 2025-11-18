"""
BaseAI - BinAI Evrim Motoru (v22.0 - "Yaratıcı Zeka" Enterprise Core)
Optimizer (Faz 3)

v22.0 Yükseltmeleri:
- STRATEJİ UYUMU: 'config.py' (v22.0) içindeki yeni parametrelerle 
  (EMA, MACD, Bollinger) tam uyumlu hale getirildi.
- Eski 'FAST_MA_PERIOD' vb. kaldırıldı.
- 'generate_text' entegrasyonu (Asenkron) korundu.
- 'Doctor' (Heal) modülü için 'analyze_logs_and_heal' fonksiyonu eklendi.
"""

import json
import re
import sys
import time
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
import asyncio # v22.0: Asenkron işlemler için

# === BİNAİ MODÜLLERİ ===
try:
    from binai import config
    from binai.logger import log
    from binai import db_manager 
    from binai import market_data 
    from binai import backtester
    from binai import strategy 
except ImportError as e:
    print(f"KRİTİK HATA (optimizer.py): BinAI modülleri bulunamadı. {e}")
    sys.exit(1)

# === BASEAI (GEMINI) ENTEGRASYONU ===
try:
    from baseai.bridges.gemini import GeminiBridge
except ImportError:
    log.error("v22.0 KRİTİK HATA: 'BaseAIEngine' (GeminiBridge) bulunamadı.")
    GeminiBridge = None


def _generate_ai_driven_intent(symbol: str, klines_df: pd.DataFrame, recent_trades_df: pd.DataFrame, current_params: Dict) -> str:
    """
    v22.0: Gemini Pro için "Niyet" (Intent) oluşturur.
    Artık yeni indikatörleri (MACD, BB, EMA) optimize etmesini ister.
    """
    klines_str = klines_df.to_csv(index=False)
    trades_str = recent_trades_df.to_csv(index=False)
    current_params_str = json.dumps(current_params, indent=2)
    
    intent = f"""
    NİYET (v22.0): Otonom Strateji Optimizasyonu.
    SEMbol: {symbol}
    MEVCUT PARAMETRELER (BAŞARISIZ/İYİLEŞTİRİLMELİ):
    {current_params_str}
    
    SON 10 İŞLEM (HAFIZA):
    {trades_str}
    
    SON 1500 MUM (5m KLINE VERİSİ):
    {klines_str}
    
    GÖREV (BaseAIEngine - Gemini Pro):
    1. Verileri analiz et.
    2. Mevcut parametrelerin (EMA, MACD, Bollinger, Risk) neden yetersiz kaldığını açıkla.
    3. Aşağıdaki parametreler için DAHA KÂRLI değerler İCAT ET (Invent):
    
    -- Trend Stratejisi --
    - EMA_FAST_PERIOD, EMA_SLOW_PERIOD
    - MACD_FAST, MACD_SLOW, MACD_SIGNAL
    - RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD
    
    -- Yatay Strateji --
    - BB_LENGTH, BB_STD (Bollinger)
    - RANGING_RSI_PERIOD, RANGING_RSI_OVERBOUGHT, RANGING_RSI_OVERSOLD
    
    -- Risk Yönetimi --
    - RISK_PER_TRADE_PERCENT (Süper Özellik #2)
    - ATR_STOP_LOSS_MULTIPLIER, ATR_TAKE_PROFIT_MULTIPLIER (Süper Özellik #1)
    
    ÇIKTI FORMATI (Sadece JSON):
    {{
      "reasoning": "...",
      "invented_params": {{ ... }}
    }}
    """
    return intent

def _parse_ai_response(ai_response: Any) -> Tuple[Optional[str], Optional[Dict]]:
    """v18.1: Yanıt ayrıştırıcı."""
    ai_text = str(ai_response)
    log.debug(f"v22.0: 'Yaratıcı Zeka' (AI) Ham Yanıtı: {ai_text[:100]}...") 
    
    match = re.search(r"```json\s*([\s\S]*?)\s*```", ai_text)
    if match:
        json_str = match.group(1)
    else:
        json_str = ai_text.strip()
        
    try:
        response_data = json.loads(json_str)
        if "reasoning" not in response_data or "invented_params" not in response_data:
            log.error("v22.0 HATA: 'Yaratıcı Zeka' (AI) yanıtı geçersiz format.")
            return None, None
            
        log.info(f"v22.0 'Yaratıcı Zeka' (AI) Fikir Yürütmesi: {response_data['reasoning']}")
        return response_data['reasoning'], response_data['invented_params']
        
    except json.JSONDecodeError as e:
        log.error(f"v22.0 KRİTİK HATA: 'Yaratıcı Zeka' (AI) yanıtı JSON formatında değil: {e}")
        return None, None
    except Exception as e:
        log.error(f"v22.0: 'Yaratıcı Zeka' (AI) yanıtı ayrıştırılamadı: {e}", exc_info=True)
        return None, None

def _get_current_parameters(symbol: str) -> Dict[str, Any]:
    """
    v22.0: 'config.py' (v22.0) içindeki YENİ parametreleri okur.
    """
    default_params = {
        'INTERVAL': config.INTERVAL,
        'MIN_SIGNAL_CONFIDENCE': config.MIN_SIGNAL_CONFIDENCE,
        
        # v22.0 YENİ: Trend (EMA + MACD)
        'EMA_FAST_PERIOD': config.EMA_FAST_PERIOD,
        'EMA_SLOW_PERIOD': config.EMA_SLOW_PERIOD,
        'MACD_FAST': config.MACD_FAST,
        'MACD_SLOW': config.MACD_SLOW,
        'MACD_SIGNAL': config.MACD_SIGNAL,
        'RSI_PERIOD': config.RSI_PERIOD,
        'RSI_OVERSOLD': config.RSI_OVERSOLD,
        'RSI_OVERBOUGHT': config.RSI_OVERBOUGHT,
        'VOLUME_AVG_PERIOD': config.VOLUME_AVG_PERIOD,
        
        # v22.0 YENİ: Yatay (Bollinger)
        'BB_LENGTH': config.BB_LENGTH,
        'BB_STD': config.BB_STD,
        'RANGING_RSI_PERIOD': config.RANGING_RSI_PERIOD,
        'RANGING_RSI_OVERSOLD': config.RANGING_RSI_OVERSOLD,
        'RANGING_RSI_OVERBOUGHT': config.RANGING_RSI_OVERBOUGHT,
        
        # Rejim
        'ADX_PERIOD': config.ADX_PERIOD,
        'ADX_TREND_THRESHOLD': config.ADX_TREND_THRESHOLD,
        
        # Kasa & Risk
        'LEVERAGE': config.LEVERAGE,
        'POSITION_SIZE_PERCENT': config.POSITION_SIZE_PERCENT,
        'STOP_LOSS_PERCENT': config.STOP_LOSS_PERCENT,
        'TAKE_PROFIT_PERCENT': config.TAKE_PROFIT_PERCENT,
        'USE_DYNAMIC_SLTP': config.USE_DYNAMIC_SLTP,
        'ATR_STOP_LOSS_MULTIPLIER': config.ATR_STOP_LOSS_MULTIPLIER,
        'ATR_TAKE_PROFIT_MULTIPLIER': config.ATR_TAKE_PROFIT_MULTIPLIER,
        'USE_DYNAMIC_POSITION_SIZING': config.USE_DYNAMIC_POSITION_SIZING,
        'RISK_PER_TRADE_PERCENT': config.RISK_PER_TRADE_PERCENT
    }
    
    params_from_db = db_manager.get_strategy_params(symbol)
    if params_from_db:
        log.info(f"{symbol} için 'Hafıza' (DB) parametreleri bulundu.")
        default_params.update(params_from_db)
    else:
        log.info(f"{symbol} için 'Hafıza'da parametre bulunamadı. Varsayılanlar kullanılıyor.")
        
    return default_params

# === v23.0 DOKTOR ENTEGRASYONU ===
def analyze_logs_and_heal(symbol: str, error_logs: str) -> bool:
    """
    v23.0: 'doctor.py' tarafından gönderilen hata/zarar loglarını analiz eder.
    """
    log.info(f"--- [v23.0 DOKTOR] {symbol} için Hata/Zarar Analizi Başlatıldı ---")
    
    if not GeminiBridge: return False
    current_params = _get_current_parameters(symbol)
    
    intent = f"""
    GÖREV: BinAI Otonom Hata Düzeltme ve İyileştirme (Doctor Mode).
    SORUNLU SEMBOL: {symbol}
    LOGLAR: {error_logs}
    PARAMETRELER: {json.dumps(current_params, indent=2)}
    GÖREVİN (Gemini): Sorunu analiz et ve parametreleri iyileştir (JSON).
    """
    
    try:
        gemini = GeminiBridge()
        # Senkron çağrı (şimdilik)
        if hasattr(gemini, 'generate_text'):
             # Eğer asenkron ise loop içinde çalıştır
             ai_response = asyncio.run(gemini.generate_text(intent))
        else:
             log.error("Bridge metodu bulunamadı")
             return False

        reasoning, new_params = _parse_ai_response(ai_response)
        
        if not new_params:
            log.error("Doktor reçete yazamadı.")
            return False
            
        log.info(f"v23.0 DOKTOR TEŞHİSİ: {reasoning}")
        updated_params = current_params.copy()
        updated_params.update(new_params)
        db_manager.save_strategy_params(symbol, updated_params)
        return True
    except Exception as e:
        log.error(f"Doktor hatası: {e}")
        return False


async def run_optimizer() -> bool:
    """
    v22.0: "Evrim Motoru" (Faz 3). Asenkron.
    """
    log.info("--- [Evrim Motoru v22.0: 'Yaratıcı Zeka' (AI-Driven) Optimizasyon Başlatıldı] ---")
    
    client = market_data.get_binance_client()
    if not client: return False
        
    all_symbols = market_data.get_tradable_symbols(client)
    if not all_symbols: return False
        
    symbols_to_optimize = all_symbols[:1] 
    log.info(f"v22.0: {len(symbols_to_optimize)} adet 'Yaratıcı Zeka' (AI-Driven) optimizasyon başlatılıyor...")
    
    total_optimized_symbols = 0
    conn = None 

    for symbol in symbols_to_optimize:
        try:
            log.info(f"--- [v22.0] 'Yaratıcı Zeka' (AI) Evrimi Başlıyor: {symbol} ---")
            
            # 1. Veri Topla
            klines = market_data.get_klines(client, symbol, config.INTERVAL, config.DEEP_EVOLUTION_KLINE_LIMIT)
            if not klines or len(klines) < (config.MIN_KLINES_FOR_STRATEGY + 100):
                log.error(f"{symbol} için optimizasyon verisi çekilemedi.")
                continue

            # 2. Hafıza (DB) Oku
            conn = db_manager.get_db_connection(is_writer_thread=False)
            if conn is None: continue
            recent_trades_df = pd.read_sql_query(f"SELECT * FROM trades WHERE symbol = '{symbol}' ORDER BY id DESC LIMIT 10", conn)
            conn.close()
            conn = None

            # 3. Niyet (Intent) Oluştur
            current_params = _get_current_parameters(symbol)
            klines_df_for_ai = pd.DataFrame(klines[-(1500):]) 
            intent = _generate_ai_driven_intent(symbol, klines_df_for_ai, recent_trades_df, current_params)
            
            # 4. Gemini Köprüsü
            if not GeminiBridge:
                log.error("v22.0 BAŞARISIZ: 'BaseAIEngine' (GeminiBridge) yüklenemedi.")
                return False

            log.info(f"v22.0: {symbol} için 'Yaratıcı Zeka' (Gemini Pro) çağrılıyor... (Bu işlem zaman alabilir)")
            gemini = GeminiBridge()
            
            # Asenkron çağrı (Kesin Çözüm)
            ai_response = await gemini.generate_text(intent)
            
            if not ai_response:
                log.error("v22.0: Gemini boş yanıt döndürdü.")
                continue
            
            reasoning, invented_params = _parse_ai_response(ai_response)
            
            if not invented_params:
                log.error(f"v22.0: 'Yaratıcı Zeka' (AI) parametre icat edemedi.")
                continue

            # 5. OTONOM DOĞRULAMA
            log.info("--- [v22.0 OTONOM DOĞRULAMA (Backtester)] ---")
            log.info(f"v22.0: Test 1/2 - Mevcut parametreler test ediliyor...")
            current_pnl, _, _ = backtester.run_backtest(symbol, params=current_params)
            log.info(f"v22.0: Mevcut PnL: {current_pnl:.4f} USDT")
            
            log.info(f"v22.0: Test 2/2 - 'Yaratıcı Zeka' parametreleri test ediliyor...")
            new_pnl, _, _ = backtester.run_backtest(symbol, params=invented_params)
            log.info(f"v22.0: 'Yaratıcı Zeka' PnL: {new_pnl:.4f} USDT")
            
            # 6. OTONOM KARAR
            if new_pnl > current_pnl:
                log.info(f"--- [v22.0 OTONOM KARAR: BAŞARILI] ---")
                log.info(f"'Yaratıcı Zeka' parametreleri daha kârlı ({new_pnl:.4f} > {current_pnl:.4f}). Hafıza güncelleniyor...")
                db_manager.save_strategy_params(symbol, invented_params)
                total_optimized_symbols += 1
            else:
                log.warning(f"--- [v22.0 OTONOM KARAR: REDDEDİLDİ] ---")
                log.warning("Yeni parametreler daha kötü veya eşit performans gösterdi.")

        except Exception as e:
            log.error(f"v22.0: {symbol} için 'Yaratıcı Zeka' (AI) Evrimi başarısız: {e}", exc_info=True)
        finally:
            if conn: conn.close() 

    log.info(f"--- [Evrim Motoru v22.0: Optimizasyon Tamamlandı] ---")
    log.info(f"{total_optimized_symbols} adet sembol için parametreler güncellendi.")
    return True

if __name__ == "__main__":
    log.info("Optimizer (v22.0) manuel modda çalıştırıldı...")
    try:
        db_manager.initialize_database()
        asyncio.run(run_optimizer())
    except Exception as e:
        log.error(f"Optimizer çöktü: {e}", exc_info=True)
    finally:
        db_manager.shutdown_db_writer()