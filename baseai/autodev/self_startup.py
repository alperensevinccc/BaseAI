# baseai/autodev/self_startup.py
"""
BaseAI Otonom Geliştirme (AutoDev) Döngüsü Başlatıcısı (Nihai Sürüm).

Bu betik, `python -m baseai.autodev.self_startup` komutuyla çalıştırıldığında,
yapılandırılmış ana otonom geliştirme döngüsünü başlatır, yönetir,
sinyal işlemlerini ele alır ve sistemin genel yaşam döngüsünü kontrol eder.
"""

import asyncio
import time
import sys
import os
import signal
import importlib
from typing import Dict, Any, Optional, Callable, Awaitable

# Standart .env yükleyici
from dotenv import load_dotenv 

# BaseAI Çekirdek Bileşenleri
# Logger'ın varlığından emin olalım, yoksa fallback oluşturalım
try:
    from baseai.log.logger import core_logger as log
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    log = logging.getLogger("Startup_Fallback")
    log.warning("BaseAI core_logger bulunamadı. Fallback logger kullanılıyor.")

# --- Yapılandırma ve Sabitler ---

# Proje kök dizinini belirle (bu dosyanın iki üst dizini)
PROJECT_ROOT_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ortam değişkenlerinden veya varsayılanlardan döngü ayarlarını oku
DEFAULT_ERROR_DELAY: int = 60      # Hata sonrası bekleme (saniye)
DEFAULT_SUCCESS_DELAY: int = 900   # Başarı sonrası bekleme (saniye)
DEFAULT_LOOP_FUNCTION: str = "baseai.autodev.self_heal_loop.run_once" # Varsayılan döngü

try:
    ERROR_RETRY_DELAY_SEC: int = int(os.getenv('AUTODEV_ERROR_DELAY', str(DEFAULT_ERROR_DELAY)))
    SUCCESS_LOOP_DELAY_SEC: int = int(os.getenv('AUTODEV_SUCCESS_DELAY', str(DEFAULT_SUCCESS_DELAY)))
    # Hangi döngü fonksiyonunun çalıştırılacağını belirle
    AUTODEV_LOOP_FUNCTION_PATH: str = os.getenv('AUTODEV_LOOP_FUNCTION', DEFAULT_LOOP_FUNCTION) 
except ValueError:
    log.warning("AUTODEV_ERROR_DELAY veya AUTODEV_SUCCESS_DELAY geçersiz, varsayılanlar kullanılıyor.")
    ERROR_RETRY_DELAY_SEC = DEFAULT_ERROR_DELAY
    SUCCESS_LOOP_DELAY_SEC = DEFAULT_SUCCESS_DELAY
    AUTODEV_LOOP_FUNCTION_PATH = DEFAULT_LOOP_FUNCTION

# Ana döngü fonksiyonunu dinamik olarak import et
try:
    module_path, function_name = AUTODEV_LOOP_FUNCTION_PATH.rsplit('.', 1)
    log.debug(f"Dinamik import deneniyor: Modül='{module_path}', Fonksiyon='{function_name}'")
    module = importlib.import_module(module_path)
    main_autodev_loop_iteration: Callable[[], Awaitable[Optional[Dict[str, Any]]]] = getattr(module, function_name)
    log.info(f"Otonom geliştirme döngüsü olarak '{AUTODEV_LOOP_FUNCTION_PATH}' başarıyla yüklendi.")
except ImportError as e:
    log.critical(f"[Startup|FATAL] Belirtilen otonom döngü modülü ('{module_path}') bulunamadı: {e}")
    log.critical("BaseAI başlatılamıyor. Lütfen AUTODEV_LOOP_FUNCTION ortam değişkenini veya varsayılan değeri kontrol edin.")
    sys.exit(1)
except AttributeError as e:
    log.critical(f"[Startup|FATAL] Belirtilen otonom döngü fonksiyonu ('{function_name}') '{module_path}' modülünde bulunamadı: {e}")
    log.critical("BaseAI başlatılamıyor.")
    sys.exit(1)
except Exception as e:
    log.critical(f"[Startup|FATAL] Döngü fonksiyonu ('{AUTODEV_LOOP_FUNCTION_PATH}') yüklenirken beklenmedik hata: {e}", exc_info=True)
    sys.exit(1)

# Kapatma sinyallerini yönetmek için global bayrak
_shutdown_requested: asyncio.Event = asyncio.Event()

# --- Ana Döngü Yönetimi ---

async def reflex_loop():
    """
    Ana BaseAI otonom geliştirme (Reflex) döngüsünü yönetir.
    Yapılandırılmış döngü fonksiyonunu periyodik olarak çalıştırır,
    gecikmeleri yönetir ve kapatma sinyallerini dinler.
    """
    log.info(f"🔁 BaseAI Reflex Loop Başlatılıyor (Döngü: '{AUTODEV_LOOP_FUNCTION_PATH}').")
    log.info(f"   Başarı Sonrası Bekleme: {SUCCESS_LOOP_DELAY_SEC} saniye")
    log.info(f"   Hata Sonrası Bekleme  : {ERROR_RETRY_DELAY_SEC} saniye")
    
    iteration_count = 0
    while not _shutdown_requested.is_set():
        iteration_count += 1
        log.info(f"[Loop #{iteration_count}] Yeni otonom geliştirme iterasyonu başlıyor...")
        start_time = time.monotonic()
        
        try:
            # Ana otonom geliştirme fonksiyonunu çağır
            # Görevin iptal edilip edilmediğini kontrol etmek için bir zaman aşımı ekleyebiliriz (opsiyonel)
            result: Optional[Dict[str, Any]] = await asyncio.wait_for(
                main_autodev_loop_iteration(), 
                timeout=None # Şimdilik zaman aşımı yok
            ) 
            
            # Sonucun geçerli olup olmadığını kontrol et
            if not isinstance(result, dict):
                 log.error(f"[Loop #{iteration_count}] Döngü fonksiyonu geçersiz bir sonuç döndürdü (Tip: {type(result)}). Hata olarak değerlendiriliyor.")
                 result = {"success": False, "error": "Invalid return type from loop function"}

            # Başarı durumuna göre gecikmeyi belirle
            is_successful = result.get("success", False)
            current_delay = SUCCESS_LOOP_DELAY_SEC if is_successful else ERROR_RETRY_DELAY_SEC
            status_message = "BAŞARILI" if is_successful else f"BAŞARISIZ ({result.get('error', 'Bilinmeyen hata')})"
            
            end_time = time.monotonic()
            log.info(f"[Loop #{iteration_count}] İterasyon tamamlandı. Durum: {status_message}. Süre: {end_time - start_time:.2f}s.")
            
            # Kapatma istenmediyse bekle
            if not _shutdown_requested.is_set():
                log.info(f"[Loop #{iteration_count}] Sonraki iterasyon için {current_delay} saniye bekleniyor...")
                try:
                    # Kapatma olayını bekleyerek uyu
                    await asyncio.wait_for(_shutdown_requested.wait(), timeout=current_delay)
                    # Eğer buraya gelirse, bekleme sırasında kapatma istendi demektir
                    log.info("[Loop] Bekleme sırasında kapatma isteği alındı.")
                    break # Döngüden çık
                except asyncio.TimeoutError:
                    # Bekleme süresi doldu, sorun yok, döngü devam eder
                    pass 
                
        except asyncio.CancelledError:
             log.info("[Loop] Döngü iterasyonu iptal edildi (kapatma isteği).")
             break # Döngüden çıkış garantili
        except Exception as e:
            # Ana döngü fonksiyonu içindeki hatalar zaten loglanmış olmalı
            log.error(f"[Loop #{iteration_count}|FATAL] İterasyon sırasında yakalanamayan kritik hata: {e}", exc_info=True)
            if not _shutdown_requested.is_set():
                log.info(f"[Loop #{iteration_count}] Hata nedeniyle {ERROR_RETRY_DELAY_SEC} saniye bekleniyor...")
                try:
                    await asyncio.wait_for(_shutdown_requested.wait(), timeout=ERROR_RETRY_DELAY_SEC)
                    log.info("[Loop] Hata sonrası bekleme sırasında kapatma isteği alındı.")
                    break
                except asyncio.TimeoutError:
                    pass # Hata sonrası bekleme bitti, devam et

    log.info("🏁 BaseAI Reflex Loop Kapatıldı.")

# --- Sinyal Yönetimi ve Başlatma ---

def _handle_shutdown_signal(signum: int, loop: asyncio.AbstractEventLoop):
    """Kapatma sinyallerini (SIGINT, SIGTERM) yakalar ve kapatma olayını tetikler."""
    global _shutdown_requested
    if not _shutdown_requested.is_set():
        sig_name = signal.Signals(signum).name
        log.warning(f"🚨 Kapatma sinyali ({sig_name}) alındı. Döngü mevcut iterasyon/bekleme sonrası durdurulacak...")
        _shutdown_requested.set() # Olayı ayarla, bekleyen sleep'ler uyanacak
        # İkinci sinyalde zorla çıkış için ek bir mekanizma eklenebilir
        # Örneğin, 5 saniye sonra hala kapanmadıysa sys.exit çağıracak bir zamanlayıcı
    else:
         log.warning("🚨 Tekrarlanan kapatma sinyali alındı. Derhal çıkış zorlanıyor.")
         sys.exit(1)

async def main():
    """Asenkron ana giriş noktası. Yapılandırmayı yükler, sinyalleri ayarlar ve döngüyü başlatır."""
    
    # Kapatma sinyallerini ayarla
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_shutdown_signal, sig, loop)
        
    log.info("Kapatma sinyal yöneticileri ayarlandı (SIGINT, SIGTERM).")

    # .env dosyasını yüklemeyi dene
    try:
        env_path = os.path.join(PROJECT_ROOT_DIR, '.env')
        if os.path.exists(env_path):
            # override=False: Mevcut ortam değişkenlerini ezme
            # verbose=True: Yüklenen değişkenleri logla (DEBUG seviyesi için iyi)
            loaded = load_dotenv(dotenv_path=env_path, verbose=False, override=False) 
            if loaded:
                 log.info(f".env dosyası başarıyla yüklendi: {env_path}")
            else:
                 log.warning(f".env dosyası bulundu ancak boş veya yorum satırlarından oluşuyor: {env_path}")
        else:
            log.info(".env dosyası bulunamadı. Sadece çevresel değişkenler kullanılacak.")
    except Exception as e:
        log.error(f".env dosyası yüklenirken beklenmedik hata (opsiyonel): {e}", exc_info=True)

    # Ana döngüyü başlat ve bitmesini bekle
    main_loop_task = asyncio.create_task(reflex_loop())
    
    # Görevin bitmesini veya kapatma sinyalini bekle
    await _shutdown_requested.wait()
    
    # Kapatma istendi, ana döngü görevini iptal etmeyi dene (eğer hala çalışıyorsa)
    if not main_loop_task.done():
        log.info("Ana döngü görevi iptal ediliyor...")
        main_loop_task.cancel()
        try:
            # İptalin tamamlanmasını bekle (kısa bir süre)
            await asyncio.wait_for(main_loop_task, timeout=5.0) 
        except asyncio.CancelledError:
            log.info("Ana döngü görevi başarıyla iptal edildi.")
        except asyncio.TimeoutError:
             log.warning("Ana döngü görevi 5 saniye içinde iptal edilemedi. Zorla çıkış gerekebilir.")
        except Exception as e:
             log.error(f"Ana döngü iptal edilirken hata oluştu: {e}", exc_info=True)
             
    log.info("BaseAI ana görevi sonlandırıldı.")

if __name__ == "__main__":
    """
    'python -m baseai.autodev.self_startup' komutuyla çalıştırıldığında 
    bu blok tetiklenir. Asenkron döngüyü başlatır ve yönetir.
    """
    log.info(f"🚀 BaseAI Otonom Geliştirme Başlatıcısı Çalıştırılıyor...")
    log.info(f"   Proje Kök Dizini: {PROJECT_ROOT_DIR}")
    log.info(f"   Python Sürümü: {sys.version.split()[0]}")
    log.info(f"   Çalıştırılacak Döngü: {AUTODEV_LOOP_FUNCTION_PATH}")
    
    try:
        asyncio.run(main())
        log.info("👋 BaseAI Başlatıcısı Normal Şekilde Sonlandırıldı.")
        sys.exit(0) # Başarılı çıkış kodu
    except KeyboardInterrupt:
        # Sinyal yöneticisi bunu yakalamalı, burası fallback.
        log.info("KeyboardInterrupt (Ana Seviye) algılandı. Kapatılıyor...")
        sys.exit(0)
    except Exception as e:
        log.critical(f"💥 Başlatıcı (main) kritik bir hatayla çöktü: {e}", exc_info=True)
        sys.exit(1) # Başarısız çıkış kodu