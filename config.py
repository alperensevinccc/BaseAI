import os
from dotenv import load_dotenv


class Config:
    """
    BaseAI Çekirdek Yapılandırma Yöneticisi.
    .env dosyasından tüm API anahtarlarını ve ayarları yükler.
    Bu, sistemin güvenli ve merkezi yapılandırma noktasıdır.
    """

    def __init__(self):
        # .env dosyasının yolunu güvenli bir şekilde bul ve yükle
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if not os.path.exists(env_path):
            print("[Core System: HATA] .env dosyası bulunamadı. Lütfen oluşturun.")
            raise FileNotFoundError(".env dosyası mevcut değil.")

        load_dotenv(dotenv_path=env_path)

        # API Anahtarları
        self.gemini_api_key = self._get_env_variable("GEMINI_API_KEY")
        self.openai_api_key = self._get_env_variable("OPENAI_API_KEY")

        # Sistem Ayarları
        self.log_level = self.get_env_variable("LOG_LEVEL", "INFO")
        self.environment = self.get_env_variable("ENVIRONMENT", "DEVELOPMENT")

        print("[Core System: Config] Yapılandırma başarıyla yüklendi.")

    def _get_env_variable(self, var_name: str) -> str:
        """
        Çevre değişkenini alır veya eksikse kritik hata fırlatır.
        """
        value = os.getenv(var_name)
        if value is None:
            print(f"[Core System: HATA] Zorunlu çevre değişkeni eksik: {var_name}")
            raise EnvironmentError(f"{var_name} .env dosyasında tanımlanmamış.")
        return value

    def get_env_variable(self, var_name: str, default: str = None) -> str:
        """
        İsteğe bağlı çevre değişkenini alır veya varsayılan değeri döndürür.
        """
        return os.getenv(var_name, default)


# BaseAI ekosisteminin her yerinden erişilebilecek tekil yapılandırma nesnesi
try:
    config = Config()
except (FileNotFoundError, EnvironmentError) as e:
    print(f"[Core System: Başlatma Başarısız] {e}")
    config = None
