"""
BaseAI - BinAI v20.0 Mimari Yükseltmesi
"En Üst Düzey" (Highest Level) Mimari
(v15.0 "Sonsuz Otonomi" + v20.0 "Gerçek Zamanlı (WebSocket) Bellek İçi Önbellek")
"""
import time
import config
from logger import log
import market_data
import strategy # v15.0 Yönlendiricisi
import trade_manager
import db_manager
import analyzer # v14.0 Akıllı Analiz
import optimizer # v18.1 Evrim Motoru
import threading
import websocket_manager # v20.0 "Gerçek Zamanlı" (WebSocket) Motoru

# === v15.0 OTONOM EVRİM (Self-Healing) ===
OPTIMIZATION_INTERVAL_HOURS = config.OPTIMIZATION_INTERVAL_HOURS 
optimization_in_progress = False
last_optimization_time = 0

def run_autonomous_evolution_cycle():
    """
    v15.0: "Evrim Motoru"nu (Optimizer) otonom olarak (yeni bir thread'de) çalıştırır.
    (v20.0: Bu fonksiyon "Canlı Bot"tan (Live Bot) bağımsızdır)
    """
    global optimization_in_progress, last_optimization_time
    
    if optimization_in_progress:
        log.warning("v15.0: Otonom Evrim zaten çalışıyor. Yeni döngü atlanıyor.")
        return
        
    log.info("--- [v15.0 OTONOM EVRİM BAŞLATILDI] ---")
    optimization_in_progress = True
    try:
        log.info("v15.0: Adım 1/3 - Otonom 'Akıllı Analiz' (v14.0) çalıştırılıyor...")
        is_stale = analyzer.analyze_performance(is_autonomous_cycle=True)
        
        if is_stale:
            log.info("v15.0: Adım 2/3 - 'Bayatlamış Beyin' (Stale Brain) tespiti.")
            log.info("v15.0: 'Evrim Motoru' (v18.1 'Yaratıcı Zeka') çalıştırılıyor...")
            optimizer.run_optimizer() # v18.1 "Yaratıcı Zeka" (Gemini Pro) çağrısı
            
            log.info("v15.0: Adım 3/3 - 'Evrim Motoru' (v18.1) tamamlandı.")
            log.info("v15.0: 'Hafıza' (strategy_params.db) güncellendi.")
            log.info("v15.0: 'Sıfır Kesinti' (Zero Downtime) Evrimi tamamlandı.")
            last_optimization_time = time.time()
        else:
            log.info("v15.0: Adım 2/3 - Performans hedefler dahilinde. Optimizasyon gerekmiyor.")
            last_optimization_time = time.time()
            
    except Exception as e:
        log.error(f"v15.0: Otonom Evrim Döngüsü kritik hata: {e}")
    finally:
        optimization_in_progress = False

# === v20.0 "GERÇEK ZAMANLI" (Real-Time) CANLI BOT (Live Bot) ÇEKİRDEĞİ ===
def run_bot():
    global last_optimization_time
    log.info("BinAI Sistemi Başlatılıyor... (v20.0 'En Üst Düzey' Mimari)")
    
    db_manager.initialize_database()
    db_manager.initialize_strategy_db()

    client = market_data.get_binance_client()
    if not client:
        log.error("Binance istemcisi başlatılamadı. Sistem durduruluyor.")
        return
    exchange_rules = market_data.get_exchange_rules(client)
    if not exchange_rules:
        log.error("Borsa (Exchange Info) kuralları yüklenemedi. Sistem durduruluyor.")
        return

    # === v17.1 "SIFIR GÜVEN" (Zero Trust) PROTOKOLÜ ===
    trade_manager.cleanup_orphan_positions(client)
    
    # === v20.0 "GERÇEK ZAMANLI (WebSocket) MOTORU" ===
    # "WebSocket Motoru"nu (v20.0) "Bellek İçi Önbellek"i (v20.0)
    # doldurması için ayrı bir 'thread'de başlat.
    ws_thread = threading.Thread(target=websocket_manager.start_websocket_listener, daemon=True)
    ws_thread.start()
    
    log.info("v20.0: 'Gerçek Zamanlı (WebSocket) Önbelleği' (Cache) dolduruluyor... (Bu işlem zaman alabilir)")
    # (v20.0: 490+ sembolün *tümünün* (v19.0) önbelleğe (cache)
    # alınması (v19.0) için 1-2 dakika bekle)
    time.sleep(120) 
    
    log.info("Ana işlem döngüsü (v20.0 'Gerçek Zamanlı') başlatıldı. Çıkmak için Ctrl+C.")
    last_optimization_time = time.time()

    while True:
        try:
            # === v15.0 OTONOM ZAMANLAYICI (Autonomous Timer) ===
            current_time = time.time()
            if (current_time - last_optimization_time) > (OPTIMIZATION_INTERVAL_HOURS * 3600):
                evo_thread = threading.Thread(target=run_autonomous_evolution_cycle, daemon=True)
                evo_thread.start()
            
            # === v20.0 "GERÇEK ZAMANLI" (Real-Time) TİCARET (Trading) DÖNGÜSÜ ===
            
            # 1. (v17.1) Kapanan pozisyonları kontrol et (REST API - Gerekli)
            trade_manager.check_and_update_positions(client)
            
            # 2. (v20.0) "Bellek İçi Önbellek"ten (In-Memory Cache) sembolleri (490+) al
            # (Bu, v19.0'daki 'get_tradable_symbols' (REST API) çağrısını *kaldırır*)
            symbols_to_check = list(websocket_manager.klines_cache.keys())
            
            log.info(f"Analiz edilecek {len(symbols_to_check)} sembol var (v20.0 Bellek İçi Önbellek).")
            
            for symbol in symbols_to_check:
                
                # 3. (v20.0) Veriyi "Bellek İçi Önbellek"ten (In-Memory Cache) (RAM) al
                # (Bu, v19.0'daki 'get_klines' (REST API) çağrısını (490+ kez) *kaldırır*)
                klines = websocket_manager.get_klines_from_cache(symbol)
                
                if not klines or len(klines) < (config.SLOW_MA_PERIOD + config.ADX_PERIOD + 2):
                    continue # (Önbellek (Cache) henüz dolu değil)
                
                # 4. (v18.1) "Büyük Usta" (Grandmaster) Analizi
                signal, confidence, current_price = strategy.analyze_symbol(symbol, klines)
                
                if signal != "NEUTRAL":
                    # 5. (v17.1) "Büyük Usta" (Grandmaster) Emir Yönetimi
                    trade_manager.manage_risk_and_open_position(
                        client, symbol, signal, confidence, current_price, exchange_rules
                    )
            
            # v20.0: Artık 60 saniye (v19.0) değil, 5 saniye (v20.0) bekle
            log.info("Analiz döngüsü (v20.0) tamamlandı. 5 saniye bekleniyor...")
            time.sleep(5)

        except KeyboardInterrupt:
            log.info("Kullanıcı tarafından durduruldu (Ctrl+C). Sistem kapatılıyor.")
            websocket_manager.stop_websocket_listener()
            break
        except Exception as e:
            log.error(f"Ana döngüde kritik hata: {e}. 30 saniye sonra yeniden denenecek.")
            time.sleep(30)

run_bot()