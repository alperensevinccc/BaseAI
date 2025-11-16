"""
BaseAI Enterprise+++ Çekirdek Başlatıcısı (Runner)
Sistemi interaktif modda başlatır.
BinAI Alt Sistem Yöneticisi entegrasyonu [v1.0] içerir.
"""
import asyncio
import logging
import sys
import subprocess  # EKLENDİ: Alt sistem yönetimi için
import os          # EKLENDİ: Alt sistem yollarını bulmak için

# Loglamayı temel düzeyde ayarla (config yüklenene kadar)
logging.basicConfig(level="INFO", format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("BaseAI_Runner")

try:
    from baseai.config import config
    if not config:
        logger.critical("Yapılandırma yüklenemedi. .env dosyasını kontrol edin.")
        sys.exit(1)
        
    from baseai.engine import BaseAIEngine
except ImportError as e:
    logger.critical(f"Kritik Hata: BaseAI motoru veya bileşenleri bulunamadı. {e}")
    logger.critical("Lütfen 'pip install -e .' komutu ile kurulum yaptığınızdan emin olun.")
    sys.exit(1)
except Exception as e:
    logger.critical(f"Beklenmedik başlatma hatası: {e}")
    sys.exit(1)

# === ALT SİSTEM YÖNETİCİSİ (EKLENDİ) ===

# BaseAI tarafından yönetilen aktif alt sistemlerin kaydı
# { "isim": { "process": Popen_objesi, "log_file": dosya_objesi } }
active_subsystems = {}

def start_subsystem(name: str):
    global active_subsystems
    name = name.lower()
    
    if name == "binai":
        if "binai" in active_subsystems and active_subsystems["binai"]["process"].poll() is None:
            print(f"[Core Runner] SİSTEM HATA: {name} alt sistemi zaten çalışıyor (PID: {active_subsystems['binai']['process'].pid}).")
            return

        script_path = os.path.join("binai", "main.py")
        log_path = os.path.join("binai", "binai_main_runtime.log") # Ayrı log dosyası
        
        if not os.path.exists(script_path):
            print(f"[Core Runner] SİSTEM HATA: {script_path} bulunamadı. BinAI modülleri eksik.")
            return

        try:
            print(f"[Core Runner] SİSTEM: {name} alt sistemi başlatılıyor...")
            print(f"[Core Runner] SİSTEM: Loglar şuraya yönlendirildi: {log_path}")
            
            log_file = open(log_path, "a", encoding="utf-8")
            
            process = subprocess.Popen(
                [sys.executable, script_path], # Mevcut python'u kullan
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            active_subsystems[name] = {"process": process, "log_file": log_file}
            print(f"[Core Runner] SİSTEM: {name} başarıyla başlatıldı. PID: {process.pid}")

        except Exception as e:
            print(f"[Core Runner] SİSTEM HATA: {name} başlatılamadı: {e}")
    else:
        print(f"[Core Runner] SİSTEM HATA: '{name}' adında tanımlı bir alt sistem yok.")

def stop_subsystem(name: str):
    global active_subsystems
    name = name.lower()

    if name not in active_subsystems or active_subsystems[name]["process"].poll() is not None:
        print(f"[Core Runner] SİSTEM HATA: {name} alt sistemi zaten çalışmıyor.")
        return

    print(f"[Core Runner] SİSTEM: {name} alt sistemi (PID: {active_subsystems[name]['process'].pid}) durduruluyor...")
    try:
        process_data = active_subsystems[name]
        process_data["process"].terminate()
        
        try:
            process_data["process"].wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"[Core Runner] SİSTEM UYARI: {name} 5 saniyede kapanmadı. Zorla sonlandırılıyor (SIGKILL)...")
            process_data["process"].kill()
            process_data["process"].wait()

        process_data["log_file"].close()
        del active_subsystems[name]
        print(f"[Core Runner] SİSTEM: {name} başarıyla durduruldu.")
        
    except Exception as e:
        print(f"[Core Runner] SİSTEM HATA: {name} durdurulurken hata oluştu: {e}")

def analyze_subsystem(name: str):
    # Otonom analiz motorunu tetikler (v6.0)
    name = name.lower()
    if name == "binai":
        script_path = os.path.join("binai", "analyzer.py")
        if not os.path.exists(script_path):
            print(f"[Core Runner] SİSTEM HATA: {script_path} analiz modülü bulunamadı.")
            return
            
        print(f"[Core Runner] SİSTEM: {name} Analiz Modülü çalıştırılıyor...")
        try:
            # Analiz betiğini çalıştır ve çıktısını DOĞRUDAN bu terminale yazdır
            # Bu, 'start' komutunun aksine 'run' kullanır ve bitmesini bekler.
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                encoding="utf-8"
            )
            
            # Çıktıyı yazdır
            print(result.stdout)
            if result.stderr:
                print(f"[Core Runner] Analiz Hatası:\n{result.stderr}")
                
        except Exception as e:
            print(f"[Core Runner] SİSTEM HATA: {name} analiz modülü çalıştırılamadı: {e}")
    else:
        print(f"[Core Runner] SİSTEM HATA: '{name}' için tanımlı bir analiz modülü yok.")  


def backtest_subsystem(name: str):
    # Evrim Motoru v9.0 (Faz 1) tetikler
    name = name.lower()
    if name == "binai":
        script_path = os.path.join("binai", "backtester.py")
        if not os.path.exists(script_path):
            print(f"[Core Runner] SİSTEM HATA: {script_path} backtester modülü bulunamadı.")
            return
            
        print(f"[Core Runner] SİSTEM: {name} Evrim Motoru (Backtest) çalıştırılıyor...")
        print("[Core Runner] Lütfen bekleyin, geçmiş veriler analiz ediliyor...")
        try:
            # Backtest betiğini çalıştır ve çıktısını DOĞRUDAN bu terminale yazdır
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                encoding="utf-8"
            )
            
            # Çıktıyı yazdır
            print(result.stdout)
            if result.stderr:
                print(f"[Core Runner] Backtest Hatası:\n{result.stderr}")
                
        except Exception as e:
            print(f"[Core Runner] SİSTEM HATA: {name} backtest modülü çalıştırılamadı: {e}")
    else:
        print(f"[Core Runner] SİSTEM HATA: '{name}' için tanımlı bir backtest modülü yok.")


# ... (backtest_subsystem fonksiyonunun bittiği yer) ...

def optimize_subsystem(name: str):
    # Evrim Motoru v18.0 (Faz 3) - "YARATICI ZEKA" (AI-Driven)
    name = name.lower()
    if name == "binai":
        
        # === v18.0 YÜKSELTMESİ (Non-Blocking) ===
        # (v10.0'da "Evrim Motoru" (Optimizer) ana 'run.py' terminalini
        # 'subprocess.run' (engeller) ile kilitliyordu)
        
        if "binai_optimizer" in active_subsystems and active_subsystems["binai_optimizer"]["process"].poll() is None:
            print(f"[Core Runner] SİSTEM HATA: 'Evrim Motoru' (Optimizer) zaten çalışıyor (PID: {active_subsystems['binai_optimizer']['process'].pid}).")
            return

        print("[Core Runner] SİSTEM: Otonom Evrim (v18.0 'Yaratıcı Zeka') başlatıldı.")
        print("[Core Runner] SİSTEM: 'Evrim Motoru' (Optimizer) arka planda (non-blocking) çalıştırılıyor...")
        
        script_path = os.path.join("binai", "optimizer.py")
        log_path = os.path.join("binai", "binai_optimizer_runtime.log") # v18.0: Optimizer için ayrı log dosyası
        
        if not os.path.exists(script_path):
            print(f"[Core Runner] SİSTEM HATA: {script_path} optimizer modülü bulunamadı.")
            return

        try:
            log_file = open(log_path, "a", encoding="utf-8")
            
            process = subprocess.Popen(
                [sys.executable, script_path], # Mevcut python'u kullan
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            active_subsystems["binai_optimizer"] = {"process": process, "log_file": log_file}
            print(f"[Core Runner] SİSTEM: 'Evrim Motoru' (v18.0) başarıyla başlatıldı. PID: {process.pid}")
            print(f"[Core Runner] SİSTEM: Evrim logları şuraya yönlendirildi: {log_path}")
            print("[Core Runner] SİSTEM: (Evrim tamamlandığında 'Hafıza' (DB) otonom olarak güncellenecektir)")
            
        except Exception as e:
            print(f"[Core Runner] SİSTEM HATA: {name} optimizasyon modülü çalıştırılamadı: {e}")
        
    else:
        print(f"[Core Runner] SİSTEM HATA: '{name}' için tanımlı bir optimizasyon modülü yok.")

# ... (show_status fonksiyonunun başladığı yer) ...

def show_status():
    if not active_subsystems:
        print("[Core Runner] SİSTEM: Aktif çalışan hiçbir alt sistem yok.")
        return

    print("--- BaseAI Alt Sistem Durumu ---")
    for name, data in active_subsystems.items():
        pid = data["process"].pid
        if data["process"].poll() is None:
            print(f"[AKTİF]   {name} (PID: {pid})")
        else:
            return_code = data["process"].poll()
            print(f"[DURDU]   {name} (PID: {pid}) - Çıkış Kodu: {return_code}")
    print("---------------------------------")

def shutdown_all_subsystems():
    print("[Core Runner] SİSTEM: Tüm aktif alt sistemler durduruluyor...")
    # 'list()' kopyalama yapar, 'dictionary changed size during iteration' hatasını önler
    for name in list(active_subsystems.keys()):
        stop_subsystem(name)
        
# === MEVCUT ÇEKİRDEK KODU (GÜNCELLENDİ) ===

async def run_interactive_mode(engine: BaseAIEngine):
    """
    Partner ile interaktif (etkileşimli) oturum başlatır.
    Alt sistem yönetim komutlarını (start/stop/status) yakalar.
    """
    print("\n--- [BaseAI Etkileşimli Oturum (Enterprise+++ / Gemini-Özel)] ---")
    print("Sistem görevleri almaya hazır. 'exit', 'start binai', 'stop binai', 'status' kullanılabilir.")

    while True:
        try:
            raw_intent = input("\n[Partner] BaseAI'ye Niyetinizi Girin: ")
            
            # GÜNCELLENDİ: Komut yakalama (Interception)
            intent_clean = raw_intent.strip().lower()
            command_parts = intent_clean.split()
            
            if not command_parts:
                continue

            action = command_parts[0]

            if action in ["exit", "quit", "çıkış"]:
                logger.info("Etkileşimli oturum sonlandırılıyor. Sistem kapatılıyor.")
                break
            
            # ALT SİSTEM YÖNETİCİSİ KOMUTLARI
            if action == "start" and len(command_parts) > 1:
                start_subsystem(command_parts[1])
                continue # Niyeti BaseAIEngine'e gönderme

            if action == "stop" and len(command_parts) > 1:
                stop_subsystem(command_parts[1])
                continue # Niyeti BaseAIEngine'e gönderme

            if action == "analyze" and len(command_parts) > 1:
                analyze_subsystem(command_parts[1])
                continue # Niyeti BaseAIEngine'e gönderme

            if action == "backtest" and len(command_parts) > 1:
                backtest_subsystem(command_parts[1])
                continue # Niyeti BaseAIEngine'e gönderme

            if action == "optimize" and len(command_parts) > 1:
                optimize_subsystem(command_parts[1])
                continue # Niyeti BaseAIEngine'e gönderme
                
            if action == "status":
                show_status()
                continue # Niyeti BaseAIEngine'e gönderme

            # Varsayılan davranış: Niyeti ana motora (BaseAIEngine) ilet
            success = await engine.execute_pipeline(raw_intent)
            if not success:
                print("\n[BaseAI] Görev başarısız oldu. Logları kontrol edin.")

        except KeyboardInterrupt:
            logger.info("Manuel kapatma algılandı. Oturum sonlandırılıyor.")
            break
        except Exception as e:
            logger.error(f"Etkileşimli modda hata oluştu: {e}", exc_info=True)



async def main():
    try:
        engine_core = BaseAIEngine()
        await run_interactive_mode(engine_core)
    except SystemExit as e:
        logger.critical(f"Sistem başlatılamadı veya durduruldu. Sebep: {e}")
    except Exception as e:
        logger.critical(f"__main__ bloğunda yakalanan kritik hata: {e}", exc_info=True)
    finally:
        # GÜNCELLENDİ: Temiz kapatma
        logger.info("BaseAI çekirdeği kapatılıyor. Tüm alt sistemler durduruluyor.")
        shutdown_all_subsystems()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Sistem kapatıldı.")