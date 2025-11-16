"""
BaseAI - BinAI v21.1 Mimarisi
"Kurumsal" (Enterprise) Log Yöneticisi

v21.1 Yükseltmeleri (Enterprise+++):
- Entegrasyon Düzeltmesi: 'config.LOG_FILE' (hatalı) yerine 'config.CORE_LOG_FILE'
  (v21.1) kullanımı düzeltildi.
- Kararlı (Stable) Path (Yol) Yönetimi: Log dosyası ('CORE_LOG_FILE') artık 
  'mevcut çalışma dizinine' (CWD) değil, 'pathlib' kullanılarak 
  *her zaman* projenin ana dizinine (BASE_DIR) yazılır.
- Açık (Explicit) Handler Kurulumu: 'coloredlogs.install()' (örtük) yerine
  'ColoredFormatter' (açık) kullanılarak daha temiz ve kararlı
  bir 'console' ve 'file' handler kurulumu yapıldı.
"""

import logging
import sys
import os
from pathlib import Path
import coloredlogs # 'Renkli' (Colored) formatlama için gerekli

# === BİNAİ MODÜLLERİ ===
# (config'i import edebilmek için, 'binai' klasörünün 
# Python path'inde olduğunu varsayıyoruz)
try:
    from binai import config
except ImportError as e:
    print(f"KRİTİK HATA (logger.py): 'config' modülü bulunamadı. {e}")
    sys.exit(1)


# === v21.1 DİNAMİK PATH (YOL) YÖNETİMİ ===
try:
    # Bu dosyanın (logger.py) konumu: /BaseAI/binai/logger.py
    BINAI_DIR = Path(__file__).resolve().parent
    # Ana Proje Dizini: /BaseAI/
    BASE_DIR = BINAI_DIR.parent
except NameError:
    # (örn: interaktif kabuk)
    BINAI_DIR = Path.cwd()
    BASE_DIR = BINAI_DIR.parent

# 'config.CORE_LOG_FILE' (örn: "binai_runtime.log") dosyasını
# 'BASE_DIR' (Ana Dizin) ile birleştir.
# SONUÇ: /BaseAI/binai_runtime.log (Kararlı Yol)
LOG_FILE_PATH = BASE_DIR / config.CORE_LOG_FILE


def setup_logger():
    """
    BaseAI (v21.1) standardına uygun, hem dosyaya (kararlı yol) 
    hem de konsola (renkli) yazan logger'ı ayarlar.
    """
    
    # Ana 'BinAI' logger'ını al
    logger = logging.getLogger("BinAI")
    
    # Mevcut handler'ları temizle (tekrar çağrılma durumuna karşı)
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(config.LOG_LEVEL.upper())
    # Logların 'root' logger'a (ana) gitmesini engelle (çift loglamayı önler)
    logger.propagate = False 

    # 1. Konsol (Terminal) Handler (Renkli)
    console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    console_formatter = coloredlogs.ColoredFormatter(
        fmt=console_format,
        level_styles=coloredlogs.DEFAULT_LEVEL_STYLES,
        field_styles=coloredlogs.DEFAULT_FIELD_STYLES
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config.LOG_LEVEL.upper())
    console_handler.setFormatter(console_formatter)

    # 2. Dosya (File) Handler (Renksiz, Kararlı Yol)
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a', encoding='utf-8')
    file_handler.setLevel(config.LOG_LEVEL.upper())
    file_handler.setFormatter(file_format)

    # 3. Handler'ları 'BinAI' logger'ına ekle
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

# === ANA LOG OBJESİ ===
# Tüm diğer modüller (main.py, strategy.py vb.) 
# 'from binai.logger import log' yaptıklarında bu 'log' objesini alacaklar.
log = setup_logger()

# Başlangıç logu (Logger'ın kendisinin çalıştığını doğrulamak için)
log.info(f"BinAI Logger (v21.1) başlatıldı. Log seviyesi: {config.LOG_LEVEL}")
log.info(f"Log dosyası şuraya yazılıyor: {LOG_FILE_PATH}")