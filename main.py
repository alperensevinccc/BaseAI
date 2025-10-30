import sys
from typing import Optional

try:
    from config import config
    from core.intent_processor import IntentProcessor
    from core.api_orchestrator import ApiOrchestrator
    from core.auditor import CodeAuditor
except ImportError as e:
    print(f"[BaseAI: KRİTİK HATA] Çekirdek modüller yüklenemedi: {e}")
    print("Lütfen 'requirements.txt' bağımlılıklarının kurulu olduğundan emin olun.")
    sys.exit(1)
except Exception as e:
    print(f"[BaseAI: KRİTİK HATA] Beklenmedik başlatma hatası: {e}")
    sys.exit(1)

# TODO: Gelecek adımda 'FileWriter' modülü buraya eklenecek.
# from core.file_writer import FileWriter


class BaseAI:
    """
    BaseAI Çekirdek Sistemi.
    Tüm modülleri (Processor, Orchestrator, Auditor, Writer) yönetir.
    Partner'dan gelen niyeti alır ve üretime hazır kod/mimari teslim eder.
    """

    def __init__(self):
        if config is None:
            print(
                "[BaseAI: KRİTİK HATA] Yapılandırma (config) yüklenemedi. .env dosyasını kontrol edin."
            )
            raise SystemExit("Sistem başlatılamadı.")

        self.config = config
        self.processor = IntentProcessor()
        self.orchestrator = ApiOrchestrator()
        self.auditor = CodeAuditor()
        # self.writer = FileWriter() # Gelecek adım

        print("\n--- [BaseAI Çekirdeği Başarıyla Başlatıldı] ---")
        print(f"[BaseAI] Durum: Aktif. Ortam: {self.config.environment}")
        print("[BaseAI] Stratejik Çevirmen, Orkestratör ve Denetçi modülleri devrede.")

    def execute_full_pipeline(self, raw_intent: str) -> Optional[str]:
        """
        BaseAI'nin tam üretim boru hattını çalıştırır.
        Niyet -> Blueprint -> Ham Kod -> Denetim -> Onaylanmış Kod
        """
        try:
            # 1. NİYET İŞLEME (PROCESS)
            print("-" * 30)
            print("[BaseAI Pipeline: Adım 1/3] Niyet işleniyor...")
            blueprint = self.processor.process_intent(raw_intent)

            # 2. KOD ÜRETİMİ (ORCHESTRATE)
            print("\n[BaseAI Pipeline: Adım 2/3] Kod üretimi (Gemini) başlatıldı...")
            # Not: Şimdilik varsayılan olarak Gemini kullanıyoruz.
            raw_code = self.orchestrator.generate_code(blueprint, target_model="gemini")

            if not raw_code:
                print(
                    "[BaseAI Pipeline: BAŞARISIZ] Orkestratör kod üretemedi. API bağlantısını kontrol edin."
                )
                return None

            # 3. DENETİM (AUDIT)
            print("\n[BaseAI Pipeline: Adım 3/3] Kod denetleniyor...")
            is_valid, report, audited_code = self.auditor.audit_code(raw_code, blueprint)

            print("-" * 30)
            if is_valid:
                print("\n[BaseAI Pipeline: BAŞARILI]")
                print(f"Denetçi Raporu: {report}")
                return audited_code
            else:
                print("\n[BaseAI Pipeline: BAŞARISIZ]")
                print(f"Denetçi Raporu: {report}")
                print("Üretilen kod reddedildi. Proje dosyalarına yazılmayacak.")
                return None

        except Exception as e:
            print(f"[BaseAI Pipeline: KRİTİK HATA] Boru hattı çalışırken çöktü: {e}")
            return None


def run_interactive_mode(base_ai: BaseAI):
    """
    Partner ile interaktif (etkileşimli) oturum başlatır.
    """
    print("\n--- [BaseAI Etkileşimli Oturum] ---")
    print("Sistem görevleri almaya hazır. 'exit' yazarak çıkabilirsiniz.")

    while True:
        try:
            raw_intent = input("\n[Partner] BaseAI'ye Niyetinizi Girin: ")
            if raw_intent.lower() in ["exit", "quit", "çıkış"]:
                print("[BaseAI] Etkileşimli oturum sonlandırılıyor. Sistem kapatılıyor.")
                break

            if not raw_intent:
                continue

            # Tam boru hattını çalıştır
            approved_code = base_ai.execute_full_pipeline(raw_intent)

            if approved_code:
                print("\n--- [ONAYLANMIŞ KOD ÇIKTISI] ---")
                print(approved_code)
                print("---------------------------------")
                # Gelecek Adım: Bu kod 'FileWriter'a gönderilecek.
                # self.writer.write_to_project(approved_code, blueprint)

        except KeyboardInterrupt:
            print("\n[BaseAI] Manuel kapatma algılandı. Oturum sonlandırılıyor.")
            break
        except Exception as e:
            print(f"[BaseAI: Oturum Hatası] Etkileşimli modda hata oluştu: {e}")


if __name__ == "__main__":
    try:
        # BaseAI Çekirdeğini Başlat
        base_ai_core = BaseAI()

        # Etkileşimli Modu Başlat
        run_interactive_mode(base_ai_core)

    except SystemExit as e:
        print(f"[BaseAI: Başlatma Başarısız] Sistem durduruldu. Sebep: {e}")
    except Exception as e:
        print(f"[BaseAI: Ana Hata] __main__ bloğunda yakalanan kritik hata: {e}")
