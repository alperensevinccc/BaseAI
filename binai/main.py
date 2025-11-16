"""
BaseAI - BinAI v21.1 Mimari Yükseltmesi
"Kurumsal Çekiredek" (Enterprise Core) Mimari

v21.1 Yükseltmeleri (Enterprise+++):
- 'db_manager.py' (v21.0) Entegrasyonu: 'shutdown()' metoduna 
  'db_manager.shutdown_db_writer()' çağrısı eklendi.
  Bu, 'Asenkron Yazıcı Thread'in (Async Writer Thread) 'temiz kapatma' 
  (graceful shutdown) yapmasını garanti eder.
"""

# === 1. KURULUM (GEREKLİ KÜTÜPHANELER) ===
import time
import threading
import sys
from typing import Optional, Dict, Any

# === 2. BİNAİ MODÜLLERİNİ İÇERİ AKTARMA ===
# Bu modüllerin 'binai' klasörü içinde olduğunu varsayıyoruz.
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
    # Bu kritik bir hatadır. Eğer 'binai' klasörü Python path'inde değilse
    # (örn: 'pip install -e .' yapılmadıysa) bu hata oluşur.
    print(f"KRİTİK HATA (main.py): BinAI modülleri bulunamadı. {e}")
    print("Lütfen 'run.py' dosyasını ana dizinden çalıştırdığınızdan emin olun.")
    sys.exit(1)


# === 3. ANA MOTOR SINIFI (BİNAI ENTERPRISE CORE) ===

class BinAIEngine:
    """
    BinAI (v21.1) sisteminin ana motor sınıfı.
    Tüm durumları (state) ve alt sistemleri (threads) yönetir.
    """
    
    def __init__(self):
        log.info("BinAI Motoru (v21.1 'Kurumsal Çekirdek') başlatılıyor...")
        
        # --- Durum (State) Yönetimi ---
        self.optimization_in_progress: bool = False
        self.last_optimization_time: float = 0.0
        self.main_loop_running: bool = True

        # --- Alt Sistem Bileşenleri ---
        self.client: Optional[Any] = None  # Binance Client
        self.exchange_rules: Optional[Dict[str, Any]] = None
        self.ws_thread: Optional[threading.Thread] = None

    def _initialize_systems(self) -> bool:
        """Tüm veritabanlarını ve Binance API bağlantısını başlatır."""
        try:
            # v21.1 Not: 'initialize_database()' artık 'Yazıcı Thread'i (Writer Thread)
            # otonom olarak (otomatik) başlatır.
            log.info("Adım 1/5: Veritabanları ve 'Hafıza Yazıcısı' (v21.0) başlatılıyor...")
            db_manager.initialize_database()
            # (initialize_strategy_db() artık 'initialize_database' içinden çağrılıyor)

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
        """v20.0 WebSocket Motorunu ayrı bir Thread'de başlatır."""
        log.info("v20.0: 'Gerçek Zamanlı (WebSocket) Motoru' başlatılıyor (arka planda)...")
        self.ws_thread = threading.Thread(
            target=websocket_manager.start_websocket_listener, 
            daemon=True  # Ana program kapanınca bu thread'in de kapanmasını sağlar
        )
        self.ws_thread.start()

    def _wait_for_cache_readiness(self, timeout_sec: int = 180) -> bool:
        """
        v21.0 'Akıllı Bekleme': Körü körüne 120sn beklemek yerine, 
        WebSocket önbelleğinin dolmasını aktif olarak bekler.
        """
        log.info(f"v21.0: 'Gerçek Zamanlı Önbellek' (Cache) bekleniyor...")
        log.info(f"(Hedef: en az {config.MIN_CACHE_SYMBOLS} sembol. Zaman aşımı: {timeout_sec}sn)")
        
        start_time = time.time()
        
        while True:
            try:
                # 'websocket_manager.py' (v21.0) içindeki 'is_cache_ready'
                # fonksiyonunu çağırıyoruz.
                is_ready = websocket_manager.is_cache_ready(config.MIN_CACHE_SYMBOLS)
            
            except Exception as e:
                log.error(f"'is_cache_ready' kontrolü sırasında hata: {e}", exc_info=True)
                time.sleep(5)
                continue

            if is_ready:
                ready_time = time.time() - start_time
                log.info(f"v21.0: Önbellek {ready_time:.1f} saniyede hazırlandı. Ana döngü başlıyor.")
                return True

            if (time.time() - start_time) > timeout_sec:
                log.critical(f"v21.0: Önbellek {timeout_sec} saniyede hazır olamadı! Sistem durduruluyor.")
                log.critical("Olası sebepler: İnternet bağlantısı, Binance API sorunu veya config.MIN_CACHE_SYMBOLS çok yüksek.")
                return False

            log.info(f"v21.0: Önbellek dolduruluyor... ({websocket_manager.get_cache_size()} / {config.MIN_CACHE_SYMBOLS} sembol)")
            time.sleep(5) # 5 saniyede bir tekrar kontrol et

    def _run_autonomous_evolution_cycle(self):
        """v15.0 Otonom Evrim Motoru (Ayrı Thread'de çalışır)."""
        if self.optimization_in_progress:
            log.warning("v15.0: Otonom Evrim zaten çalışıyor. Yeni döngü atlanıyor.")
            return
            
        log.info("--- [v15.0 OTONOM EVRİM BAŞLATILDI] ---")
        self.optimization_in_progress = True
        try:
            log.info("v15.0: Adım 1/3 - Otonom 'Akıllı Analiz' (v14.0) çalıştırılıyor...")
            is_stale = analyzer.analyze_performance(is_autonomous_cycle=True)
            
            if is_stale:
                log.info("v15.0: Adım 2/3 - 'Bayatlamış Beyin' (Stale Brain) tespiti.")
                log.info("v15.0: 'Evrim Motoru' (v18.1 'Yaratıcı Zeka') çalıştırılıyor...")
                optimizer.run_optimizer()
                
                log.info("v15.0: Adım 3/3 - 'Evrim Motoru' (v18.1) tamamlandı.")
                log.info("v15.0: 'Hafıza' (strategy_params.db) güncellendi.")
                self.last_optimization_time = time.time()
            else:
                log.info("v15.0: Adım 2/3 - Performans hedefler dahilinde. Optimizasyon gerekmiyor.")
                self.last_optimization_time = time.time()
                
        except Exception as e:
            log.error(f"v15.0: Otonom Evrim Döngüsü kritik hata: {e}", exc_info=True)
        finally:
            self.optimization_in_progress = False
            log.info("--- [v15.0 OTONOM EVRİM TAMAMLANDI] ---")

    def _run_main_trade_loop(self):
        """v21.0 Gerçek Zamanlı (Real-Time) Ticaret Döngüsü."""
        
        log.info("Ana işlem döngüsü (v21.1 'Kurumsal Çekirdek') başlatıldı. Çıkmak için Ctrl+C.")
        self.last_optimization_time = time.time()

        while self.main_loop_running:
            try:
                # === 1. OTONOM EVRİM ZAMANLAYICI (v15.0) ===
                current_time = time.time()
                if (current_time - self.last_optimization_time) > (config.OPTIMIZATION_INTERVAL_HOURS * 3600):
                    log.info("v15.0: Otonom Evrim zamanı geldi. Ayrı bir thread başlatılıyor...")
                    evo_thread = threading.Thread(target=self._run_autonomous_evolution_cycle, daemon=True)
                    evo_thread.start()
                    # Zamanlayıcıyı hemen sıfırla ki tekrar tetiklenmesin
                    self.last_optimization_time = current_time 
            
                # === 2. GERÇEK ZAMANLI TİCARET DÖNGÜSÜ (v21.0) ===
                
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
                        # (Önbellek (Cache) henüz dolu değil veya strateji için yetersiz veri)
                        continue 
                    
                    # 2.4. (v21.0) "Büyük Usta" (Grandmaster) Analizi
                    # (Dönen Değerler: signal, confidence, current_price, last_atr)
                    signal, confidence, current_price, last_atr = strategy.analyze_symbol(symbol, klines)
                    
                    if signal != "NEUTRAL":
                        # 2.5. (v21.0) "Büyük Usta" (Grandmaster) Emir Yönetimi
                        # (Artık 'last_atr' (Volatilite) verisini de iletiyor)
                        trade_manager.manage_risk_and_open_position(
                            client=self.client, 
                            symbol=symbol, 
                            signal=signal, 
                            confidence=confidence, 
                            current_price=current_price, 
                            last_atr=last_atr, # v21.0 YENİ (Dinamik SL/TP için)
                            exchange_rules=self.exchange_rules
                        )
                
                log.info(f"Analiz döngüsü (v21.1) tamamlandı. {config.MAIN_LOOP_SLEEP_SECONDS} saniye bekleniyor...")
                time.sleep(config.MAIN_LOOP_SLEEP_SECONDS)

            except KeyboardInterrupt:
                log.info("Ana döngüde 'Ctrl+C' algılandı. Kapatma işlemi başlatılıyor.")
                self.main_loop_running = False # Döngüyü durdur
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
            self.shutdown() # WebSocket'i ve DB'yi düzgünce kapat
            return
            
        # Ana Ticaret Döngüsü (Bloklayan kısım)
        self._run_main_trade_loop()

    def shutdown(self):
        """Sistemi 'temiz' (gracefully) kapatır."""
        log.warning("BinAI Motoru (v21.1) kapatma işlemi başlatılıyor...")
        self.main_loop_running = False
        
        # === v21.1 TEMİZ KAPATMA (GRACEFUL SHUTDOWN) ===
        
        # 1. WebSocket'i durdur (Yeni veri gelmesin)
        log.info("WebSocket Yöneticisi durduruluyor...")
        websocket_manager.stop_websocket_listener()
        
        # 2. Veritabanı Yazıcısını (DB Writer) durdur (Sıradaki (Queue) işleri bitirsin)
        log.info("v21.1: 'Hafıza' (DB) Yazıcı Thread'i durduruluyor...")
        db_manager.shutdown_db_writer()
        # === v21.1 YÜKSELTME SONU ===
        
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5)
            if self.ws_thread.is_alive():
                log.error("WebSocket thread'i 5 saniyede kapanmadı!")
        
        log.info("BinAI Motoru (v21.1) başarıyla durduruldu.")


# === 4. BAŞLATMA NOKTASI (ENTRY POINT) ===
def main():
    """
    Bu, 'binai/main.py' dosyasının ana başlatma fonksiyonudur.
    'run.py' tarafından çağırıldığında DEĞİL, doğrudan çalıştırıldığında kullanılır.
    """
    engine = BinAIEngine()
    try:
        engine.run()
    except KeyboardInterrupt:
        log.info("Dış (main) KeyboardInterrupt algılandı. Kapatılıyor.")
    except Exception as e:
        log.critical(f"Motor 'main' fonksiyonunda yakalanamayan kritik hata: {e}", exc_info=True)
    finally:
        # 'engine.run()' içindeki döngüden çıkılsa veya hata olsa bile,
        # bu 'shutdown' metodunun çağrılmasını garanti eder.
        engine.shutdown()

if __name__ == "__main__":
    main()