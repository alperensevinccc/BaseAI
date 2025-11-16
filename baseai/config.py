"""
BaseAI E3+ Merkezi Yapılandırma Yöneticisi (v8.2 / Vertex AI / Rich Logging)
Döngüsel içe aktarma hatalarını önler ve 'rich' ile renkli loglama sağlar.
"""
import logging
import traceback
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import ValidationError

# [P4 YÜKSELTME] Enterprise+++ renkli loglama için 'rich' kütüphanesi.
try:
    from rich.logging import RichHandler
except ImportError:
    print("[Config: UYARI] 'rich' kütüphanesi bulunamadı. Renkli loglama devre dışı.")
    print("Kurmak için: pip install rich")
    RichHandler = None

class Settings(BaseSettings):
    """
    Sistem yapılandırmasını .env dosyasından yükler ve doğrular.
    Bu modül, BaseAI içindeki BAŞKA HİÇBİR MODÜLÜ içe aktarmaz (Döngüsel hatayı önler).
    """
    model_config = SettingsConfigDict(
        env_file='.env', 
        env_file_encoding='utf-8', 
        extra='ignore' 
    )

    # ================================================================
    # 🔑 GOOGLE CLOUD (VERTEX AI) AYARLARI
    # ================================================================
    GOOGLE_PROJECT_ID: str
    GOOGLE_REGION: str

    # ================================================================
    # ⚙️ ÇEKİRDEK MOTOR AYARLARI
    # ================================================================
    BASEAI_ENVIRONMENT: str = "production"
    BASEAI_LOG_LEVEL: str = "INFO"
    DEFAULT_GEMINI_MODEL: str = "gemini-2.0-flash-001" 

try:
    config = Settings()

    # [P4 YÜKSELTME] Standart logging yerine 'rich' handler kullan.
    if RichHandler:
        logging.basicConfig(
            level=config.BASEAI_LOG_LEVEL.upper(),
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True, show_path=False, show_level=True)]
        )
    else:
        # 'rich' yoksa standart loglamaya geri dön
        logging.basicConfig(
            level=config.BASEAI_LOG_LEVEL.upper(),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Vertex AI SDK'sı çok "geveze"dir. Gürültüyü azalt.
    logging.getLogger("google.api_core").setLevel(logging.WARNING)
    logging.getLogger("google.cloud").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger = logging.getLogger("baseai.config")

    # Proje ID kontrolü
    if not config.GOOGLE_PROJECT_ID:
        raise ValueError("GOOGLE_PROJECT_ID .env dosyasında bulunamadı veya boş.")

    logger.info(f"Yapılandırma yüklendi. Ortam: {config.BASEAI_ENVIRONMENT}")
    logger.info(f"Kullanılacak Model: {config.DEFAULT_GEMINI_MODEL}")
    logger.info(f"Kullanılacak Proje (Vertex AI): {config.GOOGLE_PROJECT_ID}")

except (ValidationError, ValueError) as e:
    # 'config' nesnesi oluşturulamazsa, sistemin geri kalanı bunu bilir.
    print(f"[Config: KRİTİK HATA] Yapılandırma yüklenemedi. .env dosyasını kontrol edin. Hata: {e}")
    config = None