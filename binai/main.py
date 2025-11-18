"""
BaseAI - BinAI v21.4 Mimarisi
"Kusursuz" (Flawless) Kurumsal Çekirdek (Enterprise Core)

v21.4 Yükseltmeleri (Enterprise+++):
- "Süper Özellik #4: Dinamik Korelasyon Filtresi" (Işık Hızı) Entegrasyonu.
- '_run_main_trade_loop' (v21.4) içindeki 'trade_manager.manage_risk_and_open_position' 
  çağrısı, 'get_klines_func=websocket_manager.get_klines_from_cache' 
  parametresini (argümanını) "enjekte" (inject) edecek şekilde güncellendi.
- Bu, 'trade_manager'ın (v21.4) korelasyonu (correlation) "API hızı" 
  (yavaş) yerine "RAM hızı" (ışık hızı) ile hesaplamasını sağlar.
- v21.3 "Reaktif Otonomi" (Reactive Autonomy) mantığı korundu.
"""

# === 1. KURULUM (GEREKLİ KÜTÜPHANELER) ===
import time
import threading
import sys
from typing import Optional, Dict, Any, Callable # v21.4: Callable eklendi

# === 2. BİNAİ MODÜLLERİNİ İÇERİ AKTARMA ===
try:
    from binai import config
    from binai.logger import log  # 'logger.py' dosyasından 'log' objesini al
    from binai import market_data
    from binai import strategy
    from binai import trade_manager
    from binai import db_manager
    from binai import analyzer
    from binai import optimizer
    from binai import websocket_manager
except ImportError as e:
    print(f"KRİTİK HATA (main.py): BinAI modülleri bulunamadı. {e}")
    print("Lütfen 'run.py' dosyasını ana dizinden çalıştırdığınızdan emin olun.")
    sys.exit(1)


# === 3. ANA MOTOR SINIFI (BİNAI ENTERPRISE CORE) ===

class BinAIEngine:
    """
    BinAI (v21.4) sisteminin ana motor sınıfı.
    "Kusursuz" (Flawless) mimari.
    """
    
    def __init__(self):
        log.info("BinAI Motoru (v21.4 'Kusursuz Çekirdek') başlatılıyor...")
        
        # --- Durum (State) Yönetimi ---
        self.optimization_in_progress: bool = False
        self.last_analysis_time: float = 0.0
        self.main_loop_running: bool = True
        self.doctor_thread = None

        # --- Alt Sistem Bileşenleri ---
        self.client: Optional[Any] = None
        self.exchange_rules: Optional[Dict[str, Any]] = None
        self.ws_thread: Optional[threading.Thread] = None

    def _initialize_systems(self) -> bool:
        """
        Tüm veritabanlarını ve Binance API bağlantısını başlatır.
        (v21.4'te değişiklik yok)
        """
        try:
            log.info("Adım 1/5: Veritabanları ve 'Hafıza Yazıcısı' (v21.0) başlatılıyor...")
            db_manager.initialize_database()

            log.info("Adım 2/5: Binance API istemcisi alınıyor...")
            self.client = market_data.get_binance_client()
            if not self.client:
                log.critical("Binance istemcisi başlatılamadı. API anahtarlarını kontrol edin.")
                return False

            log.info("Adım 3/5: Borsa (Exchange Info) kuralları yükleniyor...")
            self.exchange_rules = market_data.get_exchange_rules(self.client)
            if not self.exchange_rules:
                log.critical("Borsa kuralları yüklenemedi. API bağlantısını kontrol edin.")
                return False

            log.info("Adım 4/5: 'Sıfır Güven' (v17.1) Protokolü çalıştırılıyor...")
            trade_manager.cleanup_orphan_positions(self.client)
            
            log.info("Adım 5/5: Tüm sistemler başarıyla başlatıldı.")
            return True
        
        except Exception as e:
            log.critical(f"Sistem başlatılırken kritik hata: {e}", exc_info=True)
            return False

    def _start_websocket_manager(self):
        """
        v20.0 WebSocket Motorunu ayrı bir Thread'de başlatır.
        (v21.4'te değişiklik yok)
        """
        log.info("v20.0: 'Gerçek Zamanlı (WebSocket) Motoru' başlatılıyor (arka planda)...")
        self.ws_thread = threading.Thread(
            target=websocket_manager.start_websocket_listener, 
            daemon=True
        )
        self.ws_thread.start()

    def _wait_for_cache_readiness(self) -> bool:
        """
        v21.0 'Akıllı Bekleme': WebSocket önbelleğinin dolmasını aktif olarak bekler.
        (v21.4'te değişiklik yok)
        """
        log.info(f"v21.0: 'Gerçek Zamanlı Önbellek' (Cache) bekleniyor...")
        log.info(f"(Hedef: en az {config.MIN_CACHE_SYMBOLS} sembol. Zaman aşımı: 180sn)")
        
        start_time = time.time()
        
        while True:
            try:
                is_ready = websocket_manager.is_cache_ready(config.MIN_CACHE_SYMBOLS)
            
            except Exception as e:
                log.error(f"'is_cache_ready' kontrolü sırasında hata: {e}", exc_info=True)
                time.sleep(5)
                continue

            if is_ready:
                ready_time = time.time() - start_time
                log.info(f"v21.0: Önbellek {ready_time:.1f} saniyede hazırlandı. Ana döngü başlıyor.")
                return True

            if (time.time() - start_time) > 180:
                log.critical(f"v21.0: Önbellek 180 saniyede hazır olamadı! Sistem durduruluyor.")
                return False

            log.info(f"v21.0: Önbellek dolduruluyor... ({websocket_manager.get_cache_size()} / {config.MIN_CACHE_SYMBOLS} sembol)")
            time.sleep(5) 

    def _run_reactive_optimization_check(self):
        """
        v21.3 "SÜPER ÖZELLİK #3" (Reaktif Otonomi).
        (v21.4'te değişiklik yok)
        """
        if self.optimization_in_progress:
            log.warning("v21.3: Reaktif Analiz zaten çalışıyor. Yeni döngü atlanıyor.")
            return
            
        log.info("--- [v21.3 REAKTİF OTONOMİ KONTROLÜ BAŞLATILDI] ---")
        self.optimization_in_progress = True
        self.last_analysis_time = time.time() 
        
        try:
            log.info("v21.3: Adım 1/3 - Otonom 'Akıllı Analiz' (v21.1) çalıştırılıyor...")
            is_stale = analyzer.analyze_performance(is_autonomous_cycle=True)
            
            if is_stale:
                log.warning("v21.3: Adım 2/3 - 'Bayatlamış Beyin' (Stale Brain) TESPİT EDİLDİ.")
                log.warning("v21.3: 'ACİL DURUM OPTİMİZASYONU' tetikleniyor...")
                log.info("v21.3: 'Evrim Motoru' (v21.1 'Yaratıcı Zeka') çalıştırılıyor...")
                
                optimizer.run_optimizer() 
                
                log.info("v21.3: Adım 3/3 - 'Evrim Motoru' (v21.1) tamamlandı.")
                log.info("v21.3: 'Hafıza' (strategy_params.db) güncellendi.")
            else:
                log.info("v21.3: Adım 2/3 - Performans hedeflerin dahilinde. Optimizasyon gerekmiyor.")
            
        except Exception as e:
            log.error(f"v21.3: Reaktif Otonomi Döngüsü kritik hata: {e}", exc_info=True)
        finally:
            self.optimization_in_progress = False
            log.info("--- [v21.3 REAKTİF OTONOMİ KONTROLÜ TAMAMLANDI] ---")

    def _run_main_trade_loop(self):
        """v21.4 Gerçek Zamanlı (Real-Time) Ticaret Döngüsü."""
        
        log.info("Ana işlem döngüsü (v21.4 'Kusursuz Çekirdek') başlatıldı. Çıkmak için Ctrl+C.")
        self.last_analysis_time = time.time()

        while self.main_loop_running:
            try:
                # === 1. "SÜPER ÖZELLİK #3" ZAMANLAYICI (v21.3) ===
                current_time = time.time()
                analysis_interval_seconds = config.REACTIVE_ANALYSIS_INTERVAL_MINUTES * 60
                
                if (current_time - self.last_analysis_time) > analysis_interval_seconds:
                    log.info(f"v21.3: Reaktif Analiz (Stale Brain Check) zamanı geldi ({config.REACTIVE_ANALYSIS_INTERVAL_MINUTES}dk).")
                    
                    evo_thread = threading.Thread(target=self._run_reactive_optimization_check, daemon=True)
                    evo_thread.start()
            
                # === 2. GERÇEK ZAMANLI TİCARET DÖNGÜSÜ (v21.4) ===
                
                # 2.1. (v21.0) Kapanan pozisyonları kontrol ET ve anlık PnL'i GÜNCELLE
                trade_manager.check_and_update_positions(self.client)
                
                # 2.2. (v20.0) "Bellek İçi Önbellek"ten sembolleri al
                symbols_to_check = list(websocket_manager.klines_cache.keys())
                
                if not symbols_to_check:
                    log.warning("v21.0: Önbellekte analiz edilecek sembol yok. WebSocket çalışıyor mu? 5sn bekleniyor.")
                    time.sleep(5)
                    continue

                log.info(f"Analiz edilecek {len(symbols_to_check)} sembol var (v20.0 Bellek İçi Önbellek).")
                
                for symbol in symbols_to_check:
                    
                    # 2.3. (v20.0) Veriyi "Bellek İçi Önbellek"ten (RAM) al
                    klines = websocket_manager.get_klines_from_cache(symbol)
                    
                    if not klines or len(klines) < config.MIN_KLINES_FOR_STRATEGY:
                        continue 
                    
                    # 2.4. (v21.0) "Büyük Usta" (Grandmaster) Analizi
                    signal, confidence, current_price, last_atr = strategy.analyze_symbol(symbol, klines)
                    
                    if signal != "NEUTRAL":
                        
                        # === 2.5. (v21.4) "Büyük Usta" (Grandmaster) Emir Yönetimi ===
                        # (v21.4 YÜKSELTMESİ: "Süper Özellik #4" Entegrasyonu)
                        # 'trade_manager' (v21.4) fonksiyonuna "bana mum ver" (get_klines_func)
                        # fonksiyonunu "enjekte" (inject) et.
                        trade_manager.manage_risk_and_open_position(
                            client=self.client, 
                            symbol=symbol, 
                            signal=signal, 
                            confidence=confidence, 
                            current_price=current_price, 
                            last_atr=last_atr, # v21.1 (Dinamik SL/TP)
                            exchange_rules=self.exchange_rules,
                            get_klines_func=websocket_manager.get_klines_from_cache # v21.4 (Işık Hızı Korelasyon)
                        )
                
                log.info(f"Analiz döngüsü (v21.4) tamamlandı. {config.MAIN_LOOP_SLEEP_SECONDS} saniye bekleniyor...")
                time.sleep(config.MAIN_LOOP_SLEEP_SECONDS)

            except KeyboardInterrupt:
                log.info("Ana döngüde 'Ctrl+C' algılandı. Kapatma işlemi başlatılıyor.")
                self.main_loop_running = False
                break
            except Exception as e:
                log.error(f"Ana döngüde kritik hata: {e}. {config.CRITICAL_ERROR_SLEEP_SECONDS} saniye sonra yeniden denenecek.", exc_info=True)
                time.sleep(config.CRITICAL_ERROR_SLEEP_SECONDS)
        
        log.info("Ana işlem döngüsü durduruldu.")

    def run(self):
        """Motoru çalıştıran ana metod (Orkestratör)."""
        if not self._initialize_systems():
            log.critical("Sistem başlatılamadı. Çıkılıyor.")
            return

        self._start_websocket_manager()

        if not self._wait_for_cache_readiness():
            log.critical("Önbellek zaman aşımına uğradı. Çıkılıyor.")
            self.shutdown()
            return
            
        # === v23.1 DOKTORU BAŞLAT (AKTİF) ===
        from binai import doctor
        log.info("v23.1: Akıllı Doktor (Gözetmen) başlatılıyor...")
        self.doctor_thread = threading.Thread(target=doctor.start_doctor, daemon=True)
        self.doctor_thread.start()
        # =====================================

        self._run_main_trade_loop()


    def shutdown(self):
        """
        Sistemi 'temiz' (gracefully) kapatır.
        (v21.1 Entegrasyonu)
        """
        log.warning("BinAI Motoru (v21.4) kapatma işlemi başlatılıyor...")
        self.main_loop_running = False
        
        # === v21.1 TEMİZ KAPATMA (GRACEFUL SHUTDOWN) ===
        
        # 1. WebSocket'i durdur
        log.info("WebSocket Yöneticisi durduruluyor...")
        websocket_manager.stop_websocket_listener()
        
        # 2. Veritabanı Yazıcısını (DB Writer) durdur
        log.info("v21.1: 'Hafıza' (DB) Yazıcı Thread'i durduruluyor...")
        db_manager.shutdown_db_writer()
        # === v21.1 YÜKSELTME SONU ===
        
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5)
            if self.ws_thread.is_alive():
                log.error("WebSocket thread'i 5 saniyede kapanmadı!")
        
        log.info("BinAI Motoru (v21.4) başarıyla durduruldu.")


# === 4. BAŞLATMA NOKTASI (ENTRY POINT) ===
def main():
    """
    Bu, 'binai/main.py' dosyasının ana başlatma fonksiyonudur.
    """
    engine = BinAIEngine()
    try:
        engine.run()
    except KeyboardInterrupt:
        log.info("Dış (main) KeyboardInterrupt algılandı. Kapatılıyor.")
    except Exception as e:
        log.critical(f"Motor 'main' fonksiyonunda yakalanamayan kritik hata: {e}", exc_info=True)
    finally:
        engine.shutdown()

if __name__ == "__main__":
    main()