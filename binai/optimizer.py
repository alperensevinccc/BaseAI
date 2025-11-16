"""
BaseAI - BinAI Evrim Motoru (v18.1 - "Yaratıcı Zeka" Yükseltmesi)
Optimizer (Faz 3)
(v18.1: "JSON Ayrıştırma" (JSON Parsing) ve "Otonom Doğrulama" (Backtester) eklendi)
"""
import backtester
import config
from logger import log
import itertools
import db_manager 
import market_data 
import json # v18.1: "Yaratıcı Zeka" (AI) yanıtını ayrıştırmak için
import re # v18.1: "Yaratıcı Zeka" (AI) yanıtını temizlemek için
import pandas as pd # v18.1: "Yaratıcı Zeka" (AI) Niyeti (Intent) için
import numpy as np

try:
    from baseai.bridges.gemini import GeminiBridge
except ImportError:
    log.error("v18.1 KRİTİK HATA: 'BaseAIEngine' (GeminiBridge) bulunamadı.")
    GeminiBridge = None

def _generate_ai_driven_intent(symbol, klines_data, recent_trades_df, current_params):
    """
    v18.1: "BaseAIEngine" (Gemini Pro) için "Yaratıcı Zeka" (Creative)
    "Niyet" (Intent) istemini (Prompt) otonom olarak oluşturur.
    """
    klines_str = pd.DataFrame(klines_data).to_csv(index=False)
    trades_str = recent_trades_df.to_csv(index=False)
    
    # v18.1: Mevcut (Hafıza'dan okunan) parametreleri al
    current_params_str = json.dumps(current_params, indent=2)
    
    intent = f"""
    NİYET (v18.1): Otonom Strateji Optimizasyonu.
    SEMbol: {symbol}
    MEVCUT PARAMETRELER (BAŞARISIZ):
    {current_params_str}
    
    SON 10 İŞLEM (HAFIZA - binai_tradelog.db):
    {trades_str}
    
    SON 1500 MUM (5m KLINE VERİSİ):
    {klines_str}
    
    GÖREV (BaseAIEngine - Gemini Pro):
    1. "SON 1500 MUM" verisini (Klines) ve "SON 10 İŞLEM" (Hafıza) verisini analiz et.
    2. "MEVCUT PARAMETRELER"in (v17.1) bu piyasa koşullarında (son 1500 mum) neden başarısız olduğunu "Fikir Yürüt" (Reasoning).
    3. Bu "SON 1500 MUM" verisi üzerinde "MEVCUT PARAMETRELER"den *daha kârlı* (daha yüksek Net PnL, daha yüksek Win Rate) olacak *YENİ* bir "parametre seti" (FAST_MA_PERIOD, SLOW_MA_PERIOD, ADX_TREND_THRESHOLD, RANGING_RSI_OVERSOLD, RANGING_RSI_OVERBOUGHT, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT) *İCAT ET* (Invent).
    
    ÇIKTI FORMATI (Sadece JSON):
    {{
      "reasoning": "[BaseAIEngine Fikir Yürütmesi: Mevcut parametreler (örn: MA 10/50) bu 'Yatay' (Ranging) piyasa (örn: ADX < 20) için çok yavaştı...]",
      "invented_params": {{
        "FAST_MA_PERIOD": [Yeni Değer],
        "SLOW_MA_PERIOD": [Yeni Değer],
        "ADX_TREND_THRESHOLD": [Yeni Değer],
        "RANGING_RSI_OVERSOLD": [Yeni Değer],
        "RANGING_RSI_OVERBOUGHT": [Yeni Değer],
        "STOP_LOSS_PERCENT": [Yeni Değer],
        "TAKE_PROFIT_PERCENT": [Yeni Değer]
      }}
    }}
    """
    return intent

def _parse_ai_response(ai_response):
    """
    v18.1: "BaseAIEngine" (Gemini Pro) yanıtını (JSON) ayrıştırır.
    (Gemini'nin Markdown (```json ... ```) sarmalayıcısını (wrapper) temizler)
    """
    log.debug(f"v18.1: 'Yaratıcı Zeka' (AI) Ham Yanıtı: {ai_response}")
    
    # Markdown (```json ... ```) sarmalayıcısını (wrapper) temizle
    match = re.search(r"```json\s*([\s\S]*?)\s*```", ai_response)
    if match:
        json_str = match.group(1)
    else:
        json_str = ai_response
        
    try:
        response_data = json.loads(json_str)
        
        # v18.1: Çıktı Formatı (v18.0 Niyet) doğrulaması
        if "reasoning" not in response_data or "invented_params" not in response_data:
            log.error("v18.1 HATA: 'Yaratıcı Zeka' (AI) yanıtı geçersiz format (Eksik 'reasoning' veya 'invented_params').")
            return None, None
            
        log.info(f"v18.1 'Yaratıcı Zeka' (AI) Fikir Yürütmesi: {response_data['reasoning']}")
        return response_data['reasoning'], response_data['invented_params']
        
    except json.JSONDecodeError as e:
        log.error(f"v18.1 KRİTİK HATA: 'Yaratıcı Zeka' (AI) yanıtı JSON formatında değil: {e}")
        log.error(f"v18.1: Alınan Hatalı Yanıt: {ai_response}")
        return None, None
    except Exception as e:
        log.error(f"v18.1: 'Yaratıcı Zeka' (AI) yanıtı ayrıştırılamadı: {e}")
        return None, None

def _get_current_parameters(symbol):
    """
    v18.1: "Hafıza"dan (DB) (v12.0) veya 'config.py'den (varsayılan)
    mevcut (v17.1) parametreleri okur.
    """
    params = db_manager.get_strategy_params(symbol)
    if not params:
        # "Hafıza" (DB) boşsa, 'config.py' (varsayılan) kullanılır
        params = {
            'FAST_MA_PERIOD': config.FAST_MA_PERIOD,
            'SLOW_MA_PERIOD': config.SLOW_MA_PERIOD,
            'ADX_TREND_THRESHOLD': config.ADX_TREND_THRESHOLD,
            'RANGING_RSI_OVERSOLD': config.RANGING_RSI_OVERSOLD,
            'RANGING_RSI_OVERBOUGHT': config.RANGING_RSI_OVERBOUGHT,
            'STOP_LOSS_PERCENT': config.STOP_LOSS_PERCENT,
            'TAKE_PROFIT_PERCENT': config.TAKE_PROFIT_PERCENT
        }
    return params

def run_optimizer():
    log.info("--- [Evrim Motoru v18.1: 'Yaratıcı Zeka' (AI-Driven) Optimizasyon Başlatıldı] ---")
    
    db_manager.initialize_database()
    db_manager.initialize_strategy_db()

    client = market_data.get_binance_client()
    if not client: return False
        
    all_symbols = market_data.get_tradable_symbols(client)
    if not all_symbols: return False
        
    symbols_to_optimize = all_symbols[:1] # v18.1: Sadece 1 sembolü (API maliyetini düşürmek için)
    log.info(f"v18.1: {len(symbols_to_optimize)} adet 'Yaratıcı Zeka' (AI-Driven) optimizasyon başlatılıyor...")
    
    total_optimized_symbols = 0

    # === v18.1 "Yaratıcı Zeka" (AI-Driven) Döngü ===
    for symbol in symbols_to_optimize:
        log.info(f"--- [v18.1] 'Yaratıcı Zeka' (AI) Evrimi Başlıyor: {symbol} ---")
        
        # 1. Analiz için (v11.0) veriyi topla
        klines = market_data.get_klines(client, symbol, config.INTERVAL, config.DEEP_EVOLUTION_KLINE_LIMIT)
        if not klines or len(klines) < (config.SLOW_MA_PERIOD + config.ADX_PERIOD + 100): # (v19.0: Yeterli "Derin Veri" (Deep Data) olduğunu doğrula)
            log.error(f"{symbol} için optimizasyon verisi (Derin Evrim {config.DEEP_EVOLUTION_KLINE_LIMIT} mum) çekilemedi.")
            continue

        # 2. "Hafıza"yı (DB) (v14.0) oku
        conn = db_manager.get_db_connection()
        recent_trades_df = pd.read_sql_query(f"SELECT * FROM trades WHERE symbol = '{symbol}' ORDER BY id DESC LIMIT 10", conn)
        conn.close()

        # 3. Mevcut (v17.1) parametreleri al
        current_params = _get_current_parameters(symbol)

        # 4. "Yaratıcı Zeka" (v18.0) "Niyet" (Intent) oluştur
        intent = _generate_ai_driven_intent(symbol, klines, recent_trades_df, current_params)
        
        # 5. "BaseAIEngine" (Gemini Pro) ile Otonom İletişim Kur
        if not GeminiBridge:
            log.error("v18.1 BAŞARISIZ: 'BaseAIEngine' (GeminiBridge) yüklenemedi.")
            return False

        try:
            log.info(f"v18.1: {symbol} için 'Yaratıcı Zeka' (Gemini Pro) çağrılıyor... (Bu işlem zaman alabilir)")
            gemini = GeminiBridge()
            ai_response = gemini.generate_text_response(intent)
            
            # 6. "Yaratıcı Zeka" (v18.1) Yanıtını Ayrıştır (JSON Parsing)
            reasoning, invented_params = _parse_ai_response(ai_response)
            
            if not invented_params:
                log.error(f"v18.1: 'Yaratıcı Zeka' (AI) {symbol} için 'icat edilmiş' (invented) parametre döndürmedi. Evrim atlanıyor.")
                continue

            # 7. OTONOM DOĞRULAMA (v18.1 "Backtester" ile)
            log.info("--- [v18.1 OTONOM DOĞRULAMA (Backtester)] ---")
            
            # Test 1: Mevcut (Hatalı) Strateji
            log.info(f"v18.1: Test 1/2 - Mevcut (v17.1) parametreler ({symbol}) test ediliyor...")
            current_pnl, _, _ = backtester.run_backtest(symbol, days_to_test=5, params=current_params)
            log.info(f"v18.1: Mevcut (v17.1) PnL: {current_pnl:.4f} USDT")
            
            # Test 2: "Yaratıcı Zeka" (AI) Stratejisi
            log.info(f"v18.1: Test 2/2 - 'Yaratıcı Zeka' (v18.1) parametreleri ({symbol}) test ediliyor...")
            new_pnl, _, _ = backtester.run_backtest(symbol, days_to_test=5, params=invented_params)
            log.info(f"v18.1: 'Yaratıcı Zeka' (v18.1) PnL: {new_pnl:.4f} USDT")
            
            # 8. OTONOM KARAR (v18.1)
            if new_pnl > current_pnl:
                log.info(f"--- [v18.1 OTONOM KARAR: BAŞARILI] ---")
                log.info(f"'Yaratıcı Zeka' (AI) stratejisi ({new_pnl:.4f} USDT) > Mevcut (v17.1) strateji ({current_pnl:.4f} USDT).")
                log.info(f"v18.1: {symbol} için 'Hafıza' (strategy_params.db) otonom olarak güncelleniyor...")
                db_manager.save_strategy_params(symbol, invented_params)
                total_optimized_symbols += 1
            else:
                log.warning(f"--- [v18.1 OTONOM KARAR: REDDEDİLDİ] ---")
                log.warning(f"'Yaratıcı Zeka' (AI) stratejisi ({new_pnl:.4f} USDT) <= Mevcut (v17.1) strateji ({current_pnl:.4f} USDT).")
                log.warning(f"v18.1: 'Hafıza' (DB) güncellenmedi. Mevcut (v17.1) parametreler korunuyor.")

        except Exception as e:
            log.error(f"v18.1: {symbol} için 'Yaratıcı Zeka' (AI) Evrimi başarısız: {e}")

    log.info(f"--- [Evrim Motoru v18.1: Optimizasyon Tamamlandı] ---")
    log.info(f"{total_optimized_symbols} adet sembol için 'Yaratıcı Zeka' (AI-Driven) parametreleri 'Hafıza'ya (DB) kaydedildi.")
    
    return True # v15.0: Başarıyı (True) döndür


if __name__ == "__main__":
    run_optimizer()