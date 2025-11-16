"""
BaseAI - BinAI Evrim Motoru (v21.1 - "Yaratıcı Zeka" Enterprise Core)
Optimizer (Faz 3)

v21.1 Yükseltmeleri (Enterprise+++):
- 'db_manager' (v21.0) Entegrasyonu: 'pd.read_sql_query' (DB Okuma) işlemi 
  'db_manager.get_db_connection(is_writer_thread=False)' (Sadece Okuma) 
  bağlantısını kullanacak şekilde düzeltildi. (Kritik Hata #1 Düzeltmesi)
- 'backtester' (v21.1) Entegrasyonu: 'backtester.run_backtest' çağrısındaki 
  'days_to_test' (kaldırılmış) parametresi (argümanı) silindi. 
  (Kritik Hata #2 Düzeltmesi)
- Kararlılık (Stability): 'if __name__ == "__main__":' bloğu, 'db_manager'ın 
  'Yazıcı Thread'ini (Writer Thread) 'temiz kapatma' (graceful shutdown) 
  yapacak şekilde 'try...finally' bloğu ile düzeltildi. 
  (Kritik Hata #3 Düzeltmesi)
- Parametre Bütünlüğü: '_get_current_parameters' (v21.1) fonksiyonu, 
  'config.py' (v21.1) dosyasındaki *tüm* parametreleri (Dinamik SL/TP dahil) 
  okuyacak şekilde yeniden yazıldı. (Kritik Hata #4 Düzeltmesi)
- Esneklik (Flexibility): 'Yaratıcı Zeka' (AI) istemi (Prompt), artık 
  'config.py'den gelen *tüm* parametreleri (gelecekte eklenecekler dahil) 
  otonom olarak optimize edebilecek şekilde 'dinamik' hale getirildi. 
  (Esneklik Yükseltmesi #5)
"""

import json
import re
import sys
import time
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple

# === BİNAİ MODÜLLERİ ===
try:
    from binai import config
    from binai.logger import log
    from binai import db_manager 
    from binai import market_data 
    from binai import backtester
    from binai import strategy # (Sadece 'backtester' tarafından dolaylı kullanılır)
except ImportError as e:
    print(f"KRİTİK HATA (optimizer.py): BinAI modülleri bulunamadı. {e}")
    sys.exit(1)

# === BASEAI (GEMINI) ENTEGRASYONU ===
try:
    from baseai.bridges.gemini import GeminiBridge
except ImportError:
    log.error("v18.1 KRİTİK HATA: 'BaseAIEngine' (GeminiBridge) bulunamadı.")
    GeminiBridge = None


def _generate_ai_driven_intent(symbol: str, klines_df: pd.DataFrame, recent_trades_df: pd.DataFrame, current_params: Dict) -> str:
    """
    v21.1: "BaseAIEngine" (Gemini Pro) için "Yaratıcı Zeka" (Creative)
    "Niyet" (Intent) istemini (Prompt) otonom olarak oluşturur.
    Artık 'current_params' (v21.1) sayesinde 'dinamik'tir.
    """
    klines_str = klines_df.to_csv(index=False)
    trades_str = recent_trades_df.to_csv(index=False)
    
    # v21.1: 'current_params' (v21.1) artık 'Dinamik SL/TP' ayarları dahil 
    # *tüm* parametreleri içerir.
    current_params_str = json.dumps(current_params, indent=2)
    
    intent = f"""
    NİYET (v21.1): Otonom Strateji Optimizasyonu.
    SEMbol: {symbol}
    MEVCUT PARAMETRELER (BAŞARISIZ):
    {current_params_str}
    
    SON 10 İŞLEM (HAFIZA - binai_tradelog.db):
    {trades_str}
    
    SON 1500 MUM (5m KLINE VERİSİ):
    {klines_str}
    
    GÖREV (BaseAIEngine - Gemini Pro):
    1. "SON 1500 MUM" verisini (Klines) ve "SON 10 İŞLEM" (Hafıza) verisini analiz et.
    2. "MEVCUT PARAMETRELER"in (v21.1) bu piyasa koşullarında (son 1500 mum) neden başarısız olduğunu "Fikir Yürüt" (Reasoning).
    
    3. (v21.1 YÜKSELTMESİ) Bu "SON 1500 MUM" verisi üzerinde "MEVCUT PARAMETRELER"den *daha kârlı* (daha yüksek Net PnL, daha yüksek Win Rate) olacak *YENİ* bir "parametre JSON" nesnesi *İCAT ET* (Invent).
    
    4. (v21.1 KURAL) Sadece "MEVCUT PARAMETRELER"de (yukarıda) listelenen 'anahtarları' (keys) kullan.
    5. (v21.1 KURAL) 'USE_DYNAMIC_SLTP' (Dinamik) 'True' ise, 'STOP_LOSS_PERCENT' (Statik) yerine 'ATR_STOP_LOSS_MULTIPLIER' (Dinamik) değerini optimize etmeye odaklan.
    
    ÇIKTI FORMATI (Sadece JSON):
    {{
      "reasoning": "[BaseAIEngine Fikir Yürütmesi: Mevcut parametreler (örn: MA 10/50) bu 'Yatay' (Ranging) piyasa (örn: ADX < 20) için çok yavaştı... 'Dinamik SLTP' (v21.1) (ATR * 2.0) çok dardı, (ATR * 3.0) olmalı...]",
      "invented_params": {{
        "FAST_MA_PERIOD": [Yeni Değer],
        "SLOW_MA_PERIOD": [Yeni Değer],
        "ADX_TREND_THRESHOLD": [Yeni Değer],
        "RANGING_RSI_OVERSOLD": [Yeni Değer],
        "RANGING_RSI_OVERBOUGHT": [Yeni Değer],
        
        "USE_DYNAMIC_SLTP": [True veya False],
        "ATR_STOP_LOSS_MULTIPLIER": [Yeni Değer (Eğer Dinamik=True ise)],
        "ATR_TAKE_PROFIT_MULTIPLIER": [Yeni Değer (Eğer Dinamik=True ise)],
        
        "STOP_LOSS_PERCENT": [Yeni Değer (Eğer Dinamik=False ise)],
        "TAKE_PROFIT_PERCENT": [Yeni Değer (Eğer Dinamik=False ise)]
        // ... (ve 'MEVCUT PARAMETRELER'deki diğer tüm anahtarlar)
      }}
    }}
    """
    return intent

def _parse_ai_response(ai_response: str) -> Tuple[Optional[str], Optional[Dict]]:
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
        json_str = ai_response.strip()
        
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
        log.error(f"v18.1: 'Yaratıcı Zeka' (AI) yanıtı ayrıştırılamadı: {e}", exc_info=True)
        return None, None

def _get_current_parameters(symbol: str) -> Dict[str, Any]:
    """
    v21.1 (YENİ): 'Hafıza'dan (DB v21.0) veya 'config.py'den (v21.1)
    *tüm* (complete) parametreleri okur.
    """
    
    # Adım 1: 'config.py' (v21.1) dosyasından *TÜM* varsayılanları (defaults) yükle
    # (Bu, 'backtester.py' (v21.1) 'main' bloğu ile %100 aynı olmalıdır)
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
        
        # Kasa Doktrini (Backtester için Gerekli)
        'LEVERAGE': config.LEVERAGE,
        'POSITION_SIZE_PERCENT': config.POSITION_SIZE_PERCENT,
        
        # Risk (Statik v6.1)
        'STOP_LOSS_PERCENT': config.STOP_LOSS_PERCENT,
        'TAKE_PROFIT_PERCENT': config.TAKE_PROFIT_PERCENT,
        
        # Risk (Dinamik v21.1)
        'USE_DYNAMIC_SLTP': config.USE_DYNAMIC_SLTP,
        'ATR_STOP_LOSS_MULTIPLIER': config.ATR_STOP_LOSS_MULTIPLIER,
        'ATR_TAKE_PROFIT_MULTIPLIER': config.ATR_TAKE_PROFIT_MULTIPLIER
    }
    
    # Adım 2: 'Hafıza'dan (DB v21.0 JSON) 'optimize edilmiş' (override) 
    # parametreleri al
    params_from_db = db_manager.get_strategy_params(symbol)
    
    if params_from_db:
        log.info(f"{symbol} için 'Hafıza' (DB v21.0) parametreleri bulundu. Varsayılanlar güncelleniyor.")
        # 'Varsayılan'ların (defaults) üzerine 'Hafıza'dakileri (DB) yaz
        default_params.update(params_from_db)
        return default_params
    else:
        log.info(f"{symbol} için 'Hafıza'da (DB) parametre bulunamadı. 'config.py' (v21.1) varsayılanları kullanılıyor.")
        return default_params


def run_optimizer() -> bool:
    """
    v21.1: "Evrim Motoru" (Faz 3). 
    'analyzer.py' (v21.1) tarafından 'Stale' (Bayatlamış) tespiti 
    yapıldığında 'main.py' (v21.1) tarafından çağrılır.
    """
    log.info("--- [Evrim Motoru v21.1: 'Yaratıcı Zeka' (AI-Driven) Optimizasyon Başlatıldı] ---")
    
    # (v21.1 Not: 'db_manager.initialize_database()' zaten 'main.py' (v21.1) 
    # veya 'run.py' (v2) tarafından *önceden* çağrılmıştır.)
    
    client = market_data.get_binance_client()
    if not client: 
        log.error("v21.1 BAŞARISIZ: Optimizer, Binance istemcisini (client) başlatamadı.")
        return False
        
    all_symbols = market_data.get_tradable_symbols(client)
    if not all_symbols: 
        log.error("v21.1 BAŞARISIZ: Optimizer, taranacak sembolleri (symbols) bulamadı.")
        return False
        
    # v18.1: Sadece 1 sembolü (API maliyetini düşürmek için)
    # (Gelecekte 'analyzer.py' (v21.1) 'en kötü' (worst) sembolü döndürebilir)
    symbols_to_optimize = all_symbols[:1] 
    log.info(f"v21.1: {len(symbols_to_optimize)} adet 'Yaratıcı Zeka' (AI-Driven) optimizasyon başlatılıyor...")
    
    total_optimized_symbols = 0
    conn = None # v21.1: DB Bağlantısı

    # === v18.1 "Yaratıcı Zeka" (AI-Driven) Döngü ===
    for symbol in symbols_to_optimize:
        try:
            log.info(f"--- [v21.1] 'Yaratıcı Zeka' (AI) Evrimi Başlıyor: {symbol} ---")
            
            # 1. Analiz için (v21.0) veriyi topla
            klines = market_data.get_klines(client, symbol, config.INTERVAL, config.DEEP_EVOLUTION_KLINE_LIMIT)
            if not klines or len(klines) < (config.MIN_KLINES_FOR_STRATEGY + 100): # (v21.1: 'config'den okur)
                log.error(f"{symbol} için optimizasyon verisi (Derin Evrim {config.DEEP_EVOLUTION_KLINE_LIMIT} mum) çekilemedi.")
                continue

            # 2. "Hafıza"yı (DB) (v21.1 - GÜVENLİ OKUMA) oku
            conn = db_manager.get_db_connection(is_writer_thread=False)
            if conn is None:
                log.error(f"{symbol} için 'Hafıza' (DB) okunamadı (DB Kilitli mi?). Evrim atlanıyor.")
                continue
            recent_trades_df = pd.read_sql_query(f"SELECT * FROM trades WHERE symbol = '{symbol}' ORDER BY id DESC LIMIT 10", conn)
            conn.close()
            conn = None # Bağlantıyı kapat

            # 3. Mevcut (v21.1 - TAM) parametreleri al
            current_params = _get_current_parameters(symbol)

            # 4. "Yaratıcı Zeka" (v21.1 - Dinamik) "Niyet" (Intent) oluştur
            klines_df_for_ai = pd.DataFrame(klines[-(1500):]) # (AI'ı (Gemini) 15000 mum ile boğma, son 1500'ü gönder)
            intent = _generate_ai_driven_intent(symbol, klines_df_for_ai, recent_trades_df, current_params)
            
            # 5. "BaseAIEngine" (Gemini Pro) ile Otonom İletişim Kur
            if not GeminiBridge:
                log.error("v18.1 BAŞARISIZ: 'BaseAIEngine' (GeminiBridge) yüklenemedi.")
                return False

            log.info(f"v18.1: {symbol} için 'Yaratıcı Zeka' (Gemini Pro) çağrılıyor... (Bu işlem zaman alabilir)")
            gemini = GeminiBridge()
            ai_response = gemini.generate_text_response(intent)
            
            # 6. "Yaratıcı Zeka" (v18.1) Yanıtını Ayrıştır (JSON Parsing)
            reasoning, invented_params = _parse_ai_response(ai_response)
            
            if not invented_params:
                log.error(f"v18.1: 'Yaratıcı Zeka' (AI) {symbol} için 'icat edilmiş' (invented) parametre döndürmedi. Evrim atlanıyor.")
                continue

            # 7. OTONOM DOĞRULAMA (v21.1 "Backtester" ile)
            log.info("--- [v21.1 OTONOM DOĞRULAMA (Backtester)] ---")
            
            # Test 1: Mevcut (Hatalı) Strateji
            log.info(f"v21.1: Test 1/2 - Mevcut (v21.1) parametreler ({symbol}) test ediliyor...")
            # (v21.1 DÜZELTMESİ: 'days_to_test' kaldırıldı)
            current_pnl, _, _ = backtester.run_backtest(symbol, params=current_params)
            log.info(f"v21.1: Mevcut (v21.1) PnL: {current_pnl:.4f} USDT")
            
            # Test 2: "Yaratıcı Zeka" (AI) Stratejisi
            log.info(f"v21.1: Test 2/2 - 'Yaratıcı Zeka' (v21.1) parametreleri ({symbol}) test ediliyor...")
            # (v21.1 DÜZELTMESİ: 'days_to_test' kaldırıldı)
            new_pnl, _, _ = backtester.run_backtest(symbol, params=invented_params)
            log.info(f"v21.1: 'Yaratıcı Zeka' (v21.1) PnL: {new_pnl:.4f} USDT")
            
            # 8. OTONOM KARAR (v21.1)
            # (v21.1 Not: '>= 0' (veya '>= current_pnl') kullanmak önemlidir. 
            # AI'ın en azından 'kötü' olanı 'daha az kötü' (sıfır) yapması da bir 'iyileştirme'dir.)
            if new_pnl > current_pnl:
                log.info(f"--- [v21.1 OTONOM KARAR: BAŞARILI] ---")
                log.info(f"'Yaratıcı Zeka' (AI) stratejisi ({new_pnl:.4f} USDT) > Mevcut (v21.1) strateji ({current_pnl:.4f} USDT).")
                log.info(f"v21.1: {symbol} için 'Hafıza' (DB v21.0 JSON) otonom olarak güncelleniyor...")
                # v21.1: 'Asenkron Yazıcı Sırası'na (Async Writer Queue) at (HIZLI)
                db_manager.save_strategy_params(symbol, invented_params)
                total_optimized_symbols += 1
            else:
                log.warning(f"--- [v21.1 OTONOM KARAR: REDDEDİLDİ] ---")
                log.warning(f"'Yaratıcı Zeka' (AI) stratejisi ({new_pnl:.4f} USDT) <= Mevcut (v21.1) strateji ({current_pnl:.4f} USDT).")
                log.warning(f"v21.1: 'Hafıza' (DB) güncellenmedi. Mevcut (v21.1) parametreler korunuyor.")

        except Exception as e:
            log.error(f"v21.1: {symbol} için 'Yaratıcı Zeka' (AI) Evrimi başarısız: {e}", exc_info=True)
        finally:
            if conn:
                conn.close() # Hata durumunda bağlantıyı kapat

    log.info(f"--- [Evrim Motoru v21.1: Optimizasyon Tamamlandı] ---")
    log.info(f"{total_optimized_symbols} adet sembol için 'Yaratıcı Zeka' (AI-Driven) parametreleri 'Hafıza'ya (DB) kaydedildi.")
    
    return True # v15.0: Başarıyı (True) döndür


# === v21.1 KARARLI (STABLE) TEST BLOĞU ===
if __name__ == "__main__":
    """
    Bu dosyanın 'python binai/optimizer.py' olarak 
    manuel (manuel) çalıştırılabilmesi için (v21.1 Düzeltmesi).
    """
    log.info("Optimizer (v21.1) manuel (manuel) modda çalıştırıldı...")
    
    # v21.1: Altyapıyı (DB Yazıcısı) düzgünce başlat ve kapat
    try:
        # v21.1: 'Yazıcı Thread'i (Writer Thread) BAŞLAT
        db_manager.initialize_database()
        
        # Testi çalıştır
        run_optimizer()
        
    except Exception as e:
        log.error(f"Optimizer manuel (manuel) test sırasında çöktü: {e}", exc_info=True)
    finally:
        # v21.1: 'Hafıza Yazıcısı'nı (DB Writer) temiz KAPAT
        log.info("Optimizer manuel (manuel) test tamamlandı. DB Yazıcısı kapatılıyor...")
        db_manager.shutdown_db_writer()