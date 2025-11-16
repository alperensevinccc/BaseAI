"""
BaseAI Enterprise+++ Çekirdek Başlatıcısı (Runner)
Sistemi interaktif modda başlatır ve alt sistemleri (örn: BinAI) yönetir.

v2.0 Yükseltmeleri (Enterprise):
- Profesyonel Loglama: Standart 'print' çıktıları yerine tamamen 'logging' modülü kullanıldı.
- Dinamik Path Yönetimi ('pathlib'): Sistem artık 'run.py' dosyasının konumunu
  otomatik olarak algılar ve 'binai' gibi alt modülleri bulmak için 
  sabit (hardcoded) yollar kullanmaz. Bu, sistemin her yerden çalıştırılabilmesini sağlar.
- Gelişmiş Hata Yönetimi: Subprocess (alt sistem) yönetimi için daha 
  sağlam hata yakalama mekanizmaları eklendi.
"""

# === 1. KURULUM (GEREKLİ KÜTÜPHANELER) ===

import asyncio
import logging
import sys
import subprocess
import os
from pathlib import Path  # EKLENDİ (Enterprise Path Yönetimi)

# === 2. TEMEL SİSTEM YÖNETİMİ (ENTERPRISE PATH) ===

# Bu dosyanın (run.py) bulunduğu konumu temel alarak projenin ana dizinini bulur.
# Bu, sistemin herhangi bir yerden 'python run.py' ile çalıştırılabilmesini sağlar.
try:
    BASE_DIR = Path(__file__).resolve().parent
except NameError:
    # Eğer interaktif bir kabukta (örn: IDLE) __file__ tanımlı değilse,
    # mevcut çalışma dizinini (CWD) temel al.
    BASE_DIR = Path.cwd()

# === 3. PROFESYONEL LOGLAMA KURULUMU ===

# 'print' yerine bu logger'ı kullanacağız.
# 'binai_main_runtime.log' DOSYASINA DEĞİL, BU 'run.py'NİN KENDİ ÇIKTILARI İÇİN.
log_format = "%(asctime)s - %(name)s (Runner) - %(levelname)s - %(message)s"
logging.basicConfig(
    level="INFO",
    format=log_format,
    handlers=[
        logging.StreamHandler(sys.stdout)  # Çıktıyı terminale yaz
    ]
)
logger = logging.getLogger("BaseAI_Runner")


# === 4. BASEAI ÇEKİRDEK MOTORU VE YAPILANDIRMA ===

try:
    # BaseAI motorunu ve yapılandırmayı yükle
    # 'config' ve 'engine' dosyalarının 'baseai' klasöründe olduğunu varsayar
    from baseai.config import config
    if not config:
        logger.critical("Yapılandırma yüklenemedi. .env dosyasını kontrol edin.")
        sys.exit(1)
        
    from baseai.engine import BaseAIEngine
    
except ImportError as e:
    logger.critical(f"Kritik Hata: BaseAI motoru veya bileşenleri bulunamadı. {e}")
    logger.critical("Gerekli: 'baseai' klasörü 'run.py' ile aynı dizinde olmalı.")
    logger.critical("Emin olmak için 'pip install -e .' komutu ile kurulum yapın.")
    sys.exit(1)
except Exception as e:
    logger.critical(f"Beklenmedik başlatma hatası: {e}", exc_info=True)
    sys.exit(1)


# === 5. ALT SİSTEM YÖNETİCİSİ (ENTERPRISE+++ v2) ===

# BaseAI tarafından yönetilen aktif alt sistemlerin kaydı
# { "isim": { "process": Popen_objesi, "log_file_handle": dosya_objesi, "log_path": str } }
active_subsystems = {}


def _get_subsystem_path(name: str) -> Path:
    """Alt sistemin ana python dosyasının yolunu dinamik olarak bulur."""
    return BASE_DIR / name / "main.py"

def _get_subsystem_log_path(name: str, log_file_name: str) -> Path:
    """Alt sistemin log dosyasının yolunu dinamik olarak bulur."""
    return BASE_DIR / name / log_file_name


def start_subsystem(name: str):
    """Belirtilen alt sistemi (örn: 'binai') arka planda başlatır."""
    global active_subsystems
    name = name.lower()
    
    # === Alt Sistem Tanımlamaları ===
    # Yeni bir alt sistem (örn: DropshoppingAI) eklemek için buraya yeni bir 'case' ekle.
    
    script_path = None
    log_path = None
    
    if name == "binai":
        script_path = _get_subsystem_path("binai")
        log_path = _get_subsystem_log_path("binai", "binai_main_runtime.log")
        
    elif name == "optimizer":
        # Optimizer'ı 'start optimizer' ile ayrı çalıştırabilme
        script_path = BASE_DIR / "binai" / "optimizer.py"
        log_path = _get_subsystem_log_path("binai", "binai_optimizer_runtime.log")
        
    # 'elif name == "dropshoppingai":' ... (gelecekte eklenebilir)
        
    else:
        logger.error(f"SİSTEM HATA: '{name}' adında tanımlı bir alt sistem yok.")
        return

    # --- Zaten Çalışıyor mu Kontrolü ---
    if name in active_subsystems and active_subsystems[name]["process"].poll() is None:
        logger.warning(f"SİSTEM HATA: {name} alt sistemi zaten çalışıyor (PID: {active_subsystems[name]['process'].pid}).")
        return

    # --- Dosya Yolu Kontrolü ---
    if not script_path.exists():
        logger.error(f"SİSTEM HATA: {script_path} bulunamadı. '{name}' modülleri eksik veya yanlış yerde.")
        return

    # --- Başlatma ---
    try:
        logger.info(f"SİSTEM: '{name}' alt sistemi başlatılıyor...")
        logger.info(f"SİSTEM: Loglar şuraya yönlendirildi: {log_path}")
        
        # Log dosyasını 'append' (ekleme) modunda aç
        log_file_handle = open(log_path, "a", encoding="utf-8")
        
        process = subprocess.Popen(
            [sys.executable, str(script_path)], # 'pathlib.Path' objesini str'ye çevir
            stdout=log_file_handle,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=BASE_DIR # Alt sistemin çalışma dizinini ana dizin olarak ayarla
        )
        
        active_subsystems[name] = {
            "process": process, 
            "log_file_handle": log_file_handle,
            "log_path": str(log_path)
        }
        logger.info(f"SİSTEM: '{name}' başarıyla başlatıldı. PID: {process.pid}")

    except Exception as e:
        logger.critical(f"SİSTEM HATA: '{name}' başlatılamadı!", exc_info=e)
        if 'log_file_handle' in locals():
            log_file_handle.close() # Hata olursa dosyayı kapatmayı unutma


def stop_subsystem(name: str):
    """Belirtilen alt sistemi güvenli bir şekilde durdurur (terminate -> kill)."""
    global active_subsystems
    name = name.lower()

    if name not in active_subsystems:
        logger.error(f"SİSTEM HATA: '{name}' alt sistemi bulunamadı (belki hiç başlatılmadı?).")
        return
        
    process_data = active_subsystems[name]
    
    if process_data["process"].poll() is not None:
        logger.warning(f"SİSTEM UYARI: '{name}' alt sistemi zaten çalışmıyor (DURMUŞ).")
        # 'active_subsystems' listesinden temizle
        process_data["log_file_handle"].close()
        del active_subsystems[name]
        return

    logger.info(f"SİSTEM: '{name}' alt sistemi (PID: {process_data['process'].pid}) durduruluyor...")
    try:
        # 1. Aşama: Nazikçe Kapat (Terminate)
        process_data["process"].terminate()
        
        try:
            # 2. Aşama: Kapanmasını Bekle (5 saniye)
            process_data["process"].wait(timeout=5)
        except subprocess.TimeoutExpired:
            # 3. Aşama: Kapanmazsa Zorla Kapat (Kill)
            logger.warning(f"SİSTEM UYARI: '{name}' 5 saniyede kapanmadı. Zorla sonlandırılıyor (SIGKILL)...")
            process_data["process"].kill()
            process_data["process"].wait() # 'kill' sonrası bekleme

        # Kapatma sonrası temizlik
        process_data["log_file_handle"].close()
        del active_subsystems[name]
        logger.info(f"SİSTEM: '{name}' başarıyla durduruldu.")
        
    except Exception as e:
        logger.error(f"SİSTEM HATA: '{name}' durdurulurken hata oluştu:", exc_info=e)


def _run_blocking_command(name: str, script_name: str, friendly_name: str):
    """
    'analyze' ve 'backtest' gibi bir kez çalışıp biten (engellenen) 
    komutlar için DRY (Tekrar Etmeyen) yardımcı fonksiyon.
    """
    script_path = BASE_DIR / "binai" / script_name
    
    if not script_path.exists():
        logger.error(f"SİSTEM HATA: {script_path} ({friendly_name} modülü) bulunamadı.")
        return
        
    logger.info(f"SİSTEM: '{name}' {friendly_name} Modülü çalıştırılıyor...")
    logger.info("[Core Runner] Lütfen bekleyin, komutun bitmesi bekleniyor...")
    
    try:
        # Bu komutun bitmesini BEKLER (Popen'in tersi)
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, # Çıktıyı yakala
            text=True,
            encoding="utf-8",
            cwd=BASE_DIR
        )
        
        # Çıktıyı doğrudan bu terminale (logger aracılığıyla) yazdır
        if result.stdout:
            # 'print()' yerine logger kullanmak, çıktıyı temiz tutar
            sys.stdout.write(result.stdout)
            sys.stdout.flush()
            
        if result.stderr:
            logger.error(f"SİSTEM: '{friendly_name}' çalışırken hata oluştu:\n{result.stderr}")
            
    except Exception as e:
        logger.critical(f"SİSTEM HATA: '{name}' {friendly_name} modülü çalıştırılamadı!", exc_info=e)


def analyze_subsystem(name: str):
    """BinAI Otonom Analiz Motorunu (analyzer.py) çalıştırır."""
    name = name.lower()
    if name == "binai":
        _run_blocking_command("binai", "analyzer.py", "Analiz Motoru")
    else:
        logger.error(f"SİSTEM HATA: '{name}' için tanımlı bir analiz modülü yok.")

def backtest_subsystem(name: str):
    """BinAI Evrim Motoru (Backtest) (backtester.py) çalıştırır."""
    name = name.lower()
    if name == "binai":
        _run_blocking_command("binai", "backtester.py", "Evrim Motoru (Backtest)")
    else:
        logger.error(f"SİSTEM HATA: '{name}' için tanımlı bir backtest modülü yok.")

def optimize_subsystem(name: str):
    """BinAI Evrim Motoru (Optimizer) (optimizer.py) çalıştırır (Arka Planda)."""
    name = name.lower()
    if name == "binai":
        # 'optimizer' özel bir 'start_subsystem' komutudur
        logger.info("[Core Runner] SİSTEM: 'Evrim Motoru' (Optimizer v18.0 'Yaratıcı Zeka') başlatılıyor...")
        start_subsystem("optimizer")
    else:
        logger.error(f"SİSTEM HATA: '{name}' için tanımlı bir optimizasyon modülü yok.")

def show_status():
    """Tüm aktif alt sistemlerin durumunu (PID) gösterir."""
    logger.info("--- BaseAI Alt Sistem Durumu ---")
    if not active_subsystems:
        logger.info("[SİSTEM] Aktif çalışan hiçbir alt sistem yok.")
        print("---------------------------------")
        return

    # 'poll()' ile anlık durumu kontrol et
    for name, data in active_subsystems.items():
        pid = data["process"].pid
        if data["process"].poll() is None:
            logger.info(f"[AKTİF]   {name.upper()} (PID: {pid}) -> Log: {data['log_path']}")
        else:
            return_code = data["process"].poll()
            logger.warning(f"[DURDU]   {name.upper()} (PID: {pid}) - Çıkış Kodu: {return_code}")
    logger.info("---------------------------------")


def shutdown_all_subsystems():
    """Çıkış yaparken tüm alt sistemleri güvenli bir şekilde kapatır."""
    logger.info("SİSTEM: Tüm aktif alt sistemler durduruluyor...")
    # 'list()' kopyalama yapar, 'dictionary changed size during iteration' hatasını önler
    for name in list(active_subsystems.keys()):
        stop_subsystem(name)


# === 6. ETKİLEŞİMLİ OTURUM (ANA DÖNGÜ) ===

async def run_interactive_mode(engine: BaseAIEngine):
    """
    Partner ile interaktif (etkileşimli) oturum başlatır.
    Alt sistem yönetim komutlarını (start/stop/status vb.) yakalar.
    """
    logger.info("--- [BaseAI Etkileşimli Oturum (Enterprise+++ / Gemini-Özel)] ---")
    logger.info("Sistem görevleri almaya hazır.")
    logger.info("Kullanılabilir komutlar: 'start binai', 'stop binai', 'status', 'analyze binai', 'backtest binai', 'optimize binai', 'exit'")

    while True:
        try:
            raw_intent = input("\n[Partner] BaseAI'ye Niyetinizi Girin: ")
            
            intent_clean = raw_intent.strip().lower()
            command_parts = intent_clean.split()
            
            if not command_parts:
                continue

            action = command_parts[0]

            if action in ["exit", "quit", "çıkış", "kapat"]:
                logger.info("Etkileşimli oturum sonlandırılıyor...")
                break
            
            # --- ALT SİSTEM YÖNETİCİSİ KOMUT YAKALAMA (INTERCEPTION) ---
            # Bu komutlar BaseAIEngine'e (Gemini motoruna) HİÇ GİTMEZ.
            
            subsystem_name = command_parts[1] if len(command_parts) > 1 else None

            if action == "start" and subsystem_name:
                start_subsystem(subsystem_name)
                continue 

            if action == "stop" and subsystem_name:
                stop_subsystem(subsystem_name)
                continue 

            if action == "analyze" and subsystem_name:
                analyze_subsystem(subsystem_name)
                continue 

            if action == "backtest" and subsystem_name:
                backtest_subsystem(subsystem_name)
                continue 

            if action == "optimize" and subsystem_name:
                optimize_subsystem(subsystem_name)
                continue 
                
            if action == "status":
                show_status()
                continue 

            # --- Varsayılan Davranış: Niyeti BaseAI Çekirdeğine İlet ---
            logger.info(f"Niyet '{raw_intent}' BaseAI Çekirdeğine (Engine) iletiliyor...")
            success = await engine.execute_pipeline(raw_intent)
            if not success:
                logger.error("Görev başarısız oldu. BaseAI Motor loglarını kontrol edin.")

        except (KeyboardInterrupt, EOFError):
            logger.info("Manuel kapatma (Ctrl+C / Ctrl+D) algılandı. Oturum sonlandırılıyor.")
            break
        except Exception as e:
            logger.error(f"Etkileşimli modda beklenmedik bir hata oluştu:", exc_info=e)


# === 7. ANA BAŞLATMA NOKTASI ===

async def main():
    """Ana Asenkron fonksiyon."""
    engine_core = None
    try:
        engine_core = BaseAIEngine()
        await run_interactive_mode(engine_core)
        
    except SystemExit as e:
        logger.critical(f"Sistem başlatılamadı veya zorla durduruldu. Sebep: {e}")
    except Exception as e:
        logger.critical(f"__main__ bloğunda yakalanan kritik hata:", exc_info=e)
    finally:
        # TEMİZ KAPATMA (En Önemli Kısım)
        logger.info("BaseAI çekirdeği kapatılıyor...")
        shutdown_all_subsystems()
        # Eğer engine_core'un da 'await engine_core.shutdown()' gibi bir 
        # kapatma metoduna ihtiyacı varsa, buraya eklenebilir.
        logger.info("Tüm sistemler durduruldu. Çıkış yapıldı.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Bu, 'asyncio.run(main())' içindeki KeyboardInterrupt'ı yakalar
        logger.info("Sistem kapatma işlemi (Ctrl+C) algılandı... Lütfen bekleyin.")